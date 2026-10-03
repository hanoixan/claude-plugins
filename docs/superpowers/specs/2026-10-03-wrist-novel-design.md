# wrist: novel profile design (cycle 2)

Date: 2026-10-03. Status: draft for review. Builds on `2026-10-03-wrist-foundation-design.md`.

## Purpose

Add the `novel` profile to wrist. A novel needs three things the short story profile cannot
express: files that exist only on request (forward, prologue, afterward, index), a numbered family
of chapter files whose count is fixed up front, and publishing that assembles front matter,
chapters and back matter into one book. A novel is also long enough that realization spans many
sessions, so facts established in early chapters must reach later ones without rereading the book.

The quality bar is unchanged: work that would stand up to an editor or a prize jury for its
audience.

## Decisions taken with the user

| Question | Decision |
|---|---|
| How is the file set decided? | In `PREMISE.md`: `chapters: <n>` and yes/no keys for the optional files. `check` expands the profile from those values and requires exactly those stand-ins. |
| How do chapter facts carry forward? | An `Established:` field on each chapter stand-in, filled after the chapter is realized. |
| Front matter beyond the file shape? | `PREMISE.md` keys `copyright:`, `dedication:`, `epigraph:`; the contents page is generated. |
| Title page? | A novel has one (`title_page: true`, the default). A short story has none. |

## Engine changes

All are generic: no novel vocabulary enters the checker. The short story profile is unchanged and
all of its tests keep passing.

### `files` entries

Three kinds, all in `profile.json`:

```json
{"path": "synopsis.md", "function": "synopsis", "order": 1},
{"path": "work/prologue.md", "function": "prologue", "order": 6, "when": "prologue"},
{"path": "work/chapter-{n}.md", "function": "chapter", "order": 7, "family": "chapters"}
```

- A plain entry always exists.
- `when` names a `PREMISE.md` key of type `bool`. The entry exists only when that key is true.
- `family` names a `PREMISE.md` key of type `int`. The entry expands into one file per number
  `1..N`, with `{n}` replaced by the number zero-padded to the width of `N` (28 chapters give
  `chapter-01.md` … `chapter-28.md`; 9 give `chapter-1.md` … `chapter-9.md`). The path must
  contain `{n}`. A family entry may not also carry `when`.
- `order` keeps its meaning (realization order, ties by position). A family's files come out in
  ascending `n`.

### `premise_keys`

A new top-level section declares the `PREMISE.md` front matter keys the profile reads:

```json
"premise_keys": {
  "chapters": {"type": "int", "min": 1, "max": 200, "required": true},
  "forward": {"type": "bool"}, "prologue": {"type": "bool"},
  "afterward": {"type": "bool"}, "index": {"type": "bool"}
}
```

- `bool` accepts `yes`, `no`, `true`, `false` (any case); the default is false.
- `int` accepts a base-10 integer within `min` and `max`.
- `required` keys must be present. A wrong or missing value is an error from `check` and the
  generation gate, naming the key and the accepted values.
- Keys not declared are ignored, so a short story's `PREMISE.md` is unaffected.
- `when` and `family` must name declared keys of the right type; `profile.json` validation rejects
  anything else.

### API

`Profile.expected_files(slug, options=None)` and `Profile.function_for(rel, slug, options=None)`
take the resolved premise values. `Profile.resolve_options(front)` turns the premise front matter
into `(values, problems)`. When a value is missing or invalid, a `when` file is treated as absent
and a family as empty, and the problem is reported once through `premise_problems`. Every command
that used `expected_files(slug)` (`check`, `order`, `status`, `stamp`, `gate`, `lint`, `publish`)
passes the premise values.

### Function-level additions

| Field in `functions.<name>` | Meaning |
|---|---|
| `required_when_realized` | field labels the stand-in must hold once its realized file exists |
| `sequence` | true: each file in the family should link to the previous one with `(continues)` |
| `heading_field` | name of the field whose value is the exact first line the realized file must start with |

- `stamp` refuses to stamp a realized file whose stand-in lacks a `required_when_realized` field,
  and says which. `gate publishing` reports the same as a blocker.
