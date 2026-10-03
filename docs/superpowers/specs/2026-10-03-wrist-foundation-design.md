# wrist: foundation design (cycle 1)

Date: 2026-10-03. Status: draft for review.

## Purpose

`wrist` is a Claude Code plugin for writing prose works the way `skel` designs code: a tree of
prose stand-ins is written first, checked mechanically, and only then turned into the final
text. Each stand-in holds notes, facts, dependencies, rules and unknowns for one file that will
exist later. It never holds the final text.

The target quality for every profile is **award-winning work for its intended audience**. Each
profile therefore carries its own questions, structures, and a list of clichés and marks of
low quality to avoid.

## Phases

Every phase is preceded by a **question phase** whose job is to surface concerns, ambiguities
and knowledge gaps before work begins. Answers that the user defers become formal
`*UNKNOWN*:` entries.

| # | Phase | Result |
|---|---|---|
| 1 | Premise | `wrist/PREMISE.md`: profile, title, slug, and the answers to the profile's questions |
| 2 | Generation | the complete stand-in tree under `wrist/`, checked clean |
| 3 | Realization | the real files, written from the stand-ins; the work is fully readable but unpublished |
| 4 | Publishing | `output/<slug>.pdf` and `output/<slug>.epub` |

Gates, each failing with a message that names the exact blocker:

- Premise to Generation: the profile is chosen and its questions are answered or recorded as
  unknowns.
- Generation to Realization: `check` is clean and the tree has no blocking unknowns.
- Realization to Publishing: every stand-in has a realized file, `status` shows none stale or
  hand-edited since stamping, and the review pass is recorded as done.

## Decomposition

This spec covers **cycle 1 only**. Later cycles each get their own spec, plan and build.

| Cycle | Content |
|---|---|
| 1 (this spec) | copy and rename, profile-driven checker, `shortstory` profile, phases 1 to 3 workflow, basic publisher |
| 2 | `novel` profile |
| 3 | `screenplay` profile |
| 4 | `poem` profile |

The file shapes of the later profiles are fixed by the user and listed under "Roadmap" so the
cycle 1 profile format is designed to hold them.

## Plugin layout

`plugins/wrist/` starts as a copy of `plugins/skel/`, renamed throughout: directory, plugin
manifest, skill name, script names (`wrist_check.py`, `wrist_mv.py`), CLI help, SKILL.md,
references, templates, tests, and every mention of the word and its `.skel.md` / `skel/`
forms. `plugins/skel/` is not modified. The marketplace README gains a wrist entry.

```text
plugins/wrist/
  .claude-plugin/plugin.json
  skills/wrist/
    SKILL.md
    references/            grammar, phases, publishing
    assets/templates/      one template per heading type and file function
    profiles/shortstory/   profile.json, questions.md, structures.md, quality.md, lint.json
    publish/               stylesheet, typst template, metadata mapping
    scripts/               wrist_check.py, wrist_mv.py
  tests/
```

### Removed from the copy

The following describe code and have no prose meaning:

- file kinds code, data, iac and resource, and extension inference;
- `role:`, `unit:`, `untested:`, manifests, and test-to-product pairing and warnings;
- abstract placeholder extensions;
- `module`, `class`, `function` headings and the Inputs, Returns, State changes, Owns and
  Access fields;
- the `Spec:` header stamp and name-in-code checks;
- the undo-system example and `batches`.

### Kept

Parsing of sections and fields, link resolution and fragments, the bidirectionality check,
unknown declaration and follower rules, `unknowns`, `fix-backlinks` and `wrist_mv`.

## Stand-ins

### Naming

`wrist/<mirrored path>.wrist.md` stands in for `<mirrored path>` at the project root, using
skel's convention. One work per project root.

```text
wrist/synopsis.md.wrist.md         ->  synopsis.md
wrist/work/the-lamp.md.wrist.md    ->  work/the-lamp.md
```

