# autolink

Writes Obsidian wikilinks into a chosen set of notes, so that a name already
covered elsewhere in the wiki becomes a link wherever it is mentioned.

[../README.md](../README.md) covers how this fits into the wider pipeline, and
why the awkward parts work the way they do.

## Running it

```bash
python3 autolink.py            # preview only
python3 autolink.py --apply    # write the links
```

Only the standard library is used, and only the notes matched by `[scope]` are
ever written to. Running it twice changes nothing, because a link that is
already there is left alone.

## The two roots

What can be linked and what gets written are looked up separately. The first is
always the whole wiki under `--content`; the second is `[scope]` under
`--scope-root`, which is the same place unless told otherwise:

```bash
python3 autolink.py --apply --scope-root ../gdoc_import/build/sessions
```

That links a freshly split log while it is still in `build/`, so the copy into
`content/` brings the links with it instead of flattening the ones already
there. The notes being written need not be part of the wiki yet; they only need
the wiki to point at.

Because the two roots hold the sessions at different depths, `[scope]` lists
both spellings — `G5eC/log/Session*.md` and `Session*.md`. Only one can match
under a given root, and a pattern matching nothing costs nothing.

## Where the links come from

Three sources, folded into one `phrase -> target` table:

| source | example |
| --- | --- |
| note file name | `Callindal` becomes `[[Callindal]]` |
| `alias` in the front matter | `Piscaro` becomes `[[Piskaro\|Piscaro]]` |
| a heading listed in `autolink.ini` | `Kozma` becomes `[[Griff-ház#Kozma (bronz)\|Kozma]]` |

Matching is exact and case sensitive. Hungarian suffixes are deliberately not
guessed: `Griff-házba` is left alone, and where an inflected form has to be
caught, the note carries an alias for it.

## Choosing the headings

The wiki has hundreds of headings and listing the useful ones by hand would be
tedious, so `--scan` narrows it down:

```bash
python3 autolink.py --scan
```

It reports every heading that the notes in scope actually mention — a handful,
rather than the hundreds that exist — and writes them into `autolink.ini`
switched off. Delete the leading `#` on the ones worth linking. Run it again
later and only what is new is listed, so a heading added afterwards does not go
unnoticed.

The heading is the link anchor, but the phrase searched for is the bare name:
`### Tori Sandro (ezüst)` appears as `Tori Sandro` in a log, so the entry reads
`Tori Sandro = Griff-ház#Tori Sandro (ezüst)`. A heading often carries a
description alongside the name, so the phrase also drops HTML tags, anything
after the first comma and a trailing `:`, which is how `##### Ordo, kikötőmester`
is found by the `Ordo` a log actually writes.

Every level from `#` to `######` is read. Two kinds of heading are passed over:
one that already contains a wikilink, since it points somewhere else and its
brackets would make the anchor unreachable, and one whose name a note or an
alias already answers to. The second matters because a heading entry overrides a
plain name, so proposing `Griff-ház = NPC#Griff-ház` would quietly send all 36
mentions of the guild to the ten line roster instead of the guild's own page.

## Configuration

`autolink.ini` holds four sections:

| section | meaning |
| --- | --- |
| `[scope]` | which notes get links written into them, as patterns under the scope root |
| `[collectors]` | further notes that only gather what really lives elsewhere |
| `[exclude]` | phrases that never become links, whoever claims them |
| `[headings]` | the headings chosen above |

A name claimed by two ordinary notes is reported and skipped rather than linked
to an arbitrary one of them.

## Collectors

Some notes only gather what really lives elsewhere — a roster, an index, a list
of guilds. When a name is claimed both by such a note and by an ordinary one,
the ordinary note wins, so a mention of a guild lands on the guild's own page
rather than on the line about it in a roster.

A note says it is one itself:

```yaml
---
Category: Collection
---
```

That keeps the fact on the page rather than in a list that has to be kept in
step with the wiki, and a new collector is handled the moment it is written.
`[collectors]` in the config is for the notes with no front matter to say it in,
and for overruling a page whose own claim you disagree with. Every run prints
how many collectors it found and how many of them said so themselves.

## What is left alone

Front matter, headings, fenced and inline code, links and embeds that are
already there, HTML tags and bare URLs.

Raw HTML blocks are skipped whole, because Markdown is not processed inside
one: a link written there would show up as literal brackets. The verse tables
in the party log, which were too complex for pandoc to turn into Markdown, are
exactly such blocks.

## Bold with a suffix hanging off it

The log often bolds a name and leaves the Hungarian suffix outside the mark, as
in `**Hűvöskő**n`. That renders, but `**[[Hűvöskő]]**n` does not: Markdown
refuses to close emphasis on a `**` that is both preceded by punctuation and
followed by a letter, and the `]]` the link brings turns a working closing mark
into a dead one, after which the bold bleeds into the rest of the line.

So after linking a line, the closing mark is moved past the suffix and
`**[[Hűvöskő]]n**` is written instead. Only the unambiguous shape is touched,
where the opening `**` sits directly in front of the link, so a `**` that opens
a span just after a link is never mistaken for one that closes. A suffix
separated by a space or a hyphen needs no help and is left alone.

The repair runs on every note in scope, not only the ones being linked, so a
rerun also mends notes written before this existed.

## Notes that do not exist yet

```bash
python3 autolink.py --missing
```

writes [missing.md](missing.md) next to this file and prints the same thing, so
the worklist can be read in the repository without running anything. It lists
the names the logs set in bold that no note and no heading claims, and since the
log bolds what it considers notable, this doubles as a worklist of the notes
still to be written. The report carries no timestamp, so a rerun only shows up
as a change when the logs or the wiki did.

The report answers in two parts. The first is the cheap half: names that do have
a note and are only spelt differently, where an alias on the existing note is
the whole fix. `Nartheá` is Narthea with a suffix, `Hüvöskő` is a typo for
Hűvöskő, and the report finds both by ignoring case and vowel length. The second
part is the names that genuinely have nothing behind them, most frequent first,
with the one-off names gathered into a single line at the end.

Bold is not used for names only, so three kinds of entry are dropped before
counting: dates, which the log sets in bold on every session heading; anything
longer than five words or starting with a lower-case letter, which is an
emphasised sentence rather than a name; and the phrases under `[exclude]`, which
are not missing, only deliberately unlinked.
