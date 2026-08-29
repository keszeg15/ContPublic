# gdoc_import

Fetches a Google Doc and converts it into Quartz-flavoured Markdown, ready to be
split into individual wiki notes.

[../README.md](../README.md) covers how this fits into the wider pipeline, and
why the awkward parts work the way they do.

Both scripts use nothing but the standard library, so there is no virtual
environment and no pip to deal with:

```bash
python3 fetch_gdoc.py
python3 split_notes.py
```

The one thing that has to be installed is pandoc itself, which does the docx to
Markdown conversion:

```bash
sudo apt install pandoc              # or: brew install pandoc
```

Calling the `pandoc` command rather than a wrapper library is what keeps the
dependency list empty. A wrapper such as `pypandoc-binary` would carry the
pandoc binary along, but then the script could no longer be started with a
plain `python3`, which is awkward on Debian and Ubuntu: they ship `python3`
without pip and refuse system-wide installs (PEP 668).

Useful flags:

| Flag | Purpose |
| --- | --- |
| `--doc-id` | Document id or full Google Docs URL. Defaults to the G5EC party log. |
| `--slug` | Base name for the generated files. Defaults to `partylog`. |
| `--skip-download` | Reuse the cached export instead of hitting the network. |
| `--google-md` | Also fetch Google's own Markdown export, to compare against. |
| `--work-dir` | Where to stage the output. Defaults to `build/`. |

## Splitting into notes

`split_notes.py` turns the converted document into one note per Google Docs
tab, adds the front matter and tightens the spacing.

Each note gets `Category: Log` and `tags: [G5eC]`, and the tab title becomes the
file name. A tab tends to restate its own name at the top of the page, sometimes
twice over, so any `Title` styled line the tab opens with is dropped rather than
duplicating the file name in the body.

A blank line between two ordinary lines is also removed. Headings, quotes,
tables, raw HTML, image embeds and indented blocks keep their spacing, so the
structure is never altered. This suits Quartz, where the `hard-line-breaks`
plugin renders a single newline as a line break.

## Splitting into sessions

The party log tab is one long note of its own, so `split_sessions.py` cuts it
again, this time at every `Session #N` heading:

```bash
python3 split_sessions.py
```

The heading becomes the file name, minus the characters that would break a
wikilink or a Windows path — `#`, `:` and `?` among them, plus the odd emoji —
so `Session #4: Mezuppi nyomában` is written to `Session4 - Mezuppi
nyomában.md`. The heading itself stays at the top of the note as an `h1`.

Sessions that were played in one sitting share a heading, and stay in a single
note. Such a note gets an alias per session (`session1`, `session2`), which is
also how the spinoffs keep their `session22.5` form. A heading below the session
level, like the verses in the log, belongs to the session it sits in and is left
alone.

Alongside `Category` and `tags`, each note records the `Chapter` it belongs to.
The `# Prológus` and `# Chapter N` headings are dropped from the body, since
they carried no text of their own — they only marked where a chapter began.

## Output

```
build/
  raw/partylog.docx        downloaded source
  raw/partylog.google.md   Google's own export, used as a structure reference
  out/partylog.md          converted Markdown
  out/partylog.tabs.json   the tab titles, consumed by split_notes.py
  out/pics/*.png|jpg       extracted images
  notes/*.md               one note per tab
  notes/pics/              the same images, alongside the notes
  sessions/*.md            the party log tab, one note per session
  sessions/pics/           the images those sessions embed
```

Nothing is written into `content/` — that happens in the splitting step, so the
staging directory can be deleted and regenerated at any time.

## Notes

The document has to be shared as "anyone with the link"; that is what lets the
export endpoint work without authentication. If sharing is revoked, Google
answers with an HTML login page under a 200 status, which the script detects by
checking the `.docx` magic bytes.

The document is split into Google Docs tabs, and the export concatenates them
all into one file — the `tab=` URL parameter is ignored, so a tab cannot be
fetched on its own. pandoc renders each tab title as an ordinary paragraph,
which is why the tabs have to be found in the `.docx` itself: Google gives a
tab title a `Title` styled paragraph that also starts a new page and a new
section, whereas a `Title` used as a heading inside a tab has neither. Style
alone is not enough to tell them apart, and neither is font size, since both
vary between tabs.

Google's own Markdown export can be fetched with `--google-md`. It is not used
for anything, but it renders the structure differently and is handy for
double-checking the conversion by hand.

Images are renamed after the section they appear in and referenced as Obsidian
embeds (`![[name.png]]`), matching the convention used elsewhere in `content/`.
Images that sit inside a table stay as `<img>` tags, because an embed would not
be rendered inside a raw HTML block.

Tables that are too complex for GitHub-flavoured Markdown are emitted as raw
HTML by pandoc. They render fine, but are worth revisiting when the document is
split into notes.
