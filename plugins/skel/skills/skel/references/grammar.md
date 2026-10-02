# Skel grammar (normative)

This is the full grammar for `.skel.md` files. `skel_check.py check` enforces every rule marked **(checked)**.

## Contents
1. Layout and naming
2. File kinds
3. Common traits: the five basic questions
4. Field syntax
5. Unknowns
6. Links and bidirectionality
7. Code files
8. Data files
9. Persistent storage and infrastructure-as-code
10. Resource files
11. Sample code and fences
12. SYSTEM.md

---

## 1. Layout and naming

- Every file the project will contain gets a stand-in at `skel/<path>/<file>.<ext>.skel.md`. **(checked)**
- `skel/` mirrors the project root. `skel/src/net/client.py.skel.md` stands in for `src/net/client.py`, and that file is generated in that place during development.
- The extension is part of the stand-in name, because the extension decides the file kind and tells the implementer what to produce. **(checked)** Conventional extensionless files such as `Dockerfile`, `Makefile`, or `Procfile` are allowed as `skel/Dockerfile.skel.md`.
- Language-neutral specifications use the placeholder extensions `.code`, `.data`, and `.iac` until a language and platform are chosen; see `abstract-systems.md`. The checker reports these as abstract.
- Plain `.md` files in `skel/` that are not `.skel.md` (normally just `SYSTEM.md`) are context, not stand-ins. Apart from the unknowns and links in `SYSTEM.md`, they are not checked.

## 2. File kinds

The kind is inferred from the implementation extension:

| Kind | Extensions (non-exhaustive) | Level-1 heading |
|---|---|---|
| code | py ts tsx js go rs java kt cs cpp c h swift rb php dart … and `.code` | `# module: <name>` |
| data | json jsonl yaml yml toml csv tsv xml parquet avro proto … and `.data` | `# data: <name>` |
| iac | tf tfvars hcl bicep sql, Dockerfile … and `.iac` | `# infrastructure: <name>` |
| resource | anything else (png, svg, css, html, md, fonts …) | `# resource: <name>` |

You can override the inference with YAML front matter as the very first lines of the file:

```yaml
---
kind: iac
---
```

Use the override for files whose extension is ambiguous, for example `docker-compose.yml` or `k8s/deployment.yaml` (which would otherwise be data), or a `.sql` file that is seed data rather than schema.

Each file has exactly one level-1 heading, and it must match the kind. **(checked)**

## 3. Common traits: the five basic questions

Every stand-in, whatever its kind, answers these five questions somewhere in the file. **(checked)**

| Question | Field(s) |
|---|---|
| What depends on this? | `Referred by:` (one or more) |
| What does this depend on? | `Depends on:` (one or more) |
| Is this always required? | `Required:` |
| Known failure modes | `Failure modes:` |
| Known unknowns that must be answered | one or more `*UNKNOWN*:` entries, or `Unknowns: none` |

Put `Required:` and `Failure modes:` under the level-1 heading so they describe the whole file. You can also add `Failure modes:` to individual functions or resources, and you are encouraged to.

`Depends on:` and `Referred by:` attach to the heading they appear under. Place them at the most specific level that is true. If only `save()` touches the store, the link belongs under `### function: save`, not under the module. The file-level answer is the union of all of them.

Explicit "nothing" values are allowed and preferred to omission, because they record that the question was considered:

```markdown
- **Depends on:** none
- **Referred by:** none known
- **Unknowns:** none
```

Write `Required:` as one of these:

- `always`
- `conditional — <condition>`
- `optional — <what is lost without it>`

## 4. Field syntax

A field is a line that begins (optionally after a list bullet) with a label and a colon. All of these forms are accepted:

```markdown
Inputs: a path and a read mode
- Inputs: a path and a read mode
- **Inputs:** a path and a read mode
- **Inputs**: a path and a read mode
```

The canonical form is `- **Label:** value`. Values can continue in prose or sub-bullets on the lines that follow.

The recognized labels are `Depends on`, `Referred by`, `Inputs`, `Returns`, `State changes`, `Owns`, `Access`, `Required`, `Failure modes`, `Unknowns`, `Source`, and `Data requirements`.

Fields belong to the nearest typed heading above them (`module:`, `class:`, `function:`, `symbol:`, `data:`, `infrastructure:`, `resource:`). Untyped sub-headings such as `#### Notes` or `## Schema` do not change ownership, so fields under `#### Edge cases` inside a function still belong to that function.

