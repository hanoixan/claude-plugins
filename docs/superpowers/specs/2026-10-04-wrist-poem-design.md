# wrist: poem profile design (cycle 4)

Date: 2026-10-04. Status: draft for review. Builds on the foundation, novel and screenplay specs in the same folder.

## Purpose

Add the `poem` profile to wrist, the last of the four. The planning side is small: a form and a poem. What is new is
a **poetry grammar** (data describing verse forms), a **verse check** that can say what is knowable about a poem
against its form, a **verse text format** and reader, and a **poem publishing style** that sets verse as verse: line
breaks and indentation kept, never justified or reflowed.

The quality bar is unchanged: a poem an editor or a jury would stop for.

## Decisions taken with the user

| Question | Decision |
|---|---|
| What should the grammar do beyond describing forms? | It is data (`forms.json`). Exact checks are errors (stanza and line counts, refrains word for word, end-word groups). Syllable counts and rhyme are advisory estimates from a standard-library heuristic and never block. |
| How is the realized poem written? | As plain verse, read by a pandoc Lua reader: stanzas separated by blank lines, one line of verse per line, leading spaces kept as indentation, no markup characters to dodge. |
| Where does the machine-readable form live? | In the realized `structure.md`, written by the agent in a fixed table format and read by the checker. (The alternative, generating it from the stand-in, was offered and not chosen.) Because the agent writes it, the checker also compares it against the grammar. |

## Engine changes

All generic. The short story, novel and screenplay profiles are unchanged in behavior and every existing test keeps
passing.

### The `form` profile setting

A profile may declare a poem form:

```json
"form": {"structure": "structure.md", "poem": "work/{slug}.md"}
```

- `structure` and `poem` are paths in the file shape (the realized structure file and the realized poem; `{slug}` as
  elsewhere). Both must be listed in `files`. The grammar is the profile's own `forms.json`.
- A profile with a `form` setting gets the `verse` command and the verse checks in `gate publishing`. A profile without
  it is unaffected.
- `publish.style` gains `poem` (the registry in `wrist_publish.py` gets its third non-prose entry).

### The grammar (`profiles/poem/forms.json`)

```json
{"forms": {
  "villanelle": {"summary": "Nineteen lines in six stanzas on two rhymes with two refrains.",
                 "breaks": "exact", "syllables": 10,
                 "stanzas": ["A1 b A2", "a b A1", "a b A2", "a b A1", "a b A2", "a b A1 A2"]},
  "ballad": {"summary": "Rhymed quatrains, alternating four and three beats.", "breaks": "exact",
             "repeat": {"stanza": "X a X a", "syllables": ["8", "6", "8", "6"], "min": 2, "max": 40}},
  "free": {"summary": "No fixed pattern; the structure states the lines and stanzas.", "breaks": "free",
           "open": {"scheme": "X", "syllables": null}}
}}
```

