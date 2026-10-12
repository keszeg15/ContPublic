#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Download a Google Doc and convert it to Quartz-flavoured Markdown.

This covers the fetch + convert stage only. It produces one large Markdown file
plus an extracted image folder; splitting that into individual wiki notes is a
separate step.

The document must be shared as "anyone with the link", which is what allows the
export endpoint to be called without any authentication.

Only the standard library is used, so the script runs under a bare `python3`.
pandoc has to be on PATH.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

DEFAULT_DOC_ID = "1kqRKCE7SC9ZBxYFklRfUqybh3DkJ0xFwTo11AxCJ3Lg"
DEFAULT_SLUG = "partylog"
EXPORT_URL = "https://docs.google.com/document/d/{doc_id}/export?format={fmt}"
EDIT_URL = "https://docs.google.com/document/d/{doc_id}/edit"

# The tab list in the model the editor page is built from: the first tab on its
# own, then every other one with its position. A JSON string literal each.
FIRST_TAB = re.compile(r'\{"ty":"mkch","d":\[\[1,("(?:[^"\\]|\\.)*")\]\]\}')
OTHER_TAB = re.compile(r'\{"ty":"ac","d":\["t\.[^"]+",\[1,("(?:[^"\\]|\\.)*")\],\[(\d+)\]\]\}')

# Google serves an HTML error page with a 200 status when a document is not
# publicly readable, so the payload itself has to be validated.
DOCX_MAGIC = b"PK\x03\x04"

IMG_TAG = re.compile(r'<img src="(?P<src>[^"]+)"(?P<rest>[^>]*?)/?>')
HTML_TABLE = re.compile(r"<table>.*?</table>", re.S)
EMPTY_HEADING = re.compile(r"^#{1,6}[ \t]*$\n?", re.M)
EXTRA_BLANKS = re.compile(r"\n{4,}")

