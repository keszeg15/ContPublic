# gdoc_import

Fetches a Google Doc and converts it into Quartz-flavoured Markdown, ready to be
split into individual wiki notes.

Everything except the pandoc wrapper comes from the standard library, and
`pypandoc-binary` ships pandoc itself, so no system packages are required.

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt     # macOS / Linux
```

## Usage

```bash
.venv/Scripts/python fetch_gdoc.py
```

Useful flags:

| Flag | Purpose |
| --- | --- |
| `--doc-id` | Document id or full Google Docs URL. Defaults to the G5EC party log. |
| `--slug` | Base name for the generated files. Defaults to `partylog`. |
| `--skip-download` | Reuse the cached exports instead of hitting the network. |
| `--work-dir` | Where to stage the output. Defaults to `build/`. |

## Output

```
build/
  raw/partylog.docx        downloaded source
  raw/partylog.google.md   Google's own export, used as a structure reference
  out/partylog.md          converted Markdown
  out/pics/*.png|jpg       extracted images
```

Nothing is written into `content/` — that happens in the splitting step, so the
staging directory can be deleted and regenerated at any time.

## Notes

The document has to be shared as "anyone with the link"; that is what lets the
export endpoint work without authentication. If sharing is revoked, Google
answers with an HTML login page under a 200 status, which the script detects by
checking the `.docx` magic bytes.

Both exports are downloaded because neither is complete on its own. The `.docx`
has the better body structure and keeps images at their original resolution,
but it flattens Google Docs tab titles into ordinary paragraphs. Google's own
Markdown export renders those titles as level 1 headings, so it is used purely
as a reference to promote them back into headings. The `tab=` URL parameter is
not a way around this: the export endpoint ignores it and always returns the
whole document.

Images are renamed after the section they appear in and referenced as Obsidian
embeds (`![[name.png]]`), matching the convention used elsewhere in `content/`.
Images that sit inside a table stay as `<img>` tags, because an embed would not
be rendered inside a raw HTML block.

Tables that are too complex for GitHub-flavoured Markdown are emitted as raw
HTML by pandoc. They render fine, but are worth revisiting when the document is
split into notes.