`wrist/PREMISE.md` is the one non-stand-in file. It replaces skel's `SYSTEM.md`.

### Function of a stand-in

A stand-in's function in the profile (for example synopsis, outline, characters, misc, story)
comes from the profile's file-shape table, matched on its mirrored path. It is not inferred
from the extension and there is no `kind:` or `role:` front matter.

### Headings and fields

The first heading of a stand-in is typed by its function, and sub-headings use the typed
headings the profile declares for that function. Both the typed headings and the required
fields per heading come from `profile.json`, not from the checker. Fields belong to the nearest
typed heading, as in skel.

Fields common to all profiles:

| Field | Meaning |
|---|---|
| `Depends on:` | what must be known or fixed before this can be written |
| `Referred by:` | what relies on this; maintained by `fix-backlinks` |
| `Rules:` | constraints the realization must follow (voice, tense, length, forbidden moves) |
| `Required:` | `always`, `conditional: <when>` or `optional: <what is lost>` |
| `Unknowns:` | `*UNKNOWN*:` entries, or `Unknowns: none` |

Fields specific to a heading (such as a scene's Purpose or a character's Wants) are declared in
the profile.

### Links

`Depends on:` and `Referred by:` keep skel's syntax and bidirectionality rule. A link may carry
an optional relation word in parentheses after the link text, taken from a list the profile
declares (for example `appears`, `sets up`, `pays off`, `mentions`). An unlisted word is a
warning. The checker does not require the two ends of a pair to use the same word.

```markdown
- **Depends on:** [Mara](../character.md.wrist.md#character-mara) (appears)
```

### Unknowns

Unchanged from skel: `*UNKNOWN*:` with `Kind: blocking | local`, `Proposed:`, `Consequence:`,
`Unlocks:`, names, and followers. Informal markers (TBD, TODO, FIXME, ???) outside fences are
warned about.

### Content rule

A stand-in states what the realized file must contain, in notes: facts, constraints, beats,
intent. It must not contain the final text. The checker cannot judge this, so it enforces the
structural proxy: a stand-in has only the declared headings and fields, and the profile caps
the length of free prose per heading (`max_prose_words`, a warning). Quoted sample lines belong
in fences and must be marked as samples.

## Profiles

A profile is data in `profiles/<name>/`. The checker is generic and contains no story
vocabulary.

### `profile.json`

```json
{
  "name": "shortstory",
  "files": [
    {"path": "synopsis.md",  "function": "synopsis",   "order": 1},
    {"path": "outline.md",   "function": "outline",    "order": 2},
    {"path": "character.md", "function": "characters", "order": 3},
    {"path": "misc.md",      "function": "misc",       "order": 4},
    {"path": "work/{slug}.md", "function": "story",    "order": 5}
  ],
  "functions": {
    "characters": {
      "heading": "characters",
      "children": ["character"],
      "required_fields": {"character": ["Wants", "Flaw", "Voice", "Depends on", "Referred by"]}
    }
  },
  "relations": ["appears", "mentions", "sets up", "pays off", "contradicts-if-changed"],
  "limits": {"max_prose_words": 120}
}
```

(The JSON above is illustrative of the shape; the exact schema and the full shortstory
definition are written during implementation and checked by a schema test.)

- `files` is the exhaustive file shape. `{slug}` is replaced by the slug in `PREMISE.md`. A
  `files` entry may declare `count` as `fixed` (named in the tree) so that, for profiles with
  numbered files, the set is closed at generation. Shortstory has only fixed single files.
- **Realization order** is the `order` field. Within one order value, files are realized in
  the sequence given. By default it follows the order the user listed the files in. It is
  independent of dependencies.
- `functions` declares, per file function, its level-1 heading type, its child heading types,
  and required fields per heading type.
- `relations` is the list of accepted link relation words.

### Other profile files

