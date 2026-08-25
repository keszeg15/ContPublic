# gdoc_import

Fetches a Google Doc and converts it into Quartz-flavoured Markdown, ready to be
split into individual wiki notes.

Everything except the pandoc wrapper comes from the standard library, and
`pypandoc-binary` ships pandoc itself, so no system packages are required.

## Running it

The script declares its dependency inline (PEP 723), so with
[uv](https://docs.astral.sh/uv/) there is no setup step at all:

```bash
uv run fetch_gdoc.py
```

uv fetches a suitable Python and the pandoc-bearing wheel on first run. Install
uv itself with `curl -LsSf https://astral.sh/uv/install.sh | sh`.

### Without uv

Debian and Ubuntu ship `python3` without pip and refuse system-wide installs
(PEP 668), so go through a virtual environment, which brings its own pip:

```bash
sudo apt install python3-venv        # only if `python3 -m venv` fails
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python fetch_gdoc.py
```

On Windows the interpreter is at `.venv/Scripts/python` instead.

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
tab, adds the front matter and tightens the spacing:

```bash
uv run split_notes.py
```

Each note gets `Category: Log` and `tags: [G5eC]`, and the tab title becomes the
file name. A tab tends to restate its own name at the top of the page, sometimes
twice over, so any `Title` styled line the tab opens with is dropped rather than
duplicating the file name in the body.

A blank line between two ordinary lines is also removed. Headings, quotes,
tables, raw HTML, image embeds and indented blocks keep their spacing, so the
structure is never altered. This suits Quartz, where the `hard-line-breaks`
plugin renders a single newline as a line break.

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
