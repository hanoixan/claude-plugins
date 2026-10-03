---
name: wrist
description: Author, validate, and implement Wrist specifications. Wrist is a code-shaped, prose-only design format where every project file gets a stand-in at wrist/PATH/FILE.EXT.wrist.md describing its modules, classes, functions, data schemas, or infrastructure, with bidirectional `Depends on:`/`Referred by:` links and formal `*UNKNOWN*:` markers. Use this skill whenever the user mentions Wrist, .wrist.md files, or a wrist/ folder. Also use it when the user wants to plan or architect a codebase before coding, turn a design, PRD, or spec into an implementation plan shaped like the code, describe a reusable subsystem (undo, auth, sync, plugins, job queues) independent of language or platform, or implement or update code from an existing wrist/ tree. Prefer it over writing a linear spec or task list whenever the user wants architecture-first planning that an agent will implement.
---

# Wrist specifications

A Wrist tree is an intermediate design that has the **shape of the final code** but is written entirely in prose. `wrist/` mirrors the project root, and each file in it is a stand-in for one file that will be generated in its place:

```text
wrist/src/net/client.py.wrist.md   ->  src/net/client.py
wrist/data/regions.json.wrist.md   ->  data/regions.json
wrist/infra/main.tf.wrist.md       ->  infra/main.tf
```

Inside a code stand-in, headings follow the code (`# module:` > `## class:` > `### function:`). Every unit states its inputs, returns, state changes, ownership, and access. Every dependency is a link, and every link has a backlink, so an implementer can see both what a unit needs and who relies on it. Anything not yet known is a formal `*UNKNOWN*:` rather than a guess. The tree then works as an implementation plan an agent can follow file by file with little ambiguity.

## When you are doing which job

| Job | Read |
|---|---|
| Author a wrist tree for a concrete project | `references/grammar.md` (always), then the workflow below |
| Describe a language- and platform-neutral system | `references/grammar.md`, `references/abstract-systems.md`, `assets/examples/undo-system/` |
| Implement code from an existing wrist tree, or keep code and wrist in sync | `references/implementing.md` |

Read `references/grammar.md` before writing or editing any `.wrist.md`. It is the normative grammar, and the checker enforces it.

The `references/`, `assets/`, and `scripts/` paths in this skill are relative to the skill's own directory, `${CLAUDE_SKILL_DIR}`, not to the project you are working in.

## Core rules (summary)

- **Naming:** use `wrist/<mirrored path>/<file>.<ext>.wrist.md`. The extension sets the kind: code, data, iac, or resource. Abstract systems use the placeholders `.code`, `.data`, and `.iac`.
- **Front matter:** every stand-in starts with `role: product | test | manifest`. `unit:` names the stand-in this one is built with, as a source file names its header. `untested: <reason>` records why a product unit has no test.
- **Five basic questions in every file:** `Referred by:` (what depends on this), `Depends on:` (what this depends on), `Required:`, `Failure modes:`, and unknowns (`*UNKNOWN*:` entries or `Unknowns: none`). Write `none` explicitly rather than omitting a field.
- **Code hierarchy and fields:** a module needs Owns and Access. A class needs Inputs, State changes, Owns, and Access. A function needs Inputs, Returns, State changes, and Access. Prose of any kind is welcome at every level.
- **Links:** `Depends on: [Symbol](./rel/path.ext.wrist.md#class-symbol)` must be matched by `Referred by: [Symbol](./back/path.ext.wrist.md)` in the target, and vice versa.
- **Data:** state `Source:`, give a `## Schema` with a fenced block, and if the data is generated, add a `## Generation` section with the pipeline, tool links, and a development usage fence.
- **Storage is infrastructure-as-code:** each store is a `## resource:` in an iac stand-in, with `Data requirements:` and its consumers listed as `Referred by:`.
- **Unknowns:** use `*UNKNOWN*: [name] <what>. Kind: blocking | local. Proposed: <...>. Consequence: <...>. Unlocks: <...>.` Declare a decision once and mark the other places it affects with `*UNKNOWN*: Follows [name]. Consequence: <...>.` Anything you choose that the user did not state is an unknown with a `Proposed:`. Never present your own choice as settled.
- **Fences** always carry a language tag. Include sample code only when code is the clearest way to state a contract.

## Authoring workflow

