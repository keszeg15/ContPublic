#!/usr/bin/env python3
"""Download a Google Doc and convert it to Quartz-flavoured Markdown.

This covers the fetch + convert stage only. It produces one large Markdown file
plus an extracted image folder; splitting that into individual wiki notes is a
separate step.

The document must be shared as "anyone with the link", which is what allows the
export endpoint to be called without any authentication.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

import pypandoc

DEFAULT_DOC_ID = "1kqRKCE7SC9ZBxYFklRfUqybh3DkJ0xFwTo11AxCJ3Lg"
DEFAULT_SLUG = "partylog"
EXPORT_URL = "https://docs.google.com/document/d/{doc_id}/export?format={fmt}"

# Google serves an HTML error page with a 200 status when a document is not
# publicly readable, so the payload itself has to be validated.
DOCX_MAGIC = b"PK\x03\x04"

IMG_TAG = re.compile(r'<img src="(?P<src>[^"]+)"(?P<rest>[^>]*?)/?>')
HTML_TABLE = re.compile(r"<table>.*?</table>", re.S)
EMPTY_HEADING = re.compile(r"^#{1,6}[ \t]*$\n?", re.M)
EXTRA_BLANKS = re.compile(r"\n{4,}")


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

    markdown = pypandoc.convert_file(
        str(docx),
        to="gfm",
        format="docx",
        extra_args=["--wrap=none", f"--extract-media={media_root}"],
    )
    # pandoc emits CRLF on Windows, which would stop the cleanup patterns below
    # from ever matching an end of line.
    return markdown.replace("\r\n", "\n").replace("\r", "\n")


def normalise_title(text: str) -> str:
    """Strip export artefacts so titles can be compared across the two exports."""
    text = re.sub(r"\{#[^}]*\}", "", text)
    text = re.sub(r"\\(.)", r"\1", text)
    text = re.sub(r"[*_`]", "", text)
    return " ".join(text.split())


def promote_tab_titles(markdown: str, google_markdown: str) -> tuple[str, list[str]]:
    """Restore section titles that the .docx export flattened into plain text.

    The document is split into Google Docs tabs. The .docx export concatenates
    every tab but leaves each tab title as an ordinary paragraph, whereas
    Google's own Markdown export renders it as a level 1 heading. Comparing the
    two exports recovers the structure that would otherwise be lost.
    """
    existing = {
        normalise_title(m.group(1))
        for m in re.finditer(r"^#{1,6}[ \t]+(.*)$", markdown, re.M)
    }
    missing = [
        title
        for m in re.finditer(r"^# (.+)$", google_markdown, re.M)
        if (title := normalise_title(m.group(1))) and title not in existing
    ]

    promoted: list[str] = []
    lines = markdown.split("\n")
    for index, line in enumerate(lines):
        if line.startswith("#"):
            continue
        title = normalise_title(line)
        if title in missing:
            lines[index] = f"# {title}"
            promoted.append(title)
            missing.remove(title)
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
    parser.add_argument("--skip-download", action="store_true", help="reuse the previously downloaded exports")
    args = parser.parse_args()

    doc_id = parse_doc_id(args.doc_id)
    prefix = args.slug if args.image_prefix is None else args.image_prefix
    raw_dir = args.work_dir / "raw"
    out_dir = args.work_dir / "out"
    docx = raw_dir / f"{args.slug}.docx"
    google_md = raw_dir / f"{args.slug}.google.md"

    if args.skip_download:
        absent = [path for path in (docx, google_md) if not path.exists()]
        if absent:
            listing = ", ".join(path.name for path in absent)
            raise SystemExit(f"Missing cached export(s): {listing}. Run without --skip-download first.")
        print(f"Reusing the exports in {raw_dir}")
    else:
        print(f"Downloading document {doc_id} ...")
        payload = download(doc_id, "docx", docx)
        digest = hashlib.sha256(payload).hexdigest()[:12]
        print(f"  {docx.name}: {len(payload) / 1e6:.1f} MB (sha256 {digest})")
        reference = download(doc_id, "md", google_md)
        print(f"  {google_md.name}: {len(reference) / 1e6:.1f} MB (structure reference)")

    print("Converting with pandoc ...")
    media_root = args.work_dir / "media"
    markdown = convert(docx, media_root)
    markdown, promoted = promote_tab_titles(markdown, google_md.read_text(encoding="utf-8"))

    pics_dir = out_dir / "pics"
    if pics_dir.exists():
        shutil.rmtree(pics_dir)
    markdown, embeds, html_refs = rewrite_images(markdown, media_root, pics_dir, prefix)
    markdown = tidy(markdown)

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{args.slug}.md"
    target.write_text(markdown, encoding="utf-8", newline="\n")
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
    if HTML_TABLE.search(markdown):
        print(f"  note: {len(HTML_TABLE.findall(markdown))} tables remain as raw HTML (too complex for GFM)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