- `check` warns when a `sequence` file with `n > 1` has no `Depends on:` link to file `n-1` with
  the relation `continues`.
- `gate publishing` reports a realized file whose first line is not `# <value of heading_field>`.
- The relation word `continues` is added to the novel profile's `relations`.

## The novel profile

### File shape

```text
synopsis.md      outline.md      character.md      misc.md
work/forward.md        (when forward)
work/prologue.md       (when prologue)
work/chapter-<nn>.md   (family chapters, count from PREMISE)
work/afterward.md      (when afterward)
work/index.md          (when index)
```

Realization order is the order above, as the user listed it. The profile's `order` values are data,
so changing it later needs no code.

### Stand-in functions

| Function | Heading | Fields | Children |
|---|---|---|---|
| synopsis | `synopsis` | Logline, Ending, Theme | none |
| outline | `outline` | Structure | `beat`: Purpose, Change |
| characters | `characters` | none | `character`: Wants, Flaw, Voice, Arc |
| misc | `misc` | none | `place`, `object`, `concept`: Facts; `timeline`: Facts |
| forward, prologue, afterward | same name | Heading, Purpose, Voice, Must include, Must avoid | none |
| index | `index` | Heading, Rules | none |
| chapter | `chapter` | Heading, Point of view, Length, Established | `scene`: Purpose, Length, Must include, Must avoid |

- `heading_field` is `Heading` for forward, prologue, afterward, index and chapter. The stand-in
  states the exact first line of the realized file, for example `# 7. The Long Wait`.
- `chapter` has `required_when_realized: ["Established"]` and `sequence: true`.
- `forward`, `prologue`, `afterward`, `chapter` and `index` are `prose`.
- The common fields (Required, Rules, Depends on, Referred by, Unknowns) apply as in every profile.
- Outline beats are tied to chapters by the chapter's `Depends on:` links to beats, with the
  relation `realizes`, as scenes link to beats in the short story.
- Relations: appears, mentions, sets up, pays off, realizes, continues.
- `limits.max_prose_words` stays 120.

### Established

`Established:` records what a realized chapter fixed that later chapters must respect: new facts,
dates, injuries, objects moved, who knows what, promises made. It is written after the chapter,
then the chapter is re-stamped. Later chapters link back with `(continues)` and read the field in
place of the earlier text. An empty field does not satisfy the requirement.

### Premise keys

`chapters` (required int, 1 to 200), `forward`, `prologue`, `afterward`, `index` (bool). Optional
free-text keys read only by the publisher: `copyright`, `dedication`, `epigraph`, `trim`, `font`,
`author`, `language`.

### Structures (`structures.md`)

Three-act, Save the Cat! (15 beats), Hero's Journey (12 stages), Seven-Point, five-act (Freytag),
Fichtean curve, and Story Circle (8 steps). For each: what it is, best fit, how its beats spread
across a chapter count (as percentages and as an example for 24 chapters), what the outline must
hold, and what to watch for. A genre table suggests defaults: mystery, romance, thriller, fantasy,
science fiction, literary, young adult, historical, horror.

### Premise questions (`questions.md`)

Required: genre, premise, ending, tone, audience (including the age category: adult, young adult,
middle grade), length (target words), chapters (count; the skill proposes one from the length and
the structure), viewpoint (person, tense, single or multiple point-of-view characters).
Deferrable: subgenre, setting and era, world rules, themes, comparable titles, standalone or
series, known characters, known events, fixed details, structure, content to avoid, and one
yes/no question each for forward, prologue, afterward and index with the reason it is wanted.
The `chapters`, `forward`, `prologue`, `afterward` and `index` answers are written into the
`PREMISE.md` front matter as well as the body, because they decide the file set.

### Quality data (`quality.md`, `lint.json`)

- **Clichés and stock moves** for long fiction: openings (the chosen one, the dream, the
  alarm-clock waking, the mirror), prologues that explain the world, information dumped in dialogue,
  mentor-dies-so-the-hero-grows, villains who explain their plan, ensemble casts of one voice,
  coincidences that solve the plot, the last-chapter epilogue that ties every thread.
