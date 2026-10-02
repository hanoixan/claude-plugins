# hanoixan-claude-plugins

A Claude Code plugin marketplace. Five plugins.

Four are small and built around the same observation: **a skill body reaches the model
once, when it is invoked, and then sits at a fixed point in the conversation while
everything after it competes for attention.** Guidance that has to hold for a whole
session cannot live there. Each of those pairs its skill (where the long-form reasoning
belongs) with a hook (which re-states the short form on every turn, at the end of the
context window, where recency works in its favour).

The fifth, [skel](#skel), is a different kind of thing: a design format with its own
grammar, checker and templates, loaded when you ask for it.

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
```

### Requirements

`bash` and `jq` on `PATH`. Every hook exits quietly if `jq` is missing, so a plugin
degrades to its skill rather than erroring.

skel has no hooks and needs `python3` instead, for its two scripts. They use only the
standard library.

---

## The plugins at a glance

| Plugin | What it changes | Hooks | Skill | Per-turn cost |
| --- | --- | --- | --- | --- |
| [economy-of-words](#economy-of-words) | How replies are written | `UserPromptSubmit` | yes | 170 words |
| [do-next](#do-next) | Working a prompt queue | none | yes | none |
| [plan-batch-execution](#plan-batch-execution) | How many subagents get dispatched | `UserPromptSubmit`, `PreToolUse`, `PostToolUse` | yes | 19 words |
| [ask-questions](#ask-questions) | Asking instead of assuming | `UserPromptSubmit` | no | 10 words |
| [skel](#skel) | Designing a codebase before writing it | none | yes | none |

---

## economy-of-words

Strips filler, framing and self-appraisal out of replies.

**What ships**

| Piece | Role |
| --- | --- |
| `/economy-of-words` skill | The full reference: reply shape, banned phrases, a typography budget, rewrites, a red-flags checklist. 812 words, loaded only when invoked. |
| `UserPromptSubmit` hook | A 170-word condensation, injected every turn. |

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

Works through a queue of prompts kept in `./NEXT.md`, one at a time, confirming before
it starts and archiving each finished prompt to `./DONE.md` with a timestamp read from
the system clock.

```
/do-next        one prompt
/do-next 3      the top three, in order
```

**The queue format.** Prompts are separated by a line containing exactly `--`. Not
`---`, which is a horizontal rule and a frontmatter fence.

```
Do the first thing.
--
Do the second thing.
It can span many lines.
```

**What a batch buys.** One confirmation instead of several. It does not buy
parallelism: prompts run in order, each finished and archived before the next starts,
and trouble anywhere stops the batch with the queue left honest about what remains.

Of the four small plugins, this is the one with no hook. The skill is invoked
deliberately, by you, so there is nothing to keep alive between turns.

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

Gates (full suite plus review) go at chain hand-off points plus one final, rather than
after every task.

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
`*UNKNOWN*:` entry that states its consequence, rather than a guess. The finished tree
is an implementation plan an agent can follow file by file.

**What ships**

| Piece | Role |
| --- | --- |
| `/skel` skill | The workflow for three jobs: authoring a tree, describing a system independent of language and platform, and implementing code from a tree. 1114 words. |
| `references/` | The normative grammar, plus a guide each for abstract systems and for implementing. Read only for the job at hand. |
| `scripts/skel_check.py` | The checker, below. |
| `scripts/skel_mv.py` | Moves or renames stand-ins and rewrites every link that pointed at them. |
| `assets/templates/` | A starting stand-in for each kind: code, data, infrastructure, and the tree's `SYSTEM.md`. |
| `assets/examples/undo-system/` | A complete abstract tree for an undo system, which passes the checker. |

**The checker**

```
skel_check.py check SKEL_DIR            grammar, required fields, links and their backlinks
skel_check.py unknowns SKEL_DIR         every open decision, with its location
skel_check.py order SKEL_DIR            build order, dependencies first
skel_check.py status SKEL_DIR --root .  implemented, pending, or code with no stand-in
skel_check.py fix-backlinks SKEL_DIR    insert missing `Referred by:` lines
```

`check` exits non-zero on errors, so it can run in CI or a pre-commit hook to keep the
tree and the code in step.

No hook. The rules that have to hold are enforced by a checker that can be run at any
point, so nothing depends on the model still remembering them.

```
/plugin install skel@hanoixan-claude-plugins
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
.claude-plugin/marketplace.json     the five plugin entries
plugins/<name>/
  .claude-plugin/plugin.json        manifest
  hooks/hooks.json                  hook registrations
  hooks/*.sh                        hook scripts
  hooks/*.txt                       the injected text, editable
  skills/<name>/SKILL.md            the long form
  skills/skel/references/           skel only: grammar and guides
  skills/skel/scripts/              skel only: the checker and the mover
  skills/skel/assets/               skel only: templates and a worked example
```

---

## License

MIT
