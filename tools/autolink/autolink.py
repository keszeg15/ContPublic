#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Turn known names into Obsidian wikilinks inside a chosen set of notes.

A phrase becomes a link when it matches a note file name, one of the aliases in
a note's front matter, or a heading listed in the configuration. Matching is
exact and case sensitive: the wiki carries an alias wherever an inflected form
has to be caught, so no attempt is made to guess Hungarian suffixes.

Nothing outside the configured scope is ever written to, and the run is a
preview unless --apply is given.

Only the standard library is used, so the script runs under a bare `python3`.
"""

from __future__ import annotations

import argparse
import configparser
import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_CONFIG = """\
# Which notes get links written into them, one pattern per line, relative to
# the content root.
[scope]
G5eC/log/Session*.md

# Notes that only gather what really lives elsewhere. When a name is claimed
# both by a collector and by an ordinary note, the ordinary note wins. A note
# saying `Category: Collection` in its front matter counts as one without being
# listed here; this section is for the ones that cannot say it themselves.
[collectors]
NPC

# Phrases that never become links, whoever claims them. The party members turn
# up in nearly every session, so linking them would colour half the log without
# telling the reader anything.
[exclude]
Harm
Alex
Arachis
Ryel
Ulrich
Joli

# Headings worth linking, written as `phrase = note#heading`. --scan proposes
# these with a leading # on the entry; delete that # to switch one on.
[headings]
"""

FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
ALIAS_BLOCK = re.compile(r"^(?:alias|aliases):[ \t]*\n((?:[ \t]+-[ \t]*.+\n?)+)", re.M)
ALIAS_ITEM = re.compile(r"^[ \t]+-[ \t]*(.+?)[ \t]*$", re.M)
CATEGORY = re.compile(r"^Category:[ \t]*(.+?)[ \t]*$", re.M)
COLLECTION = "Collection"
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.M)
FENCE = re.compile(r"^[ \t]*(```|~~~)")

# Markdown is not processed inside a raw HTML block, so a link written there
# would show up as literal brackets. The tables pandoc could not turn into GFM
# are exactly such blocks.
HTML_LINE = re.compile(r"^[ \t]*<")
HTML_OPEN = re.compile(r"^[ \t]*<(table|div|details|blockquote)\b", re.I)
HTML_CLOSE = re.compile(r"^[ \t]*</(table|div|details|blockquote)\b", re.I)
BOLD = re.compile(r"\*\*(.+?)\*\*")

# `**Hűvöskő**n` renders, `**[[Hűvöskő]]**n` does not: CommonMark only lets a
# `**` close when it is not both preceded by punctuation and followed by a
# letter, and the `]]` the link adds turns a working closing mark into a dead
# one, after which the bold bleeds into the rest of the line. Moving the mark
# past the suffix gives back a legal closing mark, and reads as the log meant
# it. A space before the suffix works too, which is why those cases look fine.
SUFFIXED_BOLD = re.compile(r"\*\*(!?\[\[[^\]]*\]\])\*\*(\w+)")

# Bold marks dates and whole emphasised sentences as well as names, and neither
# of those will ever become a note, so the missing-name report leaves them out.
MONTHS = "január|február|március|április|május|június|július|augusztus|szeptember|október|november|december"
DATED = re.compile(rf"(?:{MONTHS})|^\d", re.I)
TRIM = " \t*_\"'“”„.,:;!?"
MAX_NAME_WORDS = 5

# Folding away case and vowel length lets `Nartheá` and `Hüvöskő` meet the
# `Narthea` and `Hűvöskő` notes they are really inflections and typos of.
LONG_VOWELS = str.maketrans("áéíóúőű", "aeiouöü")

# Spans a link must never be written into: code, links and embeds that are
# already there, HTML tags, and bare URLs.
PROTECTED = re.compile(
    r"(`[^`]*`|!?\[\[[^\]]*\]\]|\[[^\]]*\]\([^)]*\)|<[^>]+>|https?://\S+)"
)

MIN_LENGTH = 3


def read_config(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(
        allow_no_value=True,
        delimiters=("=",),
        interpolation=None,
        comment_prefixes=("#",),
        inline_comment_prefixes=None,
    )
    parser.optionxform = str
    parser.read_string(DEFAULT_CONFIG)
    if path.exists():
        # utf-8-sig, because a Windows editor may leave a byte order mark, and a
        # mark in front of `[scope]` or of `---` hides the whole file's meaning.
        parser.read_string(path.read_text(encoding="utf-8-sig"))
    return parser


def section_keys(config: configparser.ConfigParser, name: str) -> list[str]:
    return [key for key in config[name]] if config.has_section(name) else []


def aliases_of(text: str) -> list[str]:
    matter = FRONT_MATTER.match(text)
    if not matter:
        return []
    found = []
    for block in ALIAS_BLOCK.finditer(matter.group(0)):
        found += [item.strip().strip('"').strip("'") for item in ALIAS_ITEM.findall(block.group(1))]
    return [alias for alias in found if alias]


def category_of(text: str) -> str:
    matter = FRONT_MATTER.match(text)
    if not matter:
        return ""
    found = CATEGORY.search(matter.group(0))
    return found.group(1).strip().strip('"').strip("'") if found else ""


def collectors_of(notes: dict[str, str], config: configparser.ConfigParser) -> set[str]:
    """Notes that only gather what really lives elsewhere.

    A note says so itself with `Category: Collection`, which keeps the fact where
    the page is rather than in a list that has to be kept in step with the wiki.
    The config still names the ones that carry no front matter to say it in.
    """
    named = set(section_keys(config, "collectors"))
    return named | {stem for stem, text in notes.items() if category_of(text) == COLLECTION}


def collect_targets(
    notes: dict[str, str], config: configparser.ConfigParser
) -> tuple[dict[str, str], list[str]]:
    """Map every linkable phrase to the note, or note#heading, it points at."""
    collectors = collectors_of(notes, config)
    excluded = set(section_keys(config, "exclude"))

    claims: dict[str, list[str]] = {}
    for stem, text in notes.items():
        for phrase in [stem] + aliases_of(text):
            claims.setdefault(phrase, []).append(stem)

    targets: dict[str, str] = {}
    ambiguous: list[str] = []
    for phrase, owners in claims.items():
        if phrase in excluded or len(phrase) < MIN_LENGTH:
            continue
        preferred = [owner for owner in owners if owner not in collectors] or owners
        if len(set(preferred)) > 1:
            ambiguous.append(f"{phrase} -> {', '.join(sorted(set(preferred)))}")
            continue
        targets[phrase] = preferred[0]

    for phrase, target in config["headings"].items():
        if phrase in excluded or not target:
            continue
        targets[phrase] = target.strip()

    return targets, sorted(ambiguous)


