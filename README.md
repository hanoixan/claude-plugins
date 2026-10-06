# hanoixan-claude-plugins

A Claude Code plugin marketplace. Six plugins.

Four are small. Three of them are built around the same observation: **a skill body
reaches the model once, when it is invoked, and then sits at a fixed point in the
conversation while everything after it competes for attention.** Guidance that has to hold
for a whole session cannot live there, so each puts it in a hook that re-states the short
form on every turn, at the end of the context window, where recency works in its favour.
economy-of-words and plan-batch-execution pair that hook with a skill holding the long-form
reasoning; ask-questions is the hook alone. The fourth, do-next, is a skill with no hook: you
invoke it deliberately, so there is nothing to keep alive between turns.

The fifth, [skel](#skel), is a different kind of thing: a design format with its own
grammar, checker and templates, loaded when you ask for it. The sixth, [wrist](#wrist), is
skel adapted for writing: the same stand-in tree, checker and unknowns, applied to a short
story, novel, screenplay or poem instead of a codebase, and carried through to a published
PDF and EPUB.

---

## Install

Add the marketplace once:

```
/plugin marketplace add hanoixan/claude-plugins
```

Then install whichever plugins you want:

```
/plugin install economy-of-words@hanoixan-claude-plugins
/plugin install do-next@hanoixan-claude-plugins
/plugin install plan-batch-execution@hanoixan-claude-plugins
/plugin install ask-questions@hanoixan-claude-plugins
/plugin install skel@hanoixan-claude-plugins
/plugin install wrist@hanoixan-claude-plugins
```

### Requirements

`bash` and `jq` on `PATH`. Every hook exits quietly if `jq` is missing, so a plugin
degrades to its skill rather than erroring.

skel has no hooks and needs `python3` instead, for its two scripts. They use only the
standard library.

wrist has no hooks either. Its scripts need `python3` (standard library only); publishing
also needs `pandoc` 3.2+ and `typst` 0.12+, and wrist prints install steps if either is
missing.

---

## The plugins at a glance

| Plugin | What it changes | Hooks | Skill | Per-turn cost |
| --- | --- | --- | --- | --- |
| [economy-of-words](#economy-of-words) | How replies are written | `UserPromptSubmit` | yes | 191 words |
| [do-next](#do-next) | Working a prompt queue | none | yes | none |
| [plan-batch-execution](#plan-batch-execution) | How many subagents get dispatched | `UserPromptSubmit`, `PreToolUse`, `PostToolUse` | yes | 19 words |
| [ask-questions](#ask-questions) | Asking instead of assuming | `UserPromptSubmit` | no | 10 words |
| [skel](#skel) | Designing a codebase before writing it | none | yes | none |
| [wrist](#wrist) | Writing a story, novel, screenplay or poem from a checked outline | none | yes | none |

---

## economy-of-words

Strips filler, framing and self-appraisal out of replies.

**What ships**

| Piece | Role |
| --- | --- |
| `/economy-of-words` skill | The full reference: reply shape, banned phrases, a typography budget, rewrites, a red-flags checklist. 812 words, loaded only when invoked. |
| `UserPromptSubmit` hook | A 191-word condensation, injected every turn. |

**Why the phrase list looks so specific**

It is not generic writing advice. It was derived by counting tics across one real
870-reply Claude Code session:

| Tic | Occurrences |
| --- | --- |
| em-dashes | 1407 |
| bold spans | 1163 |
| "Now the…" transitions | 330 |
| "actually" | 102 |
| "Let me check…" narrations | 78 |
| trailing "which is exactly why…" clauses | 66 |

**Scope**

The rules govern replies to the user. Content written into files follows the
conventions of that file and its audience — a typography budget of one bold span is
right for a chat reply and wrong for a README.

```
/plugin install economy-of-words@hanoixan-claude-plugins
```

---

## do-next

Works through a queue of prompts kept in `./NEXT.md`. It confirms the set, asks every
prompt's questions and writes every prompt's plan up front, then runs the prompts one at a
time, archiving each to `./DONE.md` the moment it is finished.

```
/do-next                  one prompt
/do-next 3                the top three prompts, in order
/do-next section          every prompt in the next section
/do-next section 2        every prompt in the next two sections
/do-next section Cleanup  every prompt in the section named Cleanup
```

Anything else as the argument (a zero, a decimal, an unknown word, a section name that
matches nothing or more than one section) makes it stop and ask rather than guess. If the
queue holds fewer prompts than asked for, it takes what is there and says so.

**The queue format.** Prompts are separated by a line whose trimmed content is exactly `--`.
Not `---`, which is a horizontal rule and a frontmatter fence. A line starting with `#`
divides the queue into named sections; sections do not nest, and the name is a label, never
part of a prompt.

```
# Groundwork
Do the first thing.
--
Do the second thing.
It can span many lines.

# Cleanup
Do the third thing.
```

Both files live at the project root (the current directory).

**The run**

| Step | What happens |
| --- | --- |
| Confirm | Every prompt in the set is shown, grouped by section, and you approve it. This is the only approval in the run. |
| Ask | Every prompt's clarifying questions are asked in one sitting, cumulatively: prompt 3's questions take into account what prompts 1 and 2 will do. Nothing is changed yet. |
| Plan | A plan for every prompt (its text, your answers, the steps, how it is verified) is written to `./.claude/do-next-run.md` before any work starts, so a compaction or crash does not lose it. |
| Run | One prompt at a time, in order, each re-checked against the tree as it then stands. |
| Stop on trouble | A failing test, a plan that no longer fits, a missing dependency or work far larger than planned stops the run and asks you, unless this run told it to press through, in which case it records each deviation in the scratch file. A stopped prompt and everything after it stay queued. |
| Archive | Each finished prompt is appended to `DONE.md` under a timestamp read from the system clock, then removed from `NEXT.md`; a finished section's `#` line moves with its last prompt. |
| Report | What was done, prompt by prompt, and how much of the queue remains. |

**What a batch buys.** You answer once and can then leave: one confirmation and one round of
questions instead of one per prompt. It does not buy parallelism. Prompts run in order, each
finished and archived before the next starts, and a queue interrupted half way says exactly
what is left.

The scratch file is deleted when the run completes and kept when it stops, so you can see
where it halted. Add `.claude/do-next-run.md` to your `.gitignore`.

```
/plugin install do-next@hanoixan-claude-plugins
```

---

## plan-batch-execution

Turns a written plan into the fewest subagent dispatches its dependency graph allows.

**The three rules**

1. A dependency line `T1 → T2 → T3` is **one** dispatch, not three.
2. `k` same-shape independent edits are **one** dispatch, whatever `k` is.
3. A leaf — docs, a changelog, a constant — never gets its own dispatch.

A single chain of five tasks or fewer is not dispatched at all; it runs inline. Gates (full
suite plus review) go at chain hand-off points plus one final, rather than after every task.
The skill ends with a worked example (`worked-example.md`).

**How the three hooks divide the work**

| Hook | Fires | Does |
| --- | --- | --- |
| `UserPromptSubmit` | every turn | Names the skill and the schedule file it must produce, before the dispatch count is chosen. |
| `PreToolUse` on `Agent` | each dispatch | Reads `.claude/plan-batch-schedule.md` and shows it as the approval prompt. |
| `PostToolUse` on `Agent` | after a dispatch runs | Records the approval. |

**Why approval is recorded after the fact.** `PreToolUse` cannot see your answer. Only
a dispatch that actually ran proves the gate was cleared, so a dispatch you decline
never marks a schedule approved.

**One decision, not one per slot.** The marker is a hash of the schedule file. Approve
once and that schedule's remaining dispatches run unprompted; edit the schedule and you
are asked again, because the plan you approved has changed.

**A missing schedule is reported, not ignored.** If no schedule file exists, the gate
says the skill was skipped and presents the default one-agent-per-task shape for
approval. The expensive default becomes visible instead of silent. A one-off subagent
unrelated to any plan can simply be approved.

```
/plugin install plan-batch-execution@hanoixan-claude-plugins
```

> Add `.claude/.plan-batch-approved` to your `.gitignore`. It is per-machine approval
> state, not part of the plan.

---

## ask-questions

One line, injected on every turn:

```
Ask questions to resolve all ambiguities, concerns, and knowledge gaps.
```

No skill body. No qualifying clause about when a question is worth asking — that clause
would read as permission to skip it, so the instruction stays unconditional and the
judgement stays where it belongs.

Pairs naturally with `economy-of-words`, which was where this line originally lived
before it was split out for doing a different job than concision.

```
/plugin install ask-questions@hanoixan-claude-plugins
```

---

## skel

Designs a codebase in prose before any of it is written. A `skel/` folder mirrors the
project root, and each file in it is a stand-in for one file that will be generated in
its place:

```
skel/src/net/client.py.skel.md   ->  src/net/client.py
skel/data/regions.json.skel.md   ->  data/regions.json
skel/infra/main.tf.skel.md       ->  infra/main.tf
```

Inside a code stand-in the headings follow the code: module, then class, then function.
Every dependency is a link, and every link has a backlink in its target, so a reader
sees both what a unit needs and what relies on it. Anything not yet decided is a formal
`*UNKNOWN*:` entry that states its kind, its consequence and, where the author has one,
a proposed default, rather than a guess. The finished tree is an implementation plan an
agent can follow file by file.

**What ships**

| Piece | Role |
| --- | --- |
| `/skel` skill | The workflow for three jobs: authoring a tree, describing a system independent of language and platform, and implementing code from a tree. 1678 words. |
| `references/` | The normative grammar, plus a guide each for abstract systems and for implementing. Read only for the job at hand. |
| `scripts/skel_check.py` | The checker, below. |
| `scripts/skel_mv.py` | Moves or renames stand-ins and rewrites every link that pointed at them. |
| `assets/templates/` | A starting stand-in for each kind: code, data, infrastructure, and the tree's `SYSTEM.md`. |
| `assets/examples/undo-system/` | A complete abstract tree for an undo system, which passes the checker. |

**The checker**

```
skel_check.py check SKEL_DIR            grammar, required fields, links and their backlinks, SYSTEM.md links
skel_check.py unknowns SKEL_DIR         open decisions, blocking and local, each listed once
skel_check.py order SKEL_DIR            dependency order (what must exist before what)
skel_check.py status SKEL_DIR --root .  implemented, stale (stand-in changed), edited (file
                                        changed), diverged (both), unstamped, legacy,
                                        pending, abstract; names missing from code
skel_check.py stamp SKEL_DIR --root . PATH... | --all
                                        record in each stand-in that it and its file agree:
                                        a hash of each, kept in the stand-in, never in code
skel_check.py stamp SKEL_DIR --root . --migrate
                                        move stamps from old `Spec:` headers into stand-ins
skel_check.py fix-backlinks SKEL_DIR    insert missing `Referred by:` lines
skel_check.py infer-roles SKEL_DIR      propose each stand-in's role and its unit
skel_check.py batches SKEL_DIR          buildable batches of units, manifests set aside
```

`check` exits non-zero on errors, so it can run in CI or a pre-commit hook to keep the
tree consistent. It never reads code; `status` is what reports files that have drifted from
the tree, in either direction.

**Upgrading a tree stamped with skel 2.x.** Stamps now live in the stand-in, with a hash of each side, so
`status` reports both a stand-in that changed (stale) and a file that changed (edited). Run
`stamp --migrate` once to move the old `Spec:` header stamps out of the code. Hand-written
data and infrastructure files now need a stamp too: check each and stamp it.

**Upgrading a tree written for skel 1.x.** `check` now needs a `role:` on every stand-in
and a `Kind:` on every unknown. Run `infer-roles --write` and settle the ones it marks
unsure, add the kinds by hand, and, once the code matches the tree, run `stamp --all`.

No hook. The rules that have to hold are enforced by a checker that can be run at any
point, so nothing depends on the model still remembering them.

```
/plugin install skel@hanoixan-claude-plugins
```

---

## wrist

Writes a story, novel, screenplay or poem in four phases, from a checked outline to a
published PDF and EPUB.

**Based on skel.** wrist began as a copy of [skel](#skel) and keeps its core: a folder that
mirrors the files to be written, one prose stand-in per file, `Depends on:` links with
checked backlinks, formal `*UNKNOWN*:` entries for anything not yet decided, a checker that
runs at any point, and stamps that tell you when a file has drifted from its stand-in. What
changed is the subject. Where skel describes modules, classes and functions, wrist describes
a synopsis, an outline, characters, places and scenes; where skel's tree becomes code,
wrist's becomes prose, verse or a script, written by the model one file at a time.

```
wrist/synopsis.md.wrist.md       ->  synopsis.md
wrist/work/the-lamp.md.wrist.md  ->  work/the-lamp.md
```

A stand-in holds notes, facts, rules and open questions, never the final text. The work is
only written once the stand-ins pass the checker, and it must not add a fact the stand-ins
do not hold.

**The four phases**

| Phase | What happens | Gate |
| --- | --- | --- |
| Premise | The profile's questions, answered or recorded as unknowns, in `wrist/PREMISE.md` | `gate generation` |
| Generation | The stand-in tree: every file the work will contain, with links and the quality rules that apply | `gate realization` |
| Realization | Each file written from its stand-in and stamped, then linted for clichés and reviewed against a checklist | `gate publishing` |
| Publishing | `output/<slug>.pdf` and `output/<slug>.epub`, through pandoc and typst | none |

Each phase opens with a question phase, so nothing in it is a guess, and its gate stays
closed until `PREMISE.md` records that the questions were asked.

**Profiles**

A profile is data: the file shape, the headings and required fields, the premise questions,
reference structures or forms, a list of clichés and marks of low quality, a judgment
checklist, and searchable lint patterns. `shortstory`, `novel`, `screenplay` and `poem` exist.

| Profile | Files | Written as | Published as |
| --- | --- | --- | --- |
| `shortstory` | synopsis, outline, characters, misc, the story | Markdown prose | a story with a byline under its title |
| `novel` | the same registries, one file per chapter, optional forward, prologue, afterward and index | Markdown prose, one chapter at a time, each recording what it `Established:` | a book: title page, front matter, contents, chapters |
| `screenplay` | the same registries, one file per act | Fountain, read by a custom pandoc reader | screenplay layout: Courier, title page, page numbers |
| `poem` | a skeleton and the poem | the skeleton in a poem grammar (PSGv2.1), the poem as plain verse | set verse: line breaks and indentation kept, never reflowed |

The poem profile adds a `verse` command. It parses the skeleton, compares it with the form it
names from a catalog of 13 (sonnets, villanelle, sestina, pantoum, haiku, ballad and others),
and checks the poem against it: stanza and line counts, refrains word for word and sestina end
words are errors, while syllables and rhyme are labelled estimates that never block.

**What ships**

| Piece | Role |
| --- | --- |
| `/wrist` skill | The four phases, the rules for each profile, and how to write a good stand-in. 2113 words. |
| `profiles/` | One folder per profile: `profile.json`, `questions.md`, structures or forms, `quality.md`, `lint.json`. |
| `references/` | The stand-in grammar, publishing, the Fountain dialect, the poem grammar and the verse format. |
| `scripts/wrist_check.py` | The checker, below. |
| `scripts/wrist_mv.py` | Moves or renames stand-ins and rewrites every link to them. |
| `publish/` | Pandoc readers and filters, Typst templates and EPUB stylesheets for each publishing style. |
| `assets/templates/` | Starting stand-ins for each profile. |
| `assets/examples/` | A complete worked example per profile: `the-lamp` (story), `salt-road` (novel), `the-third-bell` (screenplay), `counting` (villanelle). Each passes every gate. |

**The checker**

```
wrist_check.py check WRIST_DIR          grammar, the profile's file shape, links and backlinks, unknowns, PREMISE.md
wrist_check.py unknowns WRIST_DIR       open decisions, blocking and local, each listed once
wrist_check.py order WRIST_DIR          realization order from the profile
wrist_check.py status WRIST_DIR         realized, stale, edited, unstamped, pending
wrist_check.py stamp WRIST_DIR PATH...  record that a file was written from its stand-in
wrist_check.py fix-backlinks WRIST_DIR  insert missing `Referred by:` lines
wrist_check.py gate WRIST_DIR PHASE     what blocks generation, realization or publishing
wrist_check.py lint WRIST_DIR           the profile's searchable clichés in the written work
wrist_check.py verse WRIST_DIR          poem only: the poem against its skeleton
wrist_check.py publish WRIST_DIR        build output/<slug>.pdf and output/<slug>.epub
```

Like skel, wrist has no hook: the rules that have to hold are enforced by the checker and the
gates, so nothing depends on the model still remembering them.

```
/plugin install wrist@hanoixan-claude-plugins
```

---

## Editing a plugin's injected text

Every hook reads `${CLAUDE_PLUGIN_DATA}/<file>.txt` first and falls back to the copy
bundled in the plugin. Copy the bundled file into the plugin's data directory and edit
it there; plugin updates will never overwrite it.

| Plugin | Override file |
| --- | --- |
| economy-of-words | `rules.txt` |
| plan-batch-execution | `pointer.txt` |
| ask-questions | `rules.txt` |

Find the data directory under `~/.claude/plugins/data/<plugin>-<marketplace>/`.

---

## Repository layout

```
.claude-plugin/marketplace.json     the six plugin entries
plugins/<name>/
  .claude-plugin/plugin.json        manifest
  hooks/hooks.json                  hook registrations
  hooks/*.sh                        hook scripts
  hooks/*.txt                       the injected text, editable
  skills/<name>/SKILL.md            the long form
  skills/<name>/references/         skel and wrist: grammar and guides
  skills/<name>/scripts/            skel and wrist: the checker, the mover and helpers
  skills/<name>/assets/             skel and wrist: templates and worked examples
  tests/                            skel and wrist: tests for their scripts
  skills/wrist/profiles/            wrist only: one folder of data per profile
  skills/wrist/publish/             wrist only: pandoc and typst files per publishing style
```

---

## License

MIT License

Copyright (c) 2026 Sean E. Dunn

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