- **Marks of low quality** at novel scale: a sagging middle, no midpoint turn, stakes that do not
  escalate, subplots that stop without resolving, point-of-view slips, chapters that all end the
  same way, repeated verbal tics across chapters, a protagonist without a decision in the second act.
- **Judgment checklist** for the review pass, per chapter and for the whole book (pacing, midpoint,
  escalation, subplot closure, voice, chapter-ending variety, continuity against `Established`).
- **`lint.json`**: the short story's searchable patterns plus novel-specific ones. The two files are
  independent copies; factoring shared patterns out is deferred until a third profile needs them.

## Publishing

`publish` assembles the book in this order:

1. Title page (the profile's `title_page` is true).
2. Copyright page, dedication, epigraph: each only if its `PREMISE.md` key is set.
3. Contents page, generated from the level-1 headings of the realized files.
4. Forward, prologue, chapters in order, afterward, index (those that exist).

- **Mechanism:** the publisher writes a generated front-matter file in `output/` (removed after the
  build) containing the copyright, dedication, epigraph and contents blocks as format-specific raw
  blocks, and passes it to pandoc before the realized files. The title page comes from the template.
  The stand-in tree, `PREMISE.md` and stamps are never included.
- **PDF:** every level-1 heading starts a new page; every page before the first chapter (title page and its back, copyright,
  dedication, epigraph, contents, forward, prologue) carries no running head, and numbering starts
  after the title page in lower-case roman numerals; the first chapter's page is arabic 1.
- **EPUB:** one file per level-1 heading, a navigation contents, a visible contents page, and the
  title page.
- **Gate:** `gate publishing` additionally blocks on a missing `Established:`, a heading line that
  does not match `Heading:`, and any file of the expected set that is pending, stale or edited.

## Skill and documentation

- `SKILL.md` becomes profile-aware: it asks which profile, reads that profile's `questions.md`,
  writes the premise keys into the front matter, and names the realization loop for a family:
  realize chapter, fill `Established:`, stamp, next chapter.
- `references/grammar.md` documents `files` entry kinds, `premise_keys`, `Heading`, `Established`
  and the `continues` relation.
- The root README notes the novel profile.

## Example and tests

- **Example:** `assets/examples/salt-road/`, a complete tiny novel: 3 chapters, a forward, no
  prologue, afterward or index, with real (short) chapter text and a filled `Established:` in every
  chapter. It is the integration fixture.
- **Engine tests:** each `files` kind; zero-padding at widths 1, 2 and 3; a missing, extra or gapped
  chapter file; `when` on and off; each `premise_keys` error; `stamp` refusing without
  `Established:`; the `(continues)` warning; the heading-line blocker; a profile that declares a
  `when` or `family` key of the wrong type; the short story example unchanged.
- **Profile tests:** schema, lint pairs, structures and quality content, as for the short story.
- **Publish tests:** command planning with front matter; real builds (the tools are installed) of
  the novel example, asserting EPUB file count and navigation, and the PDF opening on a title page.
- **Trial (required for done):** a fresh headless session loads the plugin and writes a short novel
  (three to four chapters) through all four phases with me as the author, as was done for the short
  story. Defects found are fixed or recorded, and the PDF pages are looked at.

## Out of scope

The screenplay and poem profiles; parts or sections above chapters; automatic index generation;
series metadata; cover images.

## Open decisions

Choices made without an explicit instruction, to confirm during review:

1. Chapter numbers are zero-padded to the width of the count.
2. The chapter limit is 200.
3. `Heading:` is a stand-in field, and the publishing gate checks the first line of the realized file
   against it.
4. `stamp` refuses a chapter whose stand-in has no `Established:`, rather than only the gate checking.
5. Realization order follows the user's listing (forward and prologue before the chapters). A forward
   written first cannot reflect the finished book; the stand-in states what it must say, and the
   forward is stale-tracked like any file, so it can be realized again.
6. The novel's `lint.json` is a copy of the short story's plus additions.
7. The visible contents page is built from level-1 headings only.