def walk_body(text: str) -> tuple[str, list[tuple[str, bool]]]:
    """Split a note into its front matter and its lines, flagging the linkable ones.

    A link is never written into a heading, a fenced code block or a raw HTML
    block, and those are the same lines that are not worth searching either, so
    both passes work from this.
    """
    matter = FRONT_MATTER.match(text)
    head = matter.group(0) if matter else ""
    lines: list[tuple[str, bool]] = []
    fenced = False
    html_depth = 0
    for line in text[len(head):].split("\n"):
        if FENCE.match(line):
            fenced = not fenced
            lines.append((line, False))
            continue
        if HTML_CLOSE.match(line):
            html_depth = max(0, html_depth - 1)
            lines.append((line, False))
            continue
        if HTML_OPEN.match(line):
            html_depth += 1
            lines.append((line, False))
            continue
        blocked = fenced or html_depth or line.startswith("#") or HTML_LINE.match(line)
        lines.append((line, not blocked))
    return head, lines


def linkable_text(text: str) -> str:
    _, lines = walk_body(text)
    return "\n".join(line for line, linkable in lines if linkable)


def build_pattern(phrases: list[str]) -> re.Pattern:
    # Longest first, so `Tori Sandro` wins over a shorter phrase inside it.
    ordered = sorted(phrases, key=len, reverse=True)
    body = "|".join(re.escape(phrase) for phrase in ordered)
    return re.compile(rf"(?<!\w)(?:{body})(?!\w)")


def linkify(text: str, pattern: re.Pattern, targets: dict[str, str], stem: str) -> tuple[str, Counter, int]:
    """Rewrite the body of one note, leaving its structure alone.

    Emphasis is mended afterwards rather than during the substitution, because
    the damage is only visible once the link is in place, and this way a rerun
    also repairs the notes written before the fix existed.
    """
    counts: Counter = Counter()

    def replace(match: re.Match) -> str:
        phrase = match.group(0)
        target = targets[phrase]
        if target.split("#")[0] == stem:
            return phrase
        counts[phrase] += 1
        return f"[[{target}]]" if target == phrase else f"[[{target}|{phrase}]]"

    head, lines = walk_body(text)
    rewritten = []
    mended = 0
    for line, is_linkable in lines:
        if is_linkable:
            parts = PROTECTED.split(line)
            for position in range(0, len(parts), 2):
                parts[position] = pattern.sub(replace, parts[position])
            line, fixed = SUFFIXED_BOLD.subn(r"**\1\2**", "".join(parts))
            mended += fixed
        rewritten.append(line)

    return head + "\n".join(rewritten), counts, mended


