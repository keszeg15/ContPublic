#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Split the party log note into one note per session.

Reads the note written by split_notes.py and cuts it at every session heading.
Sessions that were played together share a heading, and therefore a note. The
chapter the session belongs to is carried over into the front matter, since the
chapter headings themselves are dropped.

Only the standard library is used, so the script runs under a bare `python3`.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

CATEGORY = "Log"
TAGS = ["G5eC"]

# Characters Windows forbids in file names, plus the ones that would confuse
# Obsidian's wikilink syntax. `#` matters here: every session heading has one.
ILLEGAL = re.compile(r'[<>:"/\\|?*\[\]#^]')

# Emoji are fine in a heading but make for unwieldy file names and URLs.
EMOJI = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\u2b00-\u2bff\ufe0f]")

SESSION_HEADING = re.compile(r"^##[ \t]+Session\b(?P<rest>.*)$")
CHAPTER_HEADING = re.compile(r"^#[ \t]+(?P<name>.+?)[ \t]*$")

# The numbers a session heading opens with: a single one, a decimal for the
# spinoffs, or a range when several sessions were played in one sitting. Google
# Docs writes them as `#12`, which pandoc escapes to `\#12`.
SESSION_NUMBERS = re.compile(
    r"^[ \t]*(?P<numbers>#?\d+(?:\.\d+)?(?:[ \t]*[-\u2013\u2014][ \t]*#?\d+(?:\.\d+)?)*)"
    r"(?::[ \t]*|[ \t]+)(?P<title>.*)$"
)

FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
EMBED = re.compile(r"!\[\[(?P<name>[^\]]+)\]\]")


def unescape(text: str) -> str:
    return re.sub(r"\\(.)", r"\1", text)


def safe_name(text: str) -> str:
    text = EMOJI.sub("", ILLEGAL.sub("", re.sub(r"[*_`]", "", unescape(text))))
    return re.sub(r"\s+", " ", text).strip().strip(".")


def front_matter(aliases: list[str], chapter: str | None) -> str:
    lines = ["---", f"Category: {CATEGORY}", "tags:"]
    lines += [f"  - {tag}" for tag in TAGS]
    lines.append("alias:")
    lines += [f"  - {alias}" for alias in aliases]
    if chapter:
        lines.append(f"Chapter: {chapter}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def parse_heading(rest: str) -> tuple[list[str], str]:
    """Pull the session numbers and the title out of a session heading."""
    match = SESSION_NUMBERS.match(unescape(rest))
    if not match:
        raise SystemExit(f"Could not read the session number from: Session{rest}")
    numbers = re.findall(r"\d+(?:\.\d+)?", match.group("numbers"))
    return numbers, match.group("title")


def split_sessions(markdown: str) -> tuple[list[dict], list[str]]:
    """Cut the note at every session heading, tracking the enclosing chapter.

    A chapter heading always sits directly in front of a session, so it opens
    the section that follows it rather than closing the one before.
    """
    sections: list[dict] = []
    notes: list[str] = []
    chapter: str | None = None
    current: dict | None = None
    between: list[str] = []

    for line in FRONT_MATTER.sub("", markdown).split("\n"):
        session = SESSION_HEADING.match(line)
        if session:
            numbers, title = parse_heading(session.group("rest"))
            # pandoc leaves an empty list item behind where a chapter heading
            # had one, so only real text is worth carrying over.
            lead = between if any(entry.strip(" -") for entry in between) else []
            if lead:
                notes.append(f"Session {'-'.join(numbers)} opens with {len(lead)} line(s) from its chapter heading")
            current = {
                "numbers": numbers,
                "title": title,
                "chapter": chapter,
                "body": [f"# {line.lstrip('#').strip()}"] + lead,
            }
            sections.append(current)
            between = []
            continue

        heading = CHAPTER_HEADING.match(line)
        if heading:
            chapter = safe_name(heading.group("name"))
            between = []
            current = None
            continue

        (between if current is None else current["body"]).append(line)

    return sections, notes


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--note",
        type=Path,
        default=script_dir / "build" / "notes" / "G5EC party log.md",
        help="the party log note written by split_notes.py",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=script_dir / "build" / "sessions",
        help="where to write the per-session notes",
    )
    args = parser.parse_args()

    if not args.note.exists():
        raise SystemExit(f"Missing {args.note}. Run split_notes.py first.")

    sections, notes = split_sessions(args.note.read_text(encoding="utf-8"))
    if not sections:
        raise SystemExit(f"No session headings found in {args.note}")

    if args.out_dir.exists():
        shutil.rmtree(args.out_dir)
    args.out_dir.mkdir(parents=True)

    print(f"{'note':<58} {'kB':>5} {'alias':>18}  chapter")
    print("-" * 104)
    embedded: set[str] = set()
    for section in sections:
        numbers = section["numbers"]
        title = safe_name(section["title"])
        stem = f"Session{'-'.join(numbers)}"
        if title:
            stem = f"{stem} - {title}"
        aliases = [f"session{number}" for number in numbers]

        heading, *rest = section["body"]
        body = f"{heading}\n\n" + "\n".join(rest).strip() + "\n"
        embedded.update(match.group("name") for match in EMBED.finditer(body))
        text = front_matter(aliases, section["chapter"]) + body
        (args.out_dir / f"{stem}.md").write_text(text, encoding="utf-8", newline="\n")
        print(f"{stem[:57]:<58} {len(text) / 1000:>5.1f} {', '.join(aliases):>18}  {section['chapter'] or '-'}")

    pics = args.note.parent / "pics"
    copied = 0
    if embedded and pics.is_dir():
        (args.out_dir / "pics").mkdir()
        for name in sorted(embedded):
            source = pics / name
            if source.exists():
                shutil.copy2(source, args.out_dir / "pics" / name)
                copied += 1
            else:
                notes.append(f"embedded image not found: {name}")

    chapters: dict[str, int] = {}
    for section in sections:
        chapters[section["chapter"] or "-"] = chapters.get(section["chapter"] or "-", 0) + 1

    print(f"\nWrote {len(sections)} notes to {args.out_dir}, {copied} images alongside them")
    print("  chapters: " + ", ".join(f"{name} ({count})" for name, count in chapters.items()))
    for note in notes:
        print(f"  note: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
