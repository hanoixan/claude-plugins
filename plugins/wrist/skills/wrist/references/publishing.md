# Publishing

`wrist_check.py publish wrist` turns the realized prose files into `output/<slug>.epub` and `output/<slug>.pdf`.

## Needs

- `pandoc` 3.2 or later and `typst` 0.12 or later on the path. If either is missing the command prints the install steps and stops before building.
- The `publishing` gate open: question phase recorded, `check` clean, every file realized and not stale or edited, the story non-empty, `review_done: yes`, and `author:` set.

## What goes in the book

Only files whose profile function is marked `prose` (the story, for a short story), in the profile's order. The stand-in tree, `PREMISE.md`, stamps and the notes files (synopsis, outline, character, misc) are never included.

## Layout

- **EPUB:** pandoc, with `publish/epub.css` (justified text, hyphenation, indented paragraphs, `* * *` scene breaks). The title, author and language come from `PREMISE.md`.
- **PDF:** pandoc into `publish/book.typ` via Typst: justified and hyphenated text, first-line indents, widow and orphan control, mirrored running heads, page numbers, and chapter or section openers. The default font is Libertinus Serif, which Typst embeds.
- **Trim size** is `trim:` in `PREMISE.md`, a Typst paper name (`a5` by default, `us-trade`, `iso-b5`, `a4`). **Font** is `font:`.

## Title page

Whether a work gets a separate title page is the profile's `title_page` setting. A short story has none: its own heading is the title, and an italic byline (the `author:` from `PREMISE.md`) follows it in both formats. A profile that sets `title_page` to true, as a novel's will, gets a title page with the title and author, and no byline under the first heading.

## A book with front matter

When a profile has a `sequence` function (a novel's chapters), the book is assembled in this order: title page, copyright page, dedication, epigraph, contents, then the realized files in the profile's order. The copyright, dedication and epigraph are the `copyright:`, `dedication:` and `epigraph:` keys of `PREMISE.md`, each optional; the contents page is generated from the level-1 headings. In the PDF every page before the first chapter carries no running head and is numbered in lower-case roman numerals after the title page; the first chapter's page is arabic 1. In the EPUB the contents page is the navigation document, listed in the reading order after the title page. The publisher writes a temporary marker file into `output/` for the numbering switch and removes it afterward.

## A screenplay

A screenplay is read with the Fountain reader and laid out as a script: US letter (A4 with `trim: a4`), a 12 pt monospace font taken from the list Courier Prime, Courier New, DejaVu Sans Mono (the last is bundled with typst), margins 1.5 inches left and 1 inch elsewhere, about 55 lines and about a minute a page. The title page has the title, "Written by", the author, and the optional `based_on`, `draft` and `contact` lines; it carries no number and neither does the first script page; later pages show "2." and so on at the top right. With `act_headings: yes` each act starts a new page with a centered "ACT ONE"-style heading. The EPUB is a monospace reading copy of the same elements. No copyright page, dedication, epigraph or contents page is built.

## When the build fails

Pandoc's error is printed. The usual cause is a Typst helper that a newer pandoc emits and `book.typ` does not define; run `pandoc -D typst` and copy the missing `#let` or `#show` definitions into `publish/book.typ`.