def heading_phrase(bare: str) -> str:
    """The name to look for inside a heading that also carries a description.

    The heading stays the link anchor; this is only what is searched for in the
    logs, which write `Tori Sandro`, never `Tori Sandro (ezüst)`, and `Ordo`,
    never `Ordo, kikötőmester`.
    """
    phrase = re.sub(r"<[^>]+>", "", bare)
    phrase = re.sub(r"\s*\([^)]*\)", "", phrase).split(",")[0]
    return phrase.strip().rstrip(":;.")


def scan_headings(
    notes: dict[str, str], scope: dict[str, str], config: configparser.ConfigParser, raw: str
) -> list[tuple[str, str, int, int]]:
    """Propose headings that the notes in scope actually mention."""
    collectors = collectors_of(notes, config)
    excluded = set(section_keys(config, "exclude"))
    bodies = [linkable_text(text) for text in scope.values()]

    # A heading entry overrides a plain name, so proposing one for a phrase a
    # note already answers to would quietly demote that note. `Griff-ház` is the
    # cautionary case: it is an alias of the guild page and also a heading on the
    # ten line roster, and enabling it would send all 36 mentions to the roster.
    claimed = set(notes) | {alias for text in notes.values() for alias in aliases_of(text)}

    best: dict[str, tuple[str, int, int]] = {}
    for stem, text in notes.items():
        if stem in scope:
            continue
        for _, title in HEADING.findall(FRONT_MATTER.sub("", text)):
            if "[[" in title:
                # Already points somewhere, and the brackets would make the
                # anchor unreachable anyway.
                continue
            bare = re.sub(r"[*_`]", "", title).strip()
            phrase = heading_phrase(bare)
            if len(phrase) < 4 or phrase in excluded or phrase in claimed:
                continue
            if re.search(rf"^#?[ \t]*{re.escape(phrase)}[ \t]*=", raw, re.M):
                continue
            pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)")
            total = sum(len(pattern.findall(body)) for body in bodies)
            if not total:
                continue
            seen = sum(1 for body in bodies if pattern.search(body))
            candidate = (f"{stem}#{bare}", total, seen)
            if phrase not in best or (stem not in collectors and best[phrase][0].split("#")[0] in collectors):
                best[phrase] = candidate

    rows = [(phrase, target, total, seen) for phrase, (target, total, seen) in best.items()]
    rows.sort(key=lambda row: (-row[2], row[0]))
    return rows


def fold(phrase: str) -> str:
    return phrase.casefold().translate(LONG_VOWELS)


def looks_like_a_name(phrase: str) -> bool:
    if not phrase or DATED.search(phrase):
        return False
    return len(phrase.split()) <= MAX_NAME_WORDS and phrase[0].isupper()


def collect_missing(
    scope: dict[str, str], targets: dict[str, str], config: configparser.ConfigParser
) -> tuple[list[tuple], list[tuple]]:
    """Gather the bold names that want a note, apart from those that want an alias."""
    excluded = {fold(phrase) for phrase in section_keys(config, "exclude")}
    known = {fold(phrase): target for phrase, target in targets.items()}

    groups: dict[str, Counter] = {}
    for text in scope.values():
        for span in BOLD.findall(linkable_text(text)):
            phrase = re.sub(r"\s+", " ", span).strip(TRIM)
            if len(phrase) <= MIN_LENGTH or phrase in targets or "[[" in phrase:
                continue
            if fold(phrase) in excluded or not looks_like_a_name(phrase):
                continue
            groups.setdefault(fold(phrase), Counter())[phrase] += 1

    spelt, unknown = [], []
    for key, variants in groups.items():
        row = (sum(variants.values()), variants.most_common(1)[0][0], sorted(variants), known.get(key))
        (spelt if key in known else unknown).append(row)
    spelt.sort(key=lambda row: (-row[0], row[1]))
    unknown.sort(key=lambda row: (-row[0], row[1]))
    return spelt, unknown


