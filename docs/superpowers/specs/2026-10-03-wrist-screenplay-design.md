# wrist: screenplay profile design (cycle 3)

Date: 2026-10-03. Status: draft for review. Builds on `2026-10-03-wrist-foundation-design.md` and
`2026-10-03-wrist-novel-design.md`.

## Purpose

Add the `screenplay` profile to wrist. The planning side is close to the novel's: a synopsis, an outline,
registries, and a numbered family of act files fixed by `PREMISE.md`. The difference is the realized text. A
screenplay is not prose: it is slug lines, action, character cues, dialogue, parentheticals and transitions in a
fixed industry layout, where a page is about a minute. The profile therefore needs a screenplay text format, a
reader for it, a publishing style that lays it out like a real script, and its own quality data.

The quality bar is unchanged: a script an agent, a reader or a jury would stop for.

## Decisions taken with the user

| Question | Decision |
|---|---|
| How are acts written and published? | In Fountain, the plain-text screenplay standard, inside the `act-<n>.md` files. A pandoc Lua custom reader parses it, so pandoc and typst make both the EPUB and a screenplay-layout PDF. |
| What precedes the first act? | An industry title page only: the title, "Written by", the author, and optional `based_on:`, `draft:` and `contact:` lines. No copyright page, dedication, epigraph or contents. |
| Act headings in the published script? | Off by default. The yes/no premise key `act_headings:` prints "ACT ONE"-style labels, each on a new page, for TV and stage scripts. |

## Engine changes

All generic. The short story and novel profiles are unchanged in behavior; every existing test keeps passing.

### Publishing style

A profile gets an optional top-level `publish` object:

```json
"publish": {"style": "screenplay"}
```

- `style` names a publishing style. The styles are `story`, `book` and `screenplay`; `wrist_publish.py` holds a
  registry that maps each style to the code that plans its pandoc commands. An unknown style is a `check`/`publish`
  error naming the known ones.
- With no `publish` key the style is inferred as today: `book` when the profile has a function with `sequence: true`,
  otherwise `story` (which still reads `title_page`). The short story and novel profiles therefore need no change.
- `screenplay` is explicit in its `profile.json`. Its files live under `publish/screenplay/`; the existing `story`
  and `book` files stay where they are.

### Lint format

A profile may set `"lint_format": "fountain"` (default `"prose"`). It changes which `scope` values a lint item may use
and how a line is classified:

- `prose`: `narration` or `anywhere`, as now.
- `fountain`: `action`, `dialogue` or `anywhere`. `action` means action lines only (not scene headings, cues or
  transitions); `dialogue` means dialogue and parenthetical lines.

`wrist_lint.py` gains `classify_fountain(text) -> list[(line_number, kind, text)]`, with kinds `heading`, `action`,
`character`, `parenthetical`, `dialogue`, `transition`, `centered`, `blank`, `note`, `boneyard`, `marker`. A lint item
with the wrong scope for the profile's format is a profile error.

### Shared Fountain cases

The Lua reader and the Python classifier are two implementations of the same rules. A shared file,
`tests/fountain_cases.json`, holds snippets with the expected sequence of element kinds, and both are tested against
it, so they cannot drift apart unnoticed.

## The Fountain reader

`publish/screenplay/fountain.lua` is a pandoc custom reader (`pandoc --from publish/screenplay/fountain.lua`). It
reads the concatenated act files and emits a document of Divs with classes `scene-heading`, `action`, `character`,
`dialogue`, `parenthetical`, `transition`, `centered`, plus `act-marker` and a page break. It implements Fountain 1.1:

- **Scene heading:** a line starting `INT`, `EXT`, `EST`, `INT./EXT`, `INT/EXT` or `I/E` followed by `.` or a space
  (any case), or forced with a leading `.` that is not `..`; with a blank line before and after.
- **Character:** a line of upper-case letters, digits and an optional extension in brackets (`(V.O.)`, `(CONT'D)`),
  preceded by a blank line and followed by a non-blank line, or forced with a leading `@`. A line ending in `TO:` is a
  transition, not a character.
- **Dialogue and parenthetical:** the lines after a character up to a blank line; a line wrapped in `( )` is a
  parenthetical.
