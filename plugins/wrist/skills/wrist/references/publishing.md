# Publishing

`wrist_check.py publish wrist` turns the realized prose files into `output/<slug>.epub` and `output/<slug>.pdf`.

## Needs

- `pandoc` 3.2 or later and `typst` 0.12 or later on the path. If either is missing the command prints the install steps and stops before building.
- The `publishing` gate open: question phase recorded, `check` clean, every file realized and not stale or edited, the story non-empty, `review_done: yes`, and `author:` set.

## What goes in the book

Only files whose profile function is marked `prose` (the story, for a short story), in the profile's order. The stand-in tree, `PREMISE.md`, stamps and the notes files (synopsis, outline, character, misc) are never included.

## Layout

- **EPUB:** pandoc, with `publish/epub.css` (justified text, hyphenation, indented paragraphs, `* * *` scene breaks) and a generated title page from the title, author and language in `PREMISE.md`.
- **PDF:** pandoc into `publish/book.typ` via Typst: a title page, justified and hyphenated text, first-line indents, widow and orphan control, mirrored running heads, page numbers, and chapter or section openers. The default font is Libertinus Serif, which Typst embeds.
- **Trim size** is `trim:` in `PREMISE.md`, a Typst paper name (`a5` by default, `us-trade`, `iso-b5`, `a4`). **Font** is `font:`.

## When the build fails

Pandoc's error is printed. The usual cause is a Typst helper that a newer pandoc emits and `book.typ` does not define; run `pandoc -D typst` and copy the missing `#let` or `#show` definitions into `publish/book.typ`.