def format_missing(spelt: list[tuple], unknown: list[tuple]) -> list[str]:
    """Write the worklist as Markdown, without a timestamp, so a rerun only
    changes the file when the logs changed."""
    lines = [
        "# Bold names the wiki does not cover",
        "",
        "The party log sets in bold what it holds notable, so this is a worklist of",
        "notes still to be written. Regenerate it with `python3 autolink.py --missing`.",
        "",
        "Dates, emphasised sentences and the party members under `[exclude]` are left",
        "out, and spellings that differ only in case or vowel length are counted as one",
        "name, with the rarer forms in brackets.",
        "",
        f"## {len(spelt)} already have a note and are only spelt differently",
        "",
        "An alias on the note listed here is the whole fix.",
        "",
    ]
    lines += [f"- **{' / '.join(variants)}** — {total}× — alias on `{target}`" for total, _, variants, target in spelt]

    repeated = [row for row in unknown if row[0] > 1]
    once = [row for row in unknown if row[0] == 1]
    lines += ["", f"## {len(unknown)} have nothing behind them, {sum(row[0] for row in unknown)} occurrences", ""]
    for total, surface, variants, _ in repeated:
        others = [variant for variant in variants if variant != surface]
        lines.append(f"- **{surface}** — {total}×" + (f" ({', '.join(others)})" if others else ""))
    if once:
        lines += ["", f"### {len(once)} of them turn up once", "", ", ".join(row[1] for row in once)]
    return lines


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, default=script_dir.parents[1] / "content", help="content root")
    parser.add_argument("--config", type=Path, default=script_dir / "autolink.ini", help="configuration file")
    parser.add_argument("--apply", action="store_true", help="write the links, instead of only reporting them")
    parser.add_argument("--scan", action="store_true", help="propose headings worth linking")
    parser.add_argument("--missing", action="store_true", help="list bold names that no note or heading claims")
    parser.add_argument("--report", type=Path, default=script_dir / "missing.md", help="where --missing is written")
    args = parser.parse_args()

    if not args.content.is_dir():
        raise SystemExit(f"No content directory at {args.content}")

    config = read_config(args.config)
    raw = args.config.read_text(encoding="utf-8-sig") if args.config.exists() else ""

    notes = {path.stem: path.read_text(encoding="utf-8-sig", errors="replace") for path in args.content.rglob("*.md")}
    scope_paths: list[Path] = []
    for pattern in section_keys(config, "scope"):
        scope_paths += sorted(args.content.glob(pattern))
    scope = {path.stem: notes[path.stem] for path in scope_paths}

    print(f"{len(notes)} notes, {len(scope)} of them in scope")
    if not scope:
        raise SystemExit("The [scope] patterns matched nothing.")

    if args.scan:
        rows = scan_headings(notes, scope, config, raw)
        print(f"{len(rows)} headings are mentioned in the notes in scope and are not in the config yet\n")
        block = "\n".join(
            f"# {total} occurrences in {seen} notes\n#{phrase} = {target}" for phrase, target, total, seen in rows
        )
        if not args.config.exists():
            args.config.write_text(DEFAULT_CONFIG + block + "\n", encoding="utf-8", newline="\n")
            print(f"Wrote {args.config}. Every heading is off; delete the leading # on the ones you want.")
        else:
            print(block if block else "(nothing new)")
            print(f"\nPaste the entries you want under [headings] in {args.config.name}, without the leading #.")
        return 0

    targets, ambiguous = collect_targets(notes, config)
    print(f"{len(targets)} phrases can be linked, from names, aliases and {len(config['headings'])} configured headings")
    collectors = collectors_of(notes, config)
    tagged = sum(1 for stem in collectors if category_of(notes.get(stem, "")) == COLLECTION)
    print(f"  {len(collectors)} notes lose name ties as collectors, {tagged} of them by their own Category")
    if ambiguous:
        print(f"  {len(ambiguous)} phrases are claimed by several notes and are skipped:")
        for entry in ambiguous[:10]:
            print(f"    {entry}")

    pattern = build_pattern(list(targets))
    totals: Counter = Counter()
    changed = 0
    mended = 0
    for path in scope_paths:
        text = notes[path.stem]
        linked, counts, fixed = linkify(text, pattern, targets, path.stem)
        if linked == text:
            continue
        changed += 1
        totals.update(counts)
        mended += fixed
        if args.apply:
            path.write_text(linked, encoding="utf-8", newline="\n")

    verb = "Wrote" if args.apply else "Would write"
    print(f"\n{verb} {sum(totals.values())} links across {changed} notes, {len(totals)} distinct phrases")
    if mended:
        moved = "Moved" if args.apply else "Would move"
        print(f"{moved} {mended} closing ** past the suffix that follows a link, so the bold renders again")
    print(f"\n{'phrase':<34} {'links':>6}  target")
    print("-" * 84)
    for phrase, count in totals.most_common(25):
        print(f"{phrase[:33]:<34} {count:>6}  {targets[phrase][:40]}")

    if args.missing:
        report = format_missing(*collect_missing(scope, targets, config))
        args.report.write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
        print("\n" + "\n".join(report))
        print(f"\nWritten to {args.report}")

    if not args.apply:
        print("\nThis was a preview. Add --apply to write the links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