# Word paragraphs, their style, and their text. `<w:t` needs the trailing
# whitespace guard so it does not also match `<w:top>` and friends.
WORD_PARAGRAPH = re.compile(r"<w:p [^>]*>.*?</w:p>", re.S)
WORD_STYLE = re.compile(r'<w:pStyle w:val="([^"]+)"')
WORD_TEXT = re.compile(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", re.S)


def parse_doc_id(value: str) -> str:
    """Accept either a bare document id or a full Google Docs URL."""
    match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", value)
    return match.group(1) if match else value


def slugify(text: str, max_length: int = 45) -> str:
    """Turn a heading into a lowercase ASCII slug usable as a file name."""
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[\\*_`~]", "", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_length].strip("-") or "image"


def download(doc_id: str, fmt: str, dest: Path) -> bytes:
    url = EXPORT_URL.format(doc_id=doc_id, fmt=fmt)
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Export failed for format={fmt}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Export failed for format={fmt}: {exc.reason}") from exc

    if fmt == "docx" and not payload.startswith(DOCX_MAGIC):
        raise SystemExit(
            "The export did not return a .docx file. The document is most "
            "likely not shared as 'anyone with the link'."
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(payload)
    return payload


def convert(docx: Path, media_root: Path) -> str:
    """Run pandoc, extracting embedded images next to the generated Markdown."""
    if media_root.exists():
        shutil.rmtree(media_root)
    media_root.mkdir(parents=True)

    command = [
        "pandoc",
        "--from=docx",
        "--to=gfm",
        "--wrap=none",
        f"--extract-media={media_root}",
        str(docx),
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except FileNotFoundError:
        raise SystemExit(
            "pandoc was not found on PATH. Install it with `sudo apt install pandoc`, "
            "`brew install pandoc`, or from https://pandoc.org/installing.html"
        ) from None
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(f"pandoc exited with {error.returncode}: {detail}") from None

    # pandoc writes UTF-8 whatever the locale says, and emits CRLF on Windows,
    # which would stop the cleanup patterns below from ever matching an end of line.
    markdown = result.stdout.decode("utf-8")
    return markdown.replace("\r\n", "\n").replace("\r", "\n")


def normalise_title(text: str) -> str:
    """Strip export artefacts so titles can be compared across the two exports."""
    text = re.sub(r"\{#[^}]*\}", "", text)
    text = re.sub(r"\\(.)", r"\1", text)
    text = re.sub(r"[*_`]", "", text)
    return " ".join(text.split())


def read_docx_titles(docx: Path) -> tuple[list[str], list[str]]:
    """Find the Google Docs tab boundaries inside the .docx.

    Google gives every tab title a `Title` styled paragraph that also starts a
    new page and a new section, while a `Title` used as an ordinary heading
    within a tab has neither. That is the only dependable difference: the
    style, the font size and even the text can be identical between the two.

    Returns the tab titles in document order plus every `Title` text, the
    latter so the splitter can drop headings that merely restate a tab name.
    """
    xml = zipfile.ZipFile(docx).read("word/document.xml").decode("utf-8")
    tabs: list[str] = []
    titles: list[str] = []
    for paragraph in WORD_PARAGRAPH.findall(xml):
        style = WORD_STYLE.search(paragraph)
        if not style or style.group(1) != "Title":
            continue
        text = " ".join("".join(WORD_TEXT.findall(paragraph)).split())
        if not text:
            continue
        titles.append(text)
        if "<w:pageBreakBefore" in paragraph and "<w:sectPr" in paragraph:
            tabs.append(text)
    return tabs, titles


def fetch_tab_names(doc_id: str) -> list[str]:
    """Read the tab names off the document's public page, in tab order.

    Needed when the export carries no tab titles at all, only a section break
    where one tab ends. The page is not a documented interface, so an empty
    list means its layout moved on, not that the document has no tabs.
    """
    request = urllib.request.Request(EDIT_URL.format(doc_id=doc_id), headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            page = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise SystemExit(f"Could not read the tab names off the document page: {exc}") from exc

    first = FIRST_TAB.search(page)
    if not first:
        return []
    others = sorted((int(position), json.loads(name)) for name, position in OTHER_TAB.findall(page))
    return [json.loads(first.group(1))] + [name for _, name in others]


def insert_tab_titles(docx: Path, names: list[str], dest: Path) -> None:
    """Write a copy of the export with a `Title` paragraph opening every tab.

    That is the shape the export used to have, and what the rest of the chain
    reads: pandoc takes the first title as the document title and leaves the
    others as bare lines for `promote_tab_titles` to find. A tab ends with the
    paragraph that carries its section break, so the next title goes after it.
    """
    with zipfile.ZipFile(docx) as source:
        xml = source.read("word/document.xml").decode("utf-8")
        ends = [match.end() for match in WORD_PARAGRAPH.finditer(xml) if "<w:sectPr" in match.group(0)]
        if len(ends) + 1 != len(names):
            raise SystemExit(
                f"The export has {len(ends) + 1} tabs by its section breaks, but the document page "
                f"lists {len(names)}: {', '.join(names)}"
            )
        body = re.search(r"<w:body[^>]*>", xml).end()
        for position, name in reversed(list(zip([body] + ends, names))):
            title = (
                '<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr>'
                f'<w:r><w:t xml:space="preserve">{escape(name)}</w:t></w:r></w:p>'
            )
            xml = xml[:position] + title + xml[position:]

        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                data = xml.encode("utf-8") if item.filename == "word/document.xml" else source.read(item.filename)
                target.writestr(item, data)


def promote_tab_titles(markdown: str, tab_titles: list[str]) -> tuple[str, list[str]]:
    """Turn the flattened tab titles back into level 1 headings.

    pandoc renders a `Title` paragraph as ordinary text, so each tab boundary
    arrives as a bare line and has to be marked up again before the document
    can be split on it. The very first tab is the exception: pandoc consumes it
    as the document title, so it never appears in the body at all.
    """
    pending = list(tab_titles)
    promoted: list[str] = []
    lines = markdown.split("\n")
    for index, line in enumerate(lines):
        if line.startswith("#"):
            continue
        title = normalise_title(line)
        if title in pending:
            lines[index] = f"# {title}"
            promoted.append(title)
            pending.remove(title)
    return "\n".join(lines), promoted


def collect_headings(markdown: str) -> list[tuple[int, str]]:
    return [
        (m.start(), m.group(1).strip())
        for m in re.finditer(r"^#{1,6}[ \t]*(.*)$", markdown, re.M)
        if m.group(1).strip()
    ]


def rewrite_images(markdown: str, media_root: Path, pics_dir: Path, prefix: str) -> tuple[str, int, int]:
    """Rename extracted images after their section and fix every reference.

    Images sitting in a plain paragraph become Obsidian embeds. Images inside a
    raw HTML table have to stay <img> tags, because an embed would not be
    rendered inside an HTML block, so those only get their src rewritten.
    """
    headings = collect_headings(markdown)
    tables = [(m.start(), m.end()) for m in HTML_TABLE.finditer(markdown)]
    pics_dir.mkdir(parents=True, exist_ok=True)

    used: dict[str, int] = {}
    embeds = 0
    html_refs = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal embeds, html_refs
        source = Path(re.split(r"[\\/]", match.group("src"))[-1])
        origin = media_root / "media" / source.name
        if not origin.exists():
            return match.group(0)

        preceding = [title for pos, title in headings if pos < match.start()]
        base = slugify(preceding[-1]) if preceding else "image"
        stem = f"{prefix}-{base}" if prefix else base
        used[stem] = used.get(stem, 0) + 1
        name = f"{stem}-{used[stem]}{source.suffix.lower()}"

        shutil.copy2(origin, pics_dir / name)

        if any(start <= match.start() < end for start, end in tables):
            html_refs += 1
            return f'<img src="{pics_dir.name}/{name}"{match.group("rest")}/>'

        embeds += 1
        return f"![[{name}]]"

    return IMG_TAG.sub(replace, markdown), embeds, html_refs


def tidy(markdown: str) -> str:
    markdown = EMPTY_HEADING.sub("", markdown)
    markdown = EXTRA_BLANKS.sub("\n\n\n", markdown)
    return markdown.strip() + "\n"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc-id", default=DEFAULT_DOC_ID, help="document id or full Google Docs URL")
    parser.add_argument("--slug", default=DEFAULT_SLUG, help="base name for the generated files")
    parser.add_argument("--image-prefix", default=None, help="image name prefix (defaults to --slug)")
    parser.add_argument("--work-dir", type=Path, default=script_dir / "build", help="staging directory")
    parser.add_argument("--skip-download", action="store_true", help="reuse the previously downloaded export")
    parser.add_argument("--google-md", action="store_true", help="also fetch Google's own Markdown export, to compare against")
    args = parser.parse_args()

    doc_id = parse_doc_id(args.doc_id)
    prefix = args.slug if args.image_prefix is None else args.image_prefix
    raw_dir = args.work_dir / "raw"
    out_dir = args.work_dir / "out"
    docx = raw_dir / f"{args.slug}.docx"
    google_md = raw_dir / f"{args.slug}.google.md"
    names_file = raw_dir / f"{args.slug}.tabnames.json"

    if args.skip_download:
        if not docx.exists():
            raise SystemExit(f"No cached export at {docx}. Run without --skip-download first.")
        print(f"Reusing {docx}")
    else:
        print(f"Downloading document {doc_id} ...")
        payload = download(doc_id, "docx", docx)
        digest = hashlib.sha256(payload).hexdigest()[:12]
        print(f"  {docx.name}: {len(payload) / 1e6:.1f} MB (sha256 {digest})")
        if args.google_md:
            reference = download(doc_id, "md", google_md)
            print(f"  {google_md.name}: {len(reference) / 1e6:.1f} MB")

    tab_titles, all_titles = read_docx_titles(docx)
    print(f"Found {len(tab_titles)} tabs among {len(all_titles)} Title paragraphs")

    source = docx
    if not tab_titles:
        if args.skip_download and names_file.exists():
            tab_titles = json.loads(names_file.read_text(encoding="utf-8"))
            print(f"The export carries no tab titles; reusing the {len(tab_titles)} names in {names_file.name}")
        else:
            tab_titles = fetch_tab_names(doc_id)
            if not tab_titles:
                raise SystemExit(
                    "The export carries no tab titles, and none could be read off the document page either."
                )
            names_file.write_text(json.dumps(tab_titles, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"The export carries no tab titles; read {len(tab_titles)} off the document page")
        source = raw_dir / f"{args.slug}.titled.docx"
        insert_tab_titles(docx, tab_titles, source)
        all_titles = tab_titles + all_titles

    print("Converting with pandoc ...")
    media_root = args.work_dir / "media"
    markdown = convert(source, media_root)
    markdown, promoted = promote_tab_titles(markdown, tab_titles)

    pics_dir = out_dir / "pics"
    if pics_dir.exists():
        shutil.rmtree(pics_dir)
    markdown, embeds, html_refs = rewrite_images(markdown, media_root, pics_dir, prefix)
    markdown = tidy(markdown)

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{args.slug}.md"
    target.write_text(markdown, encoding="utf-8", newline="\n")
    tabs_file = out_dir / f"{args.slug}.tabs.json"
    tabs_file.write_text(
        json.dumps({"tabs": tab_titles, "titles": all_titles}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    shutil.rmtree(media_root, ignore_errors=True)

    levels: dict[int, int] = {}
    for match in re.finditer(r"^(#{1,6})[ \t]*\S", markdown, re.M):
        level = len(match.group(1))
        levels[level] = levels.get(level, 0) + 1

    print(f"\nWrote {target}")
    print(f"  {len(markdown) / 1000:.0f} kB, headings " + ", ".join(f"h{k}={v}" for k, v in sorted(levels.items())))
    print(f"  images: {embeds} embedded, {html_refs} kept as <img> inside tables -> {pics_dir}")
    if promoted:
        print(f"  tab titles restored as headings: {', '.join(promoted)}")
    print(f"  {len(tab_titles)} tabs recorded in {tabs_file.name}")
    if HTML_TABLE.search(markdown):
        print(f"  note: {len(HTML_TABLE.findall(markdown))} tables remain as raw HTML (too complex for GFM)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