1. **Gather intent.** Read whatever the user has: a design doc, a PRD, existing code, or a conversation. Note decisions and open questions. Don't resolve open questions yourself; they become unknowns. A choice you make to keep the design moving is an unknown too, with your choice as its `Proposed:`.
2. **Write `wrist/SYSTEM.md`** from `assets/templates/SYSTEM.md`. Include scope, glossary, global decisions, and entry points.
3. **Lay out the file tree first.** List every file the project will contain and create empty stand-ins at mirrored paths. Links need targets, and seeing the whole tree early exposes structural problems (god modules, misplaced responsibilities) while they are still cheap to fix. Then give every stand-in its role, and pair each source file with its header:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" infer-roles wrist --write
   ```

   It never writes a role or a unit it is unsure of; it lists those with a `?`. Set them by hand in the front matter, and ask the user about any you cannot settle. Run it again after step 4: a source whose name only begins with its header's, or whose header is in another folder, is paired once it has a `Depends on:` link to that header.
4. **Fill each stand-in top-down** from the templates in `assets/templates/`, keeping the front matter step 3 wrote. Start with the module purpose and traits, then classes, then functions. Write `Depends on:` links at the most specific level that is true. Don't hand-write `Referred by:` yet.
5. **Walk each dependency as its caller.** For every `Depends on:` link, read the target and confirm that it declares each function, type and callback this unit's prose says it uses, that the mutability and lifetime it offers fit, and that every type the tree defines and the prose names has its own `class:` or `symbol:` heading. Add what is missing to the target now. Each gap found here is one an implementer would otherwise fill by changing the plan.
6. **Generate the backlinks** and review them:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" fix-backlinks wrist --write
   ```

   Then go through the inserted lines and fix the symbol text where a better name exists.
7. **Validate** until the tree is clean:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" check wrist            # --lenient while drafting
   ```
8. **Hand back the agenda.** Run `wrist_check.py unknowns wrist` and `wrist_check.py batches wrist`, and report in this shape:
   1. **Decisions needed before implementation:** the blocking unknowns, each with its consequence, what it unlocks, and its proposal if it has one.
   2. **Proposals to accept or change:** the local unknowns, each with its proposal. The user may accept them all in one answer.
   3. **Build batches:** the output of `batches`: which units can be built together and in what order, and which manifests grow with each batch.
   4. **Code that now trails the plan:** the Stale group from `wrist_check.py status wrist --root .`. Leave this out when nothing is implemented yet.

   The report lists no choice that is not in the tree. If you are about to write "I decided" or "I assumed", add the unknown first, then report it under 1 or 2.

## Writing good stand-ins

- **Specify contracts, not code.** The test is whether two competent implementers working from this stand-in would produce code that is interchangeable at every boundary the links describe. If they wouldn't, the stand-in is underspecified. If the stand-in dictates loop structure, it is overspecified.
- **Put intent where it's used.** Rationale, rejected alternatives, and guidance for the implementing agent ("keep this allocation-free; it's on the render path") go in prose at the level they apply to, not in a separate document.
- **Prefer the narrowest level.** A dependency used by one method is linked from that method, so the backlink names the method and change impact stays precise.
- **Make failure modes concrete:** say what triggers each one and what the expected handling is. They become the test list.
- **Frame persistence as infrastructure.** If a function reads or writes state that outlives the process, it links to an iac resource.
- **Use names the language allows.** A heading's name becomes an identifier, so it cannot be a keyword of the target language (`delete`, `class`, `namespace`), and it follows that language's naming style.
- **Give tests their seams.** If a test must set the clock or make a write fail, declare that hook on the unit, in its `Inputs:`.
- **Keep unknowns honest.** An unknown with a clear consequence and unlock is more useful than a confident guess, because it tells the user exactly which decision to make. The same goes for your own choices: a proposal the user can veto is worth more than a decision they never saw.

## Tools

All scripts use only the Python standard library.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" check WRIST_DIR [--lenient]   # grammar, traits, links, bidirectionality, SYSTEM.md links
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" unknowns WRIST_DIR [--json]   # open decisions by kind, each once, with followers
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" order WRIST_DIR [--json]      # dependency sort (not a build plan), cycles grouped
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" status WRIST_DIR --root .     # implemented / stale / unstamped / pending / abstract; names missing from code
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" stamp WRIST_DIR --root . PATH... | --all   # record your claim that code matches its stand-in; checks nothing
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" fix-backlinks WRIST_DIR [--write]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" infer-roles WRIST_DIR [--write]   # propose role: and unit: front matter
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" batches WRIST_DIR [--json]    # buildable batches of units; manifests set aside
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_mv.py" WRIST_DIR OLD NEW | --map map.txt [--dry-run]  # move or rename with link rewriting
```

The reference files and templates name the scripts by filename alone (`wrist_check.py check wrist/`). Run them by the full paths shown here.

`check` exits non-zero on errors, so it can run in CI or pre-commit to keep the tree consistent. It never reads code: `status` is what reports code that has drifted from the tree, and it always exits 0. `--lenient` reports missing fields as warnings, so a draft can be checked for structure and links before every field is filled in. Broken links and bad names still fail.
