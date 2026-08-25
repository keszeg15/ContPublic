#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Split the converted Google Doc into one wiki note per Google Docs tab.

Reads the output of fetch_gdoc.py and writes a note per tab, each with the
front matter Quartz expects, plus a shared image folder. Nothing is written
into content/ -- the notes are staged so they can be reviewed and moved by
hand.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

CATEGORY = "Log"
TAGS = ["G5eC"]

# Characters Windows forbids in file names, plus the ones that would confuse
# Obsidian's wikilink syntax.
ILLEGAL = re.compile(r'[<>:"/\\|?*\[\]#^]')

# A blank line between two ordinary lines is collapsed. Headings, quotes,
# tables, raw HTML, image embeds and indented blocks keep their spacing, so the
# document structure is never altered.
KEEPS_SPACING = r"[^\s#>|<!]"
COLLAPSE_BLANKS = re.compile(rf"(?m)^({KEEPS_SPACING}[^\n]*)\n\n(?={KEEPS_SPACING})")


def safe_name(title: str) -> str:
    name = ILLEGAL.sub("", title)
    name = re.sub(r"\s+", " ", name).strip().strip(".")
    return name or "untitled"


def front_matter() -> str:
    tags = "\n".join(f"  - {tag}" for tag in TAGS)
    return f"---\nCategory: {CATEGORY}\ntags:\n{tags}\n---\n"


def collapse_blank_lines(text: str) -> tuple[str, int]:
    collapsed, count = COLLAPSE_BLANKS.subn(r"\1\n", text)
    return collapsed, count


def normalise(text: str) -> str:
    text = re.sub(r"\{#[^}]*\}", "", text)
    text = re.sub(r"\\(.)", r"\1", text)
    text = re.sub(r"[*_`]", "", text)
    return " ".join(text.split())


def strip_leading_titles(body: list[str], titles: set[str]) -> list[str]:
    """Drop the title lines a tab opens with.

    A tab usually restates its own name at the top of the page, sometimes twice
    over -- once as the tab title and once as a visible heading -- and the file
    name already carries it. Any other `Title` styled line in that opening run
    is dropped too, which is what removes a decorative cover heading.
    """
    index = 0
    while index < len(body):
        line = body[index].strip()
        if not line:
            index += 1
            continue
        if normalise(line.lstrip("#").strip()) not in titles:
            break
        index += 1
    return body[index:]


def split_tabs(markdown: str, tab_titles: list[str], titles: set[str]) -> list[tuple[str, str]]:
    """Cut the document at each tab title heading.

    The first tab has no heading of its own -- pandoc consumes it as the
    document title -- so it is seeded as starting at the top of the document.
    """
    lines = markdown.split("\n")
    pending = list(tab_titles[1:])
    boundaries: list[tuple[int, str]] = [(0, tab_titles[0])]

    for index, line in enumerate(lines):
        if not line.startswith("# "):
            continue
        title = normalise(line[2:])
        if pending and title == pending[0]:
            boundaries.append((index, title))
            pending.pop(0)

    if pending:
        raise SystemExit(f"Could not locate these tabs in the document: {', '.join(pending)}")

    sections = []
    for position, (start, title) in enumerate(boundaries):
        end = boundaries[position + 1][0] if position + 1 < len(boundaries) else len(lines)
        body = strip_leading_titles(lines[start:end], titles)
        sections.append((title, "\n".join(body).strip()))
    return sections


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", default="partylog", help="base name used by fetch_gdoc.py")
    parser.add_argument("--work-dir", type=Path, default=script_dir / "build", help="staging directory")
    parser.add_argument("--out-dir", type=Path, default=None, help="where to write the notes")
    args = parser.parse_args()

    source_dir = args.work_dir / "out"
    markdown_file = source_dir / f"{args.slug}.md"
    tabs_file = source_dir / f"{args.slug}.tabs.json"
    out_dir = args.out_dir or args.work_dir / "notes"

    for required in (markdown_file, tabs_file):
        if not required.exists():
            raise SystemExit(f"Missing {required}. Run fetch_gdoc.py first.")

    markdown = markdown_file.read_text(encoding="utf-8")
    recorded = json.loads(tabs_file.read_text(encoding="utf-8"))
    titles = {normalise(title) for title in recorded["titles"]}
    sections = split_tabs(markdown, [normalise(tab) for tab in recorded["tabs"]], titles)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    total_collapsed = 0
    written = 0
    print(f"{'note':<34} {'kB':>6} {'lines':>7} {'collapsed':>10}")
    print("-" * 62)
    for title, body in sections:
        if not body.strip():
            print(f"{safe_name(title)[:33]:<34} {'':>6} {'':>7} {'skipped (empty tab)':>10}")
            continue
        body, collapsed = collapse_blank_lines(body)
        total_collapsed += collapsed
        text = front_matter() + body.strip() + "\n"
        target = out_dir / f"{safe_name(title)}.md"
        target.write_text(text, encoding="utf-8", newline="\n")
        written += 1
        print(f"{target.stem[:33]:<34} {len(text) / 1000:>6.1f} {text.count(chr(10)):>7} {collapsed:>10}")

    pics = source_dir / "pics"
    if pics.is_dir():
        shutil.copytree(pics, out_dir / "pics")
        print(f"\nCopied {len(list(pics.iterdir()))} images into {out_dir / 'pics'}")

    print(f"Wrote {written} notes to {out_dir}, removed {total_collapsed} blank lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
