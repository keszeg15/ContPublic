# autolink

Writes Obsidian wikilinks into a chosen set of notes, so that a name already
covered elsewhere in the wiki becomes a link wherever it is mentioned.

## Running it

```bash
python3 autolink.py            # preview only
python3 autolink.py --apply    # write the links
```

Only the standard library is used, and only the notes matched by `[scope]` are
ever written to. Running it twice changes nothing, because a link that is
already there is left alone.

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
`Tori Sandro = Griff-ház#Tori Sandro (ezüst)`.

## Configuration

`autolink.ini` holds four sections:

| section | meaning |
| --- | --- |
| `[scope]` | which notes get links written into them, as patterns under the content root |
| `[collectors]` | notes that only gather what really lives elsewhere; when a name is claimed both by a collector and by an ordinary note, the ordinary note wins |
| `[exclude]` | phrases that never become links, whoever claims them |
| `[headings]` | the headings chosen above |

A name claimed by two ordinary notes is reported and skipped rather than linked
to an arbitrary one of them.

## What is left alone

Front matter, headings, fenced and inline code, links and embeds that are
already there, HTML tags and bare URLs.

Raw HTML blocks are skipped whole, because Markdown is not processed inside
one: a link written there would show up as literal brackets. The verse tables
in the party log, which were too complex for pandoc to turn into Markdown, are
exactly such blocks.

## Notes that do not exist yet

```bash
python3 autolink.py --missing
```

lists the names the logs set in bold that no note and no heading claims. Since
the log bolds what it considers notable, this doubles as a worklist of the
notes still to be written.