## 5. Unknowns

Only describe what is known. Anything that isn't known is declared as a formal unknown, never guessed:

```markdown
*UNKNOWN*: <what is unknown>. Consequence: <what goes wrong or stays blocked while it is unknown>. Unlocks: <what can be specified or built once it is known>.
```

- The marker `*UNKNOWN*:` is exact. The checker also accepts `**UNKNOWN**:`.
- An unknown can stand on its own line, inside a bullet, or as a field value (`- **Returns:** *UNKNOWN*: ...`).
- The checker warns when an unknown has no `Consequence:` or `Unlocks:` clause, because an unknown without consequences can't be prioritized.
- The checker warns about informal markers (`TBD`, `TODO`, `FIXME`, `???`, or a bare `UNKNOWN`) outside code fences. Convert them to formal unknowns.
- Place an unknown at the level it affects. A wire-format unknown belongs on the function that encodes it, not on the module.
- Never add detail that contradicts an open unknown. If the database engine is unknown, don't write PostgreSQL-specific SQL in a sample; write the unknown instead.

`skel_check.py unknowns skel/` prints the inventory. That list is the agenda for the next conversation with the user.

## 6. Links and bidirectionality

### Syntax

```markdown
Depends on: [<symbol depended upon>](<relative path to dependency's .skel.md>)
Referred by: [<symbol or item that refers to this>](<relative path to referring .skel.md>)
```

- Paths are relative to the file containing the link. **(checked: target exists)**
- To point at a specific symbol, append a heading fragment. Fragments are GitHub-style slugs of the heading text: lowercase, with punctuation other than `-` and `_` removed, and spaces turned into `-`. So `### function: save_all` becomes `#function-save_all`. **(checked: a fragment must match a heading in the target)**
- Name the symbol in the link text using dotted qualification where it helps, for example `[UndoHistory.push](./history.code.skel.md#function-push)`. A dotted name must agree with the heading the fragment points at: `UndoHistory.push` has to land on a `function: push` under `class: UndoHistory`, not on a free function of the same name. A module-qualified name (`history.push` for a free function in `module: history`) is also accepted. **(checked, warning)**
- Use one link per line. A block form is also accepted:

  ```markdown
  - **Depends on:**
    - [Command](./command.code.skel.md#class-command)
    - [Transaction](./transaction.code.skel.md#class-transaction)
  ```

### What a link may target

| Target | Allowed? | Backlink required? |
|---|---|---|
| another `.skel.md` in `skel/` | yes | **yes** |
| same file (`#fragment`) | yes | no |
| `http(s)://` URL, for an external library or service | `Depends on` only | no |
| an existing project file outside `skel/` (code that already exists) | `Depends on` only | no |
| a non-`.skel.md` file inside `skel/` | no (warning) | no |

### The bidirectionality rule **(checked)**

If A has `Depends on: [x](B)`, then B must have a `Referred by:` linking to A. Likewise, if B has `Referred by: [y](A)`, then A must have a `Depends on:` linking to B. The pair is checked at file granularity: the symbol text and fragments may differ, but both ends must exist.

This is what lets an implementer change B and immediately see every contract that might break. Write the `Depends on:` side as you author. Then run `skel_check.py fix-backlinks skel/ --write` to insert the missing `Referred by:` lines, and review the inserted symbol names.

A `Referred by:` with no matching `Depends on:` is an error that is not auto-fixed. It claims something about another file, so decide which side is wrong.

## 7. Code files

### Hierarchy **(checked)**

```text
# module: <module name>              exactly one, level 1
## class: <class name>               level 2, under the module
### function: <method name>          level 3, under a class
## function: <function name>         level 2, a free function under the module
## symbol: <name>                    level 2 or 3: a constant, type alias, enum, or global
```

Deeper typed nesting (for example a function inside a function) is not allowed. Describe closures and inner helpers in prose under their owner. Untyped headings (`#### Algorithm`, `## Notes`) may appear anywhere for organization.

### Prose

Any level may contain any prose that explains what it does and why. Treat prose as the place for intent, rationale, rejected alternatives, and the agent prompts that should guide implementation (for example, "Prefer clarity over cleverness here; this runs once per session."). The fields below are the minimum, not the whole spec.

### Required fields per level **(checked)**