A form has exactly one of `stanzas` (an explicit list), `repeat` (one stanza repeated between `min` and `max`
times) or `open` (the author chooses the count; the grammar gives each line's defaults). Fields:

- `scheme` tokens, one per line, space separated (a stanza string lists its lines' tokens). The notation follows the
  conventions poets and reference works already use (see "Notation" below):
  - `X` an unrhymed line;
  - `a`–`z` a rhyme sound (advisory);
  - `A1`, `B2` (an upper-case letter and a number) or a bare `A`, `B` a **refrain**: every line with the same token
    is the same line, repeated exactly. `X` is never a refrain;
  - `1`–`6` (a bare numeral) an **end-word group**: every line with the same token ends in the same word. This is the
    sestina's conventional numbering (`123456`, then `615243`, and so on).
- `syllables`: one value for every line, or a list per line of a stanza; each value is a number, a range `8-9`, or
  `null` for none.
- `breaks`: `exact` means the structure's stanza division must equal the grammar's; `free` means the structure may
  divide the same lines into stanzas as it likes (sonnets, blank verse, free verse).
- `summary`: a sentence for the reader.

### Notation

There is no standard formal grammar for generating verse forms that I could find, so wrist's grammar is its own data
format, but its tokens are the conventions already in use: lower-case letters for rhyme sounds, with `X` for unrhymed
lines (the usage in Wikipedia's rhyme-scheme tables); upper-case letters for lines repeated verbatim (the same
tables, for the rondeau, roundel and chant royal), numbered as `A1`, `A2` when a form has two refrains (the usual
way of writing the villanelle, `A1 b A2 a b A1 a b A2 a b A1 a b A2 a b A1 A2`); and numerals for the sestina's
end-word rotation (`123456` to `615243`). Where conventions overlap, wrist narrows them: an upper-case letter is
always a refrain, never a masculine rhyme. The TEI P5 guidelines (chapter 6, "Verse") are a related standard that
annotates an existing poem in XML (`lg`, `l`, `rhyme`, `met`); exporting to it is out of scope.

**Equality for refrains and end words** is after lower-casing, collapsing white space, and stripping punctuation at
the ends of the line or word.

**The first catalog** (each with a summary, scheme and syllables): `sonnet-shakespearean` (abab cdcd efef gg, 10),
`sonnet-petrarchan` (abbaabba cdecde, 10), `villanelle`, `sestina` (six sestets rotating the end-word groups `1`–`6`,
then a three-line envoi, simplified to one end word per line), `pantoum` (four-line stanzas whose second and fourth
lines return as the first and third of the next, closing the circle; refrain tokens), `haiku` (5-7-5), `tanka`
(5-7-5-7-7), `limerick` (aabba, 8-9, 8-9, 5-6, 5-6, 8-9), `triolet` (A1 B1 a A2 a b A1 B1, 8), `ballad`, `couplets`
(aa repeated, open syllables), `blank-verse` (open, unrhymed, 10 syllables, free breaks) and `free`. Terza rima,
ghazal and rondeau need rules the grammar does not yet express and are out of this cycle.

### The structure file (`structure.md`)

Written by the agent in this fixed layout; the checker reads it:

```markdown
# structure: <Title>

Form: villanelle
Lines: 19
Stanzas: 6

| Line | Stanza | Scheme | Syllables |
|---|---|---|---|
| 1 | 1 | A1 | 10 |
| 2 | 1 | b | 10 |
```

`Form:` is a grammar name or `custom`. One table row per line of the poem. The syllables cell is a number, a range, or
`-` for none.

### The `verse` command

`wrist_check.py verse WRIST_DIR [--root .] [--json]` reads the realized structure and poem.

- **The structure file is checked:** the header and table are well formed (consecutive line numbers, stanza numbers
  non-decreasing from 1, valid tokens, `Lines` and `Stanzas` matching the table, a refrain or end-word token used at
  least twice); `Form:` equals the structure stand-in's `Form:` field; when the form is in the grammar the table is
  compared with it (line count, tokens, syllables, and stanza division unless `breaks` is `free`; for a repeating
  form, the repeat count within `min` and `max`). These are **errors**.
- **The poem is checked against the structure, exactly:** the same number of lines and stanzas, blank lines between
  stanzas only, every refrain token's lines identical, every end-word group's lines ending in the same word. These
  are **errors**.
- **Advisory estimates**, never errors: a line's syllables outside the table's target, and lines of one rhyme group
  that do not rhyme, each with the estimate shown. The syllable counter is an English vowel-group heuristic; the rhyme
  key is the final vowel group and what follows it. Both are labelled estimates and are English only.
- Exit 1 on errors, 0 otherwise.
- `gate publishing` runs the same exact checks and blocks on any error; advisory estimates are never a blocker.

## The verse reader

`publish/poem/verse.lua` is a pandoc custom reader for plain verse.

- An optional first line `# Title` followed by a blank line is the poem's title. A `# ` line anywhere else is verse.
- A stanza is the lines between blank lines. Each stanza becomes a `Div` with class `stanza` holding a line block, one
  line of verse per line, trailing white space removed.
- Each leading space of a line becomes an en space (U+2002), so `    stepped` is indented two ems and survives the
  typesetter.
- Nothing in a line is markup: `*`, `_`, `#`, `1.`, `>` and `[` are literal. Smart punctuation is not applied; the
  author's quotes and dashes are kept.
- `wrist_verse.py` reads the same text with the same rules (blank lines, the title line, stanza division) for the
  checker, and the two are tested against a shared case file.

## Publishing the poem

- **Style:** `poem` (`publish/poem/`). No separate title page.
- **PDF:** A5 by default (`trim:` overrides), Libertinus Serif at 11 pt with a generous line spacing, margins that
  leave the poem room, flush left, never justified or reflowed, indentation kept. A line too long for the page wraps
  with a hanging indent. A stanza that fits on a page is not split across pages. The page number shows from the
  second page only.
- **Heading:** the title (from the file's `# Title`, else `PREMISE.md`) in bold, the author as an italic byline, then
  an optional `epigraph:` in italic. An optional `dedication:` line is set in italic before the title.
- **EPUB:** the same elements as classed blocks and a stylesheet; no separate title page; the contents list the poem's
  title.
- **Pipeline:** `pandoc --from verse.lua <poem>` with a filter that adds the heading, byline, dedication and epigraph
  and, for the PDF, turns each stanza and line into calls of layout functions in the template.

## The poem profile

### File shape

```text
structure.md
work/<slug>.md
```

Realization order is the order above: the form, then the poem. There is no family and no required premise key.

### Stand-in functions

| Function | Heading | Fields | Children |
|---|---|---|---|
| structure | `structure` | Form, Lines, Stanzas, Rhyme, Meter | none |
| poem | `poem` | Subject, Speaker, Tone, Turn, Ending, Must include, Must avoid | none |

- `Form` states a grammar name or `custom`; `Lines` and `Stanzas` are counts; `Rhyme` and `Meter` are notes in words.
  `poem` is `prose: true` (published and linted); `structure` is not.
- `Turn` says where the poem changes direction (the volta); `Ending` says how it lands. The common fields apply
  (Required, Rules, Depends on, Referred by, Unknowns). The poem stand-in depends on the structure stand-in with the
  relation `realizes`.
- Settings: `title_page` false, `form` as above, `publish` `{"style": "poem"}`, `lint_format` `prose`,
  `limits.max_prose_words` 120, relations `appears`, `mentions`, `sets up`, `pays off`, `realizes`.

### Premise questions (`questions.md`)

Required: subject (what the poem is about), form (a form from the grammar or "choose for me"), tone, audience,
length (a number of lines, or the form's own). Deferrable: speaker (who is speaking, to whom), occasion, rhyme and meter
preferences, images and motifs, words or images to avoid, title, epigraph, dedication. When the author does not pick a
form the skill proposes one and records it as an `*UNKNOWN*:` with `Proposed:`.

### Forms reference (`forms.md`)

For each catalog form: what it is, where it fits, its rules in words, what the structure must hold, and what to watch
for.

### Quality data

- **Clichés and stock moves:** stock rhymes (moon/June, heart/part, fire/desire, love/above, eyes/skies), abstractions
  in place of images (soul, pain, heart, darkness, eternity, destiny), forced inversion to make a rhyme, archaic
  diction ("thee", "o'er", "'twas"), the sunset ending, the lesson in the last line, "tears fall" and "dancing in
  the moonlight".
- **Marks of low quality:** a rhyme that bends the sense, padding to reach a syllable count, every line end-stopped
  or every line enjambed, line breaks that are only a prose sentence cut at random, an image used once and
  explained, no turn, a title that only labels, an ending that states what the poem should show.
- **Judgment checklist** for the review pass: image specificity, sound read aloud, line breaks, the turn, the ending,
  the title, form kept or broken on purpose.
- **`lint.json`:** about 20 patterns with `anywhere` scope, each with a positive and a negative sample.

## Skill and documentation

- `SKILL.md` names the fourth profile, the verse format, the structure table, the `verse` command and when to run it.
- `references/verse.md` documents the verse format, the structure format, the grammar's tokens and the advisory
  heuristics; `references/grammar.md` and `publishing.md` gain the `form` setting and the poem style.
- Templates under `assets/templates/poem/`. The root README names the profile and the four are complete.

## Example and tests

- **Example:** `assets/examples/counting/`: a complete poem and its structure, a villanelle of nineteen lines so that
  the refrains and the rhyme are exercised.
- **Grammar:** schema validation of `forms.json`, each catalog form against its stated line count, and the sestina's
  end-word rotation.
- **Structure and verse checks:** every error and every advisory estimate, the structure-against-grammar comparison,
  and the gate.
- **Reader and heuristics:** a shared case file for the reader and `wrist_verse.py`, the syllable counter on a list of
  words, the rhyme key on pairs.
- **Publish:** command planning, real builds, and the Typst the filter produces. The test suite has no PDF reader, so
  page geometry, the hanging indent and stanza keeping are checked by rendering pages and looking at them in the plan
  and in the trial.
- **Trial (required for done):** a fresh headless session writes a short poem through all four phases with me as the
  author; the PDF is looked at; defects are fixed or recorded.

## Out of scope

Collections of poems (one poem per project); terza rima, ghazal and rondeau; concrete and visual poems; prose
poems; scansion beyond a syllable count; non-English syllable and rhyme heuristics; audio.

## Open decisions

Choices made without an explicit instruction, to confirm during review:

1. The token notation (`a`, `A1`, `1`, `X`) follows poets' conventions but narrows them (an upper-case letter is always a refrain), and the equality rule for refrains and end words is mine.
2. The sestina's envoi is simplified to one end word per line.
3. Each leading space of a verse line becomes an en space.
4. The default paper is A5.
5. The advisory syllable and rhyme heuristics are English only.
6. A `# Title` is a title only on the first line, followed by a blank line.
7. The grammar's `breaks` setting: `exact` or `free`; sonnets, blank verse and free verse are `free`.
8. A stanza is kept whole on a page only when it is short enough to fit one.
9. A dedication is set before the title and an epigraph after the byline.
10. The structure stand-in's `Form:` must equal the structure file's `Form:`.