- **Transition:** an upper-case line ending in `TO:` with a blank line before and after, or forced with `>`.
- **Centered:** `> text <`. **Page break:** a line of three or more `=`.
- **Emphasis:** `*italic*`, `**bold**`, `_underline_`.
- **Dropped:** notes `[[ ... ]]`, boneyard `/* ... */`, sections (`#`) and synopses (`=`), and the Fountain title page.
- **Action:** everything else. A line that is only a character-like name with no dialogue after it is action.

wrist's own extension: the publisher writes a one-line marker file `@@ACT ONE@@` before an act when `act_headings` is
yes; the reader turns it into an `act-marker` Div. Fountain applications ignore the line as action, and the marker
never appears in realized files. Dual dialogue (`^`) is read as ordinary sequential dialogue.

## Publishing the screenplay

- **PDF** (`screenplay.typ`): US letter (A4 through the `trim:` premise key); a 12 pt monospace font taken from the list
  Courier Prime, Courier New, DejaVu Sans Mono (the last is bundled with typst and has Courier's 10-characters-per-inch
  width, so a page holds about 55 lines and runs about a minute); margins left 1.5", right 1", top 1", bottom 1".
  Indents measured from the left margin: scene heading and action 0; character cue 2.2"; dialogue 1.0" with 3.5" width;
  parenthetical 1.6"; transitions right-aligned; scene headings in bold capitals; one blank line between elements. A
  character cue and the first line of its dialogue never split from each other across a page.
- **Pages:** the title page carries no number; the first script page carries none; each later page shows its number
  top right as "2.".
- **Title page:** the title centered upper-middle, then "Written by" and the author; `based_on:` below; `contact:` at
  the foot left and `draft:` at the foot right. Lines whose key is not set are left out.
- **Act headings:** when `act_headings:` is yes, a centered bold "ACT ONE", "ACT TWO" and so on, starting a new page.
- **EPUB** (`screenplay.css`): the same classes in a monospace reading layout: scene headings bold, character and
  dialogue indented, transitions right-aligned.
- **Pipeline:** `pandoc --from fountain.lua <inputs> --lua-filter screenplay.lua [-M key=value ...]`, with
  `--template screenplay.typ --pdf-engine=typst` for the PDF. The `screenplay.lua` filter turns each classed Div into
  a Typst block call for the PDF and leaves the Div for the EPUB. Generated marker files are written into `output/`
  and removed after the build, as the novel's marker is.

## The screenplay profile

### File shape

```text
synopsis.md      outline.md      character.md      misc.md
work/act-<n>.md        (family acts, count from PREMISE)
```

Realization order is the order above. Acts are zero-padded to the width of the count as the novel's chapters are.

### Premise keys

`acts` (required int, 1 to 7) and `act_headings` (bool). Optional free-text keys read by the publisher: `based_on`,
`draft`, `contact`, `trim`, `font`, `author`, `language`.

### Stand-in functions

| Function | Heading | Fields | Children |
|---|---|---|---|
| synopsis | `synopsis` | Logline, Ending, Theme | none |
| outline | `outline` | Structure | `beat`: Purpose, Change, Pages |
| characters | `characters` | none | `character`: Wants, Flaw, Voice, Arc |
| misc | `misc` | none | `location`: Slug, Facts; `prop`, `concept`, `timeline`: Facts |
| act | `act` | Pages | `scene`: Purpose, Location, Pages, Must include, Must avoid |

- `act` has `required_when_realized: ["Established"]`, `sequence: true` and `prose: true`. It has no `heading_field`:
  a screenplay act has no printed heading of its own.
- `Pages` is a target page range as text (for example `1-28`). `location`'s `Slug` states the exact location name as it
  is written in scene headings (for example `HARBOUR`), so the realization can keep slug lines consistent.
- Relations: appears, mentions, sets up, pays off, realizes, continues. `title_page` is true; `lint_format` is
  `fountain`; `publish` is `{"style": "screenplay"}`; `limits.max_prose_words` is 120.

### Structures (`structures.md`)

Aristotle's five-act, Syd Field's paradigm, Hero's Journey, Save the Cat!, the sequence approach (eight sequences),
Story Circle, Truby's 22 steps, and kishōtenketsu for shorts. For each: what it is, best fit, where its beats fall on
the page count for a 120-page feature and for a 10-page short, what the outline must hold, and what to watch for. A
format table gives defaults for acts and runtime: feature (3 or 4 acts, 90 to 120 pages), short (1 to 3 acts, 5 to 40
pages), and TV-style (5 or 6 acts with `act_headings: yes`).