| File | Content |
|---|---|
| `questions.md` | the Premise questions, grouped; each marked `required` or `deferrable` |
| `structures.md` | reference structures with when each fits (genre, length, tone), and what each implies for the outline |
| `quality.md` | clichés and low-quality marks: a searchable list (phrases, patterns, habits) and a judgment checklist |
| `lint.json` | the searchable items as patterns with a label, a note, and where they apply (narration only, dialogue allowed, anywhere) |

### The `shortstory` profile

File shape: `synopsis.md`, `outline.md`, `character.md`, `misc.md`, `work/<slug>.md`.

Structures (each with genre fit and length guidance): Freytag's arc, a compressed three-act
form, in medias res, kishōtenketsu, the story spine, and the single-scene or vignette form.

Premise questions cover at least: genre; intended audience and publication target; target
length; tone; point of view and tense; the central situation or premise; ending shape (open,
closed, ironic, reversal); characters the user wants to fix now; recurring images, themes or
motifs; real or fixed events, places or facts to weave in; what the user wants to avoid.

`quality.md` lists clichés and low-quality marks for short fiction, for example: openings on
waking up, on weather, or with a mirror description; dream endings; "it was all a story";
telling emotion through generic physiological clichés (a shiver down the spine, a breath not
known to be held); adverb-propped dialogue tags; characters who only explain; coincidence
that resolves the plot; names that carry no work; an ending that restates the theme. The full
list is written during implementation.

## Checker

`wrist_check.py` is generic over a profile. The profile is read from `PREMISE.md` front
matter, with `--profile` as an override.

### Commands

| Command | Behavior |
|---|---|
| `check` | grammar, profile shape, links, bidirectionality, unknown rules, `PREMISE.md` rules; exits non-zero on errors; `--lenient` downgrades missing fields to warnings |
| `unknowns` | open decisions grouped by kind, each once, with followers |
| `order` | the profile's realization order; reports dependencies that contradict it; cycles are not an error |
| `status` | per stand-in: pending, realized, stale (stand-in changed since stamp), edited (realized file changed since stamp) |
| `stamp` | records stand-in hash, realized-file hash and date in the sidecar for the given files or `--all` |
| `fix-backlinks` | inserts missing `Referred by:` lines |
| `gate` | lists what blocks the generation, realization or publishing phase; exit 1 when blocked |
| `lint` | scans realized files against `lint.json`; reports hits with file, line and label; advisory, exit 0 |
| `publish` | see Publishing |
| `wrist_mv.py` | moves or renames stand-ins and rewrites links |

### What `check` enforces about the file shape

The "no ambiguity about files realized later" requirement becomes these errors:

- a required file from the profile's shape has no stand-in;
- a stand-in lies outside the profile's shape;
- the story file's name does not match the slug in `PREMISE.md`;
- a typed heading is not declared for the stand-in's function, or lacks a required field;
- a link targets a missing file or heading, or lacks its backlink.

### `PREMISE.md`

Front matter: `profile:`, `title:`, `slug:`, `author:`, `language:`, optional `trim:` and `font:`, `questions_generation`, `questions_realization` and `questions_publishing` (each `done` once that phase's questions were asked), and `review_done: yes`. The body
lists each profile question with the user's answer or an `*UNKNOWN*:`. The slug must be a
file-friendly form of the title. `check` validates that every `required` question has an answer
or an unknown. Its unknowns join the tree agenda and `unknowns` output.

### Stamps

`wrist/.stamps` is a JSON sidecar: for each stand-in, the stand-in hash, the realized file's
hash and the stamping date. Realized files carry no header or marker. `status` reports `stale`
when the stand-in hash differs from the stamp, and `edited` when the realized file hash does.

## Workflow (SKILL.md)

SKILL.md loads the grammar reference, then drives the phases.

1. **Premise.** Ask which profile; load its `questions.md`; run the question phase (one topic
   at a time, deferrable questions may become unknowns); write `PREMISE.md`.
2. **Generation.** Run a question phase; read `structures.md` and `quality.md`; choose a
   structure from the premise and record the choice as an unknown with a `Proposed:` unless
   the user stated it; write every stand-in in the profile's shape; copy the applicable
   quality rules into each stand-in's `Rules:`; run `fix-backlinks`, then `check` until clean;
   hand back the agenda: blocking unknowns, proposals to accept, and the realization order.
3. **Realization.** Run a question phase; realize files in profile order; for each, read its
   stand-in and the stand-ins it depends on, write the file at the mirrored path, and run
   `stamp`; run `lint` and fix hits that are not deliberate; do a review pass against the
   judgment checklist in `quality.md` and record it done; run `status` to confirm.
4. **Publishing.** Run a question phase (trim size, font, front matter, cover, author line);
   run `publish`.

A stand-in changed after realization is realized again, and its dependents are reviewed.

## Publishing

`publish` builds from the `work/` files, in the profile's order, with metadata from
`PREMISE.md`.

- **Preflight:** checks that `pandoc` and `typst` are on the path and that the gates pass. If a
  tool is missing it stops before building and prints the install step for the platform.
- **EPUB:** pandoc, with wrist's stylesheet, a title page, and metadata (title, author,
  language, identifier). The output is validated structurally where tooling allows.
