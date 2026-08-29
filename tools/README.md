# tools

Two tools live here. `gdoc_import` brings the G5EC party log out of Google Docs
and cuts it into wiki notes; `autolink` turns names that already have a note
behind them into links. Each has its own README covering how to run it — this
document covers what they are for, what they hand to each other, the
conventions they all honour, and why the awkward decisions were made the way
they were.

Two rules hold across everything here:

- **Only the standard library.** The home machine is a Debian desktop where
  `python3` ships without pip and PEP 668 blocks system-wide installs, so
  anything that needs a virtual environment or `uv` is a tool that will not get
  run. `pandoc` is the single external program, installed once with the package
  manager and called as a subprocess.
- **Nothing touches `content/` by accident.** The import chain writes only into
  `build/`, which is disposable and ignored by git; moving the result into
  `content/` is a deliberate manual step. `autolink` is the one tool that edits
  notes in place, and it only previews unless `--apply` is given.

## The pipeline

```
Google Docs (the party log, 8 tabs)
      |
      |  gdoc_import/fetch_gdoc.py      download, convert, extract images
      v
build/out/partylog.md
build/out/partylog.tabs.json
build/out/pics/
      |
      |  gdoc_import/split_notes.py     one note per Google Docs tab
      v
build/notes/<tab>.md  (8)
build/notes/pics/
      |
      |  gdoc_import/split_sessions.py  the party log tab, one note per session
      v
build/sessions/Session<n> - <title>.md  (69)
build/sessions/pics/
      |
      |  (moved into content/ by hand, after review)
      v
content/G5eC/log/
      |
      |  autolink/autolink.py --apply   names become wikilinks
      v
content/G5eC/log/ with links
```

The steps are separate programs rather than one command because each one is
worth looking at before the next runs. The conversion is the only step that
touches the network, the two splitting steps are where the document structure
gets interpreted, and the linking step is the only one that changes notes that
are already published. Re-running any of them is safe: `build/` is rebuilt from
scratch, and linking is idempotent.

**The last step has to be last, every time.** A fresh split knows nothing about
the links, so copying `build/sessions/` over `content/G5eC/log/` silently throws
away every wikilink written there before. Run `autolink.py --apply` after each
such copy. Nothing is lost when you forget — the links are generated, so the
rerun puts all of them back — but the wiki goes flat in the meantime, and the
commit that does it looks like ordinary text edits.

## What each step hands over

**`fetch_gdoc.py`** downloads the document as `.docx` and converts it with
`pandoc --from=docx --to=gfm --wrap=none --extract-media`. It writes:

| artefact | contents |
| --- | --- |
| `build/raw/partylog.docx` | the download, kept so `--skip-download` can reuse it |
| `build/out/partylog.md` | the whole document, tab titles promoted to `h1` |
| `build/out/partylog.tabs.json` | `{"tabs": [...], "titles": [...]}` |
| `build/out/pics/` | every image, renamed after the section it appears in |

`tabs` is the tab titles in document order; `titles` is every `Title` styled
paragraph, including those that are not tab boundaries. The splitter needs both:
the first to know where to cut, the second to recognise a heading that merely
restates a name.

**`split_notes.py`** reads those two files and writes one note per tab into
`build/notes/`, copying `pics/` alongside. The tab title becomes the file name.

**`split_sessions.py`** reads `build/notes/G5EC party log.md` — the largest tab
— and cuts it again at every `## Session #N` heading into `build/sessions/`,
copying only the images those sessions actually embed.

**`autolink.py`** reads all of `content/` to learn what can be linked, and
writes only into the notes matched by `[scope]` in `autolink.ini`.

## Conventions

**Front matter.** Notes from the tab split carry `Category` and `tags`; session
notes add an `alias` per session number and the `Chapter` they belong to:

```yaml
---
Category: Log
tags:
  - G5eC
alias:
  - session1
  - session2
Chapter: Prológus
---
```

**File names.** `<>:"/\|?*[]#^` are removed, as are emoji and markdown emphasis.
The first set covers what Windows forbids in a path and what breaks an Obsidian
wikilink — `#` matters most, because every session heading has one. Session
notes are named `Session<numbers> - <title>`, with the numbers joined by `-`
when several sessions share a heading: `Session1-2 - A kiképzés.md`.

**Images.** Named `<slug>-<nearest preceding heading>-<n>.<ext>` and referenced
as Obsidian embeds, `![[name.png]]`. An image inside a raw HTML table stays an
`<img>` tag with only its `src` rewritten, because an embed would not render
inside an HTML block.