| Level | Inputs | Returns | State changes | Owns | Access |
|---|---|---|---|---|---|
| module | | | | ✔ | ✔ |
| class | ✔ (construction) | | ✔ (instance state and invariants) | ✔ | ✔ |
| function | ✔ | ✔ | ✔ | | ✔ |
| symbol | | | | | ✔ |

These fields may also appear where they are not required, for example `Owns:` on a function that allocates a resource.

The fields mean:

- **Inputs** are the parameters (name, meaning, type if known, constraints), plus any ambient input read (environment variables, global config, the clock). For a class, they are the construction inputs.
- **Returns** is the result and what it means, including error or empty results. Write `nothing` when there is no result.
- **State changes** are mutations visible outside the call: fields, files, network, caches, events emitted. Write `none` for pure functions. For a class, state the invariants that hold between calls.
- **Owns** is what this unit is the single source of truth for, or is responsible for releasing: data, resources, lifecycles.
- **Access** is how other code is expected to reach it: public or internal, singleton or injected, thread or async context, and call ordering constraints.

`Inputs` and `Returns` describe meaning and constraints first and types second. Give types when they are known, and use an `*UNKNOWN*:` when the type depends on an open decision.

## 8. Data files

```markdown
# data: <name>

<prose: what this data is for>

- **Source:** hand-authored | generated | external — <detail>
- **Required:** ...
- **Failure modes:** ...
- **Depends on:** ...
- **Referred by:** ...

## Schema
<fenced block in the most convenient notation for the format>

## Generation        (required if Source says generated)
<the full pipeline, links to tools, and development usage in a fenced block>
```

- `## Schema` **(checked)** must contain at least one fence. Use the most convenient notation: JSON Schema or annotated JSONC for JSON, a header row plus a column table for CSV, a `.proto` excerpt, a YAML example with comments, or a DDL fragment.
- `## Generation` **(checked when generated)** must contain at least one link to the tool or code that produces the data and at least one fence showing development usage (the command to regenerate, fixture flags, sample sizes). Describe every stage from source to file, including where the inputs come from, how often it runs, and how it is validated.
- Readers of the data link to it with `Depends on:`, and the data file lists them with `Referred by:`.

## 9. Persistent storage and infrastructure-as-code

Frame all storage as infrastructure-as-code. Databases, buckets, queues, caches, and even "a JSON file in the user's app-data directory" are resources that some IaC-kind stand-in declares.

- Code that reads or writes storage has a `Depends on:` link to the IaC stand-in's resource heading.
- When the IaC tool isn't decided, use a placeholder `.iac` file and record the choice as an unknown.
- For purely local storage with no real IaC tool, an `.iac` stand-in still records the requirements, so the decision is visible and reviewable.

IaC files use this structure:

```markdown
# infrastructure: <name>

- **Required:** ...
- **Failure modes:** ...
- **Depends on:** ...          (providers, accounts, other stacks)
- **Referred by:** ...         (optional at file level; required per resource)

## resource: <name>
<prose>
- **Data requirements:** shape, volume, retention, consistency, latency, access pattern, and security/PII class
- **Referred by:** [<consumer symbol>](<path>)     (every consumer, at least one)
```

Each `## resource:` **(checked)** needs `Data requirements:` and at least one `Referred by:`. The data requirements are the contract. A resource with no consumers is either dead or a missing link, and the checker warns when it sees `Referred by: none known`.

## 10. Resource files

Images, fonts, stylesheets, templates, and similar assets use `# resource: <name>` plus the five traits. Describe format, dimensions or variants, provenance and licensing, and how the resource is produced. If it is generated, follow the data-file `## Generation` convention.

## 11. Sample code and fences

- Every fence opens with three or more backticks (or tildes) followed by a language tag. **(checked)** Use `text` for plain text.
- Include sample code only when code is the clearest way to state a contract, such as a signature, a wire format, a tricky algorithm, or an API usage example. A skel file is a specification, not a draft implementation.
- Fenced content is ignored for headings, fields, links, and unknowns, so examples can show skel syntax safely.

## 12. SYSTEM.md

`skel/SYSTEM.md` is the one non-stand-in file. It holds context that belongs to no single file:

- purpose and scope
- glossary
- global decisions (language, platform, frameworks), each either stated or recorded as an unknown
- cross-cutting concerns (logging, error policy, concurrency model)
- an entry-point index linking to the main stand-ins

Use the same `*UNKNOWN*:` convention in it. The checker counts its unknowns and checks that its links resolve **(checked)**; it does not apply the stand-in grammar to it. `skel_mv.py` keeps its links up to date.