- **PDF:** pandoc into a typst template with book typography: justified text, hyphenation,
  widow and orphan control, running heads, chapter or section openers, page numbers, and
  embedded fonts.
- **Output:** `output/<slug>.epub` and `output/<slug>.pdf`. The stand-in tree, stamps and
  `PREMISE.md` are never included.
- **Verified here:** pandoc and typst are not installed on the development machine. The preflight
  path is fully tested. The real build is tested only where the tools exist and is skipped
  otherwise. End-to-end publishing must be run once on a machine with the tools before cycle 1
  is called done.

## Testing

- The skel test suite is carried over and renamed. Tests for removed behavior are deleted with
  it, not rewritten.
- A fake two-heading profile runs through `check`, `order` and `status` to prove the checker
  has no story vocabulary.
- The shortstory profile is validated by a schema test; its `lint.json` patterns are each
  tested against a positive and a negative sample.
- A complete sample shortstory tree (stand-ins plus realized files) is the integration fixture:
  `check` clean, `status` fully realized, `lint` runs, and `publish` hits the preflight path.
- Gate failures each have a test asserting the blocker message.

## Roadmap (not in cycle 1)

Fixed by the user; the profile format must hold them.

**novel.** Structures from several popular sources (Save the Cat!, three-act, hero's journey,
and more conventional sources), with structural differences by genre.
`synopsis.md`, `outline.md`, `character.md`, `misc.md`, and `work/`: `forward.md`,
`prologue.md`, `chapter-<number>.md`, `afterward.md`, `index.md`. Forward, prologue, afterward
and index exist only when the premise says so; the chapter count is fixed at generation.

**screenplay.** Structures used in older and modern films. `synopsis.md`, `outline.md`,
`character.md`, `misc.md`, and `work/act-<number>.md`.

**poem.** A poetry grammar used to generate poem structures. `structure.md` and
`work/<slug>.md`.

This implies profile support for optional files and numbered file families whose count is fixed
in the tree. Cycle 1's `files` schema reserves `optional_if` and `family` keys for these but
does not implement them.

## Open decisions

*UNKNOWN* markers are not used in this document; these are the choices made without explicit
user instruction, to confirm during review:

1. Python 3.10 has no TOML parser, so profiles use JSON.
2. The `--profile` flag overrides `PREMISE.md`.
3. `lint` is advisory and never fails a build.
4. The relation-word list is per profile and an unlisted word is a warning.
5. The review pass is recorded as a `review_done:` flag in `PREMISE.md` front matter.
6. The `max_prose_words` cap is a warning, not an error.
7. `order` does not group dependency cycles; it reports only dependencies that contradict the profile order.
8. The kept skel tests were not carried over verbatim: they were fused to the undo-system code fixture, so the behavior they covered was re-tested against the-lamp example.