**Line breaks.** pandoc runs with `--wrap=none` and the splitter removes a blank
line standing between two ordinary lines. This suits Quartz, where the
`hard-line-breaks` plugin renders a single newline as a line break. Blank lines
around headings, quotes, tables, raw HTML, embeds and indented blocks are kept,
so no structure is altered.

## The decisions worth remembering

**Tab boundaries come from the `.docx`, not from Google's Markdown export.**
A Google Docs tab title is a `Title` styled paragraph that *also* starts a new
page and a new section; a `Title` used as a heading inside a tab has neither.
Nothing else separates them — not the style, not the font size, not the text.
The first attempt compared the `.docx` against Google's own Markdown export,
where tab titles come out as `h1`, but that promoted "Ki kicsoda a
történetemben?" to a tab of its own when it is really a heading on the
Szójegyzék tab. The export can still be fetched with `--google-md` for
eyeballing a conversion, but nothing depends on it.

**A tab restates its own name at the top of its page**, sometimes twice over, so
any `Title` line a tab opens with is dropped rather than duplicated in the body
under a file name that already says it.

**Sessions played in one sitting share a heading and stay in one note**, and
that note carries an alias for each of them. The same mechanism keeps the
spinoff sessions at `session22.5`. Numbers are not zero padded.

**Chapters became a property, not a heading.** `# Prológus` and `# Chapter N`
always sit directly in front of a session and carry no text of their own, so
they are recorded as `Chapter:` and dropped from the body. Note that the source
document labels two different runs of sessions "Chapter 2" — the tool copies
what is written rather than guessing, so 52 sessions currently share that value.

**Linking is exact and case sensitive, and Hungarian suffixes are never
guessed.** `Griff-házba` is left alone. Where an inflected form has to be
caught, the target note carries an alias for it; that keeps the rule in the wiki
where it can be seen, instead of in a stemming heuristic that would eventually
mangle something.

**The party members are excluded from linking.** Their six names account for
1322 of the matches, appearing in 54 to 65 of the 69 sessions. Linking them
would colour half the log without telling a reader anything.

**Headings are opt-in, and the tool proposes rather than decides.** Of several
hundred headings in the wiki, only a handful are ever mentioned by a session,
so `--scan` finds those and writes them into the config switched off. Enabling
one is a deliberate act. The heading is the link anchor but the phrase searched
for is the bare name, which is why an entry has two sides:
`Tori Sandro = Griff-ház#Tori Sandro (ezüst)`.

**Collector notes lose ties.** A collector only gathers what really lives
elsewhere, so when a name is claimed both by a collector and by an ordinary
note, the ordinary note wins. A name claimed by two ordinary notes is reported
and skipped rather than linked to an arbitrary one.

A note declares itself one with `Category: Collection` in its front matter,
which keeps the fact on the page instead of in a list that has to be kept in
step with a growing wiki: a new collector is right by writing the property, and
the reader sees it too. `[collectors]` in the config stays for the notes that
carry no front matter to say it in, and for overruling a page you disagree with.

**Links are never written into a raw HTML block.** Markdown is not processed
inside one, so the brackets would show up literally. The verse tables in the
party log, which were too complex for pandoc to render as Markdown, are exactly
such blocks — and the first run did link into one before this rule existed.

## Known rough edges

- `content/G5eC/log/G5EC party log.md` still holds the whole log, so every
  session's text is in the wiki twice. Kept on purpose for now.
- `content/G5eC/NPC/NPC.md` and `content/G5eC/NPC/Griff-ház.md` carry the same
  roster. The second is where the veteran headings are linked, and both are
  marked as collectors so neither claims a plain name.
- `tools/autolink/missing.md` lists 280 names the logs set in bold that no note
  claims — Orion, Arnulf, Mezuppi, Rogen and so on — plus 7 that a note already
  covers under a different spelling. That is a worklist, not a defect; regenerate
  it with `autolink.py --missing`.

## If you change these

- Keep them standard library only, and keep `pandoc` as the only external
  program.
- Keep the preview as the default and writing behind a flag.
- Keep `build/` disposable: every step should be safe to re-run from scratch.
- Prefer proposing over deciding. `--scan` exists because a tool guessing which
  headings matter would be wrong often enough to be untrustworthy, while a tool
  that lists the candidates is right every time.
- Verify by counting. The session split was checked by confirming that all 1091
  content lines of the party log land in exactly one session note, and the
  pandoc change was checked by confirming the output was byte for byte identical
  to the previous build. Both caught more than reading the diff would have.