### Premise questions (`questions.md`)

Required: genre, premise, ending, tone, audience (including the rating a script aims at), format (feature or short),
runtime (minutes), acts (the count; proposed from the runtime and the structure), viewpoint of the story (whose story
it is). Deferrable: setting and period, locations and any budget limits, themes, comps, characters, events, fixed
details, structure, content to avoid, and act headings (yes or no, with the reason). The `acts` and `act_headings`
answers go in the `PREMISE.md` front matter. The title page lines (`based_on`, `draft`, `contact`) and `trim` are asked
in the publishing question phase.

### Quality data

- **Clichés and stock moves** for scripts: openings (waking up, an alarm clock, a mirror, a dream, a voice-over that
  explains), "we see" and camera directions in a spec script, on-the-nose dialogue, characters who state their feelings,
  exposition by "as you know", the quiet before the storm line, the mentor's death, and stock transitions.
- **Marks of low quality:** pages over or under the runtime, action blocks longer than four lines, unfilmable
  description (what a character thinks, remembers or knows), scenes that do not turn, dialogue in one voice, a first
  act that takes a third of the script, an act turn that lands off its page, and slug lines that rename the same place.
- **Judgment checklist** for the review pass (per act and whole script), including the runtime check against pages
  and consistency of slug lines and locations.
- **`lint.json`** with `fountain` scopes: about 16 patterns such as `we see`/`we hear` and camera directions (action),
  `suddenly` and `begins to` (action), stock reactions (action), `(beat)` and `as you know` (dialogue), each with a
  positive and a negative sample.

## Skill and documentation

- `SKILL.md` names the third profile, the Fountain format, how to write scenes (slug lines, one action beat per
  paragraph, short blocks), and the title-page questions. It carries the realization loop for a family (realize the act,
  fill in `Established:`, stamp it), as the novel does.
- `references/grammar.md` documents `publish.style`, `lint_format` and the Fountain scopes; a new
  `references/fountain.md` documents the dialect the reader accepts, wrist's own act marker, and what is dropped.
- Templates under `assets/templates/screenplay/`. The root README notes the profile.

## Example and tests

- **Example:** `assets/examples/the-third-bell/`: a tiny complete screenplay, three acts of one or two pages each,
  realized in real Fountain with a filled `Established:` per act.
- **Reader and classifier:** every Fountain rule above, against the shared cases, in both implementations.
- **Engine:** `publish.style` inference and errors, `lint_format` scope validation, the profile's premise keys and file
  set, and the gates and stamp rules on acts.
- **Publish:** command planning for the style, markers, and real builds (pandoc and typst are installed). The EPUB
  structure and classes are asserted, and the Typst the filter produces is asserted element by element. The test
  suite has no PDF reader, so page geometry, the indents and the page numbering (unnumbered title and first script
  page, "2." onward) are verified by rendering pages and looking at them, in the plan's verification step and in the
  trial.
- **Trial (required for done):** a fresh headless session writes a tiny screenplay through all four phases, with me as
  the author. The PDF pages are looked at, and defects are fixed or recorded.

## Out of scope

The poem profile (the next cycle); a check that slug lines match declared locations; an automatic page count and a
pages-against-runtime report; dual-column dialogue; revision marks and scene numbers; stage-play and TV formats beyond
the `act_headings:` option; cover images.

## Open decisions

Choices made without an explicit instruction, to confirm during review:

1. `acts` is limited to 1 through 7.
2. The default font is the list Courier Prime, Courier New, DejaVu Sans Mono; a machine with a real Courier gets it, and
   the PDF can differ between machines for that reason. `font:` overrides it.
3. The first script page carries no number and later pages show "2." and so on.
4. When a profile has no `publish` key the style is inferred (`book` if it has a `sequence` function, else `story`).
5. Publishing styles are a registry in `wrist_publish.py`; the existing `story` and `book` files stay where they are
   and only the screenplay's files are in their own folder.
6. wrist's `@@ACT ...@@` marker line is a private extension, dual dialogue is read as sequential dialogue, and Fountain
   sections and synopses are dropped.
7. The Python classifier and the Lua reader are checked against one shared case file rather than sharing code.
8. The EPUB of a screenplay is a reading copy in a monospace layout, not a formatted-script exchange format.
9. No page count is reported, although a page is about a minute.
