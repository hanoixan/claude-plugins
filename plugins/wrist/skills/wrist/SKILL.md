---
name: wrist
description: Write a prose work (short story, with novel, screenplay and poem to follow) in four phases - premise, generation, realization, publishing. A tree of prose stand-ins under wrist/ holds the notes, facts, rules and unknowns for every file before any final text exists; a checker validates links and structure; then the files are realized and published as PDF and EPUB. Use this whenever the user wants to write, plan or outline a short story, novel, screenplay or poem, mentions wrist, .wrist.md files or a wrist/ folder, or wants a long work built from a checked outline instead of drafted freehand.
---

# wrist: writing in four phases

A wrist tree is a set of **stand-ins**: one note file per file the work will contain, under `wrist/`, each ending in `.wrist.md`. A stand-in says what its file must contain (facts, beats, rules, dependencies, unknowns). It never holds the final text. The stand-ins are checked mechanically, and only then is each file written from its stand-in. The target is a work that would stand up to an editor or a prize jury for its intended audience.

```text
wrist/synopsis.md.wrist.md      ->  synopsis.md
wrist/work/the-lamp.md.wrist.md ->  work/the-lamp.md
```

The `references/`, `profiles/`, `assets/` and `scripts/` paths here are relative to this skill's directory, `${CLAUDE_SKILL_DIR}`, not to the user's project.

Read `references/grammar.md` before writing or editing any `.wrist.md`. The checker enforces it. Only the `shortstory` profile exists so far; if the user wants a novel, screenplay or poem, say it is not built yet.

## The four phases

Each phase starts with a **question phase**: ask the user whatever you need so that nothing in the phase is a guess. Ask a few questions at a time in plain language, and offer your recommendation with each. Record the result, then run the phase's gate:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" gate wrist generation   # or realization, publishing
```

A gate prints what blocks the phase. It stays blocked until `PREMISE.md` records that you asked: set `questions_<phase>: done` in its front matter after the questions are answered, never before.

### 1. Premise

1. Ask which profile (`shortstory`). Read `profiles/shortstory/questions.md`.
2. Ask the questions: `required` ones must be answered or become an `*UNKNOWN*:`; `deferrable` ones may be left out. Never invent an answer. A question the user skips on purpose still gets its line, written `- **<id>:** none (skipped on purpose)`, so `check` stops warning about it.
3. Write `wrist/PREMISE.md` from `assets/templates/PREMISE.md`: front matter (`profile`, `title`, `slug`, `author`, `language`) and one `- **<id>:** <answer>` line per question. The slug is a file-friendly form of the title (lower-case words joined by hyphens).

### 2. Generation

1. Question phase, then `questions_generation: done`.
2. Read `profiles/shortstory/structures.md` and `quality.md`. Choose a structure that fits the premise. If the user did not name one, record the choice as an `*UNKNOWN*:` with `Proposed:`; do not present your own choice as settled.
3. Write every stand-in in the profile's shape (five files for a short story), using `assets/templates/`. Create the empty files first so links have targets. Fill in the notes; copy the quality rules that apply into each stand-in's `Rules:`. No stand-in contains final prose: a scene says what it must do, include and avoid, not the sentences.
4. Add `Depends on:` links with a relation word where it helps, for example `(appears)` or `(realizes)`. Do not hand-write `Referred by:` yet. Then:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" fix-backlinks wrist --write
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" check wrist
```

   Repeat until `check` is clean. A missing file is an error: the tree must name every file that will exist.
5. Before handing back, list every choice you made that the user did not state: the action an ending turns on, a name, a number, a setting detail. Each one must already be an `*UNKNOWN*:` in the tree with your choice as `Proposed:`. A choice that appears only in your chat message is a decision made in secret.
6. Hand back the agenda from `python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" unknowns wrist` (blocking decisions need the user before realization; local ones come with a proposal to accept) and `python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" order wrist` (the realization order). List nothing as decided that is not in the tree.

### 3. Realization

1. Question phase (confirm the unknowns are resolved), then `questions_realization: done`. Run `gate wrist realization`.
2. Realize the files in the order `order` prints. For each: read its stand-in and the stand-ins it depends on, write the file at the mirrored path, then stamp it:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" stamp wrist work/the-lamp.md
```

   Follow every `Rules:`, `Must include:` and `Must avoid:`. Separate scenes with a line containing only `* * *`. Do not add a fact the stand-ins do not hold: no new name, object, event, number or backstory. If the text needs one, add it to the scene's `Must include:` first, run `check`, then write it. Never let the text drift from its notes.
3. Craft rules for every file: write for the intended reader; prefer the specific to the general; let action and detail carry feeling; give each speaker a distinct voice; vary sentence length and shape; cut anything the story survives losing; read as the audience would.
4. Run `lint`, fix each hit that is not deliberate, and re-stamp:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" lint wrist
```

5. Do the review pass as its own step, after the text is finished. Reread the story from the first line to the last, then work through the `## Judgment checklist` in `quality.md` and write down what fails. Also check continuity: every number, name, time and fact the story states must agree everywhere it appears, and the text must not contradict itself about what a character sees or says. List each concrete detail in the text that no stand-in holds, and add it to a stand-in or cut it. Fix what fails, re-stamp, and only then set `review_done: yes` in `PREMISE.md`.
6. `python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" status wrist` must show every file realized. A stand-in changed after its file was realized shows as stale: realize the file again.

### 4. Publishing

1. Question phase: ask the author line, the title page text, the trim size (`trim:` a Typst paper name such as `a5` or `us-trade`) and the font if not the default. Record them in `PREMISE.md`, then set `questions_publishing: done`.
2. Run `gate wrist publishing`, then:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" publish wrist
```

   It needs `pandoc` and `typst`; if either is missing it prints the install steps and stops. Output is `output/<slug>.epub` and `output/<slug>.pdf`. See `references/publishing.md`.

## Writing good stand-ins

- **Notes, not text.** If a stand-in could be pasted into the book, it is too long. The checker warns when free prose under a heading passes the profile's word limit.
- **Put intent where it is used.** Rationale and rules go at the level they apply to.
- **No ambiguity about files.** Every file the work will contain has a stand-in before realization starts; the profile fixes the shape.
- **Your choices are unknowns.** Anything the user did not state is an `*UNKNOWN*:` with your choice as `Proposed:`.

## Tools

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" check WRIST_DIR [--lenient] [--profile NAME]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" unknowns WRIST_DIR [--json]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" order WRIST_DIR [--json]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" status WRIST_DIR [--root .]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" stamp WRIST_DIR PATH... | --all [--root .]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" fix-backlinks WRIST_DIR [--write]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" gate WRIST_DIR generation|realization|publishing
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" lint WRIST_DIR [--root .]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" publish WRIST_DIR [--root .]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_mv.py" WRIST_DIR OLD NEW | --map map.txt [--dry-run]
```

All scripts use only the Python standard library. `check` exits non-zero on errors. `--root` defaults to the folder that holds `wrist/`.
