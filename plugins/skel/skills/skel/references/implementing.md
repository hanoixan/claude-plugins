# Implementing from a Skel tree

During development, `skel/` is the implementation plan. Every stand-in becomes exactly one file at the mirrored path. The links tell you what must exist first and what you might break.

## Before writing any code

1. Run `skel_check.py check skel/`. Fix the tree, not the code, until there are no errors. A broken link or a missing backlink means the plan itself is inconsistent.
2. Run `skel_check.py unknowns skel/`. It lists the open decisions by kind:
   - **Blocking** unknowns change an interface, a schema, or a file's existence. Ask the user about these before implementing the affected file, every place that follows the decision, and anything that depends on them. Present each with its consequence and what it unlocks, so the user can answer efficiently.
   - **Local** unknowns affect only a function body, such as a tuning constant, and each carries a `Proposed:` value. For those already in the tree when you start, implement the proposal only after the user has accepted it; they may accept all proposals in one answer. Then record the choice in the stand-in and remove the unknown.
3. If any stand-in is abstract (`.code`, `.data`, `.iac`), adapt it first; see `abstract-systems.md`.
4. Run `skel_check.py batches skel/` to get the build plan. Each batch lists units that can be built once the earlier batches exist. A unit is a stand-in plus the stand-ins that name it in `unit:`, such as a header and its source. Units flagged as a cycle should be implemented together, and a cycle is often a sign that an interface should be extracted. Mention it to the user. A cycle can also appear only because files were joined into one unit; `order` gives the same dependencies file by file and shows whether the files themselves form one.
5. Follow the batches. Build each one so that it compiles and the tests listed in it pass before you start the next. A test appears in the first batch where everything it depends on exists, which can be several batches after the unit it covers; build it there. The manifests listed above the batches (`CMakeLists.txt`, `package.json`, a `Makefile`) are created with the first batch, covering only what exists, and extended with each later batch.
6. Commit `skel/` before you start, and again after each batch, so the plan and the code can be compared at any point.

## Realizing one stand-in

For each file in order:

1. Re-read its stand-in, plus the stand-in sections it `Depends on`. Fragment links point at the exact symbols. Also skim its `Referred by` entries so you know which callers' expectations you must satisfy.
2. Generate the file at the mirrored path (`skel/a/b.py.skel.md` becomes `a/b.py`), and follow the structure exactly:
   - Each `# module` becomes the file. Each `## class` becomes a class. Each `### function` becomes a method and each `## function` a free function. Each `## symbol` becomes a constant, type, or enum.
   - Use the names in the headings unchanged.
   - Make `Inputs` and `Returns` the signature. `State changes` say which side effects are allowed; perform no others. `Access` decides visibility (public or private, exported or not).
   - Handle each listed failure mode explicitly.
   - Treat prose guidance as implementation instructions.
3. Write nothing about skel into the file: no header comment pointing at the stand-in, no hash. The link is the mirrored path. Keep docstrings short and derived from the stand-in. Don't paste the whole spec; the stand-in stays the source of intent.
4. Write tests from the stand-in. Every failure mode and every `State changes` statement is a test case, and data `## Schema` blocks become validation fixtures.
5. When a file (and, for code, its tests) matches the stand-in, stamp it: `skel_check.py stamp skel/ --root . a/b.py` writes `stamp: source <hash>, stand-in <hash>` into the stand-in's front matter: a hash of the file's exact bytes and a hash of the stand-in (which leaves the stamp line out). A stamp records your claim that the two agree. It checks nothing, so stamp one file at a time, and only what you have just brought in step. `--all` is for adopting stamps on a tree whose files already match. Code, data and infrastructure files are all stamped; generated files and abstract stand-ins are not.
6. Run `skel_check.py status skel/ --root .` to track progress. A file you have finished belongs under Implemented, with nothing of yours under Stale, Edited, Diverged, Unstamped, or Names not found in code.

## When implementation reveals something

Don't let code and skel drift. The skel is updated first:

- **A new dependency** means you add `Depends on:` to the stand-in, then run `fix-backlinks --write`.
- **A new file** means you write its stand-in before writing it.
- **A changed contract** means you update the stand-in, then follow its `Referred by:` links and check each referrer's assumptions. This check is the main payoff of bidirectional links, so don't skip it.
- **A new unknown** means you add a formal `*UNKNOWN*:` with its `Kind:`. If it is blocking, stop and ask. If it is local, which includes anything you would otherwise just decide, write your choice as its `Proposed:`, build to that proposal, and leave the marker in place. The user accepts or changes it from your report; a rejected proposal means that code is redone.
- **A resolved unknown** means you replace it with the decided specification and delete the declaration and every follower of it.

Rerun `check` after every batch of skel edits.

## When a stand-in or its file changes after stamping

The stamp holds two hashes, so `status` can tell which side moved:

| Group | What changed | Work order |
|---|---|---|
| **Stale** | the stand-in | Verify the stand-in, then bring the file in step with it, then stamp. |
| **Edited** | the file | Bring the stand-in in step with what the file now does (or revert the file), then stamp. |
| **Diverged** | both | Reconcile the two by hand, then stamp. |

A new backlink, a reflow or the stamp line itself does not change the stand-in hash; any other edit to the stand-in does. Any change to the file's bytes changes the source hash, a formatter run included.

When a stale file is a unit's primary, `status` names the unit's other files beside it, because a changed contract usually means work in the whole unit. An edited file is a change made outside the skel: treat it as a new decision, so update the stand-in first and follow its `Referred by:` links as in the section above. To see what changed in a stand-in:

```bash
git diff <last commit where code and skel agreed> -- skel
```

## Old `Spec:` headers

Trees stamped before skel 3 carry the stamp in a `# Spec: skel/<path>.skel.md @ <hash>` header comment in the code. `status` lists such files under **Legacy**. Run `skel_check.py stamp skel/ --root . --migrate` once: for each header whose hash still matches its stand-in, it writes the new stamp into the stand-in and deletes the header line from the file, keeping every other byte. A header whose hash no longer matches, that has no hash, that names another stand-in, or that shares its line with code is left and reported; settle those files, remove the header by hand, and stamp them. `--migrate` exits non-zero while anything is left.

## Existing code

`status` lists code and IaC files that have no stand-in. To bring existing code under Skel, write stand-ins that describe what the code does, mark undocumented behavior as unknowns rather than guessing intent, and link dependencies. A `Depends on:` can also point directly at an existing file outside `skel/` when that file is out of scope.

## Reporting to the user

After each implementation batch, report in this shape:

1. **Decisions needed:** blocking unknowns that remain or that this batch raised, and what each blocks.
2. **Proposals to accept or change:** local unknowns, each with its proposal, saying which ones this batch was built to.
3. **What was built:** which batches and files were realized, the test results, any cycles that `batches` flagged, and anything `status` still lists under Stale, Unstamped, or Names not found in code.
4. **Changes to the plan:** every stand-in you changed and why, including contract changes that rippled to referrers.

The report lists no choice that is not in the tree. If you made a choice the stand-ins did not dictate, it is in the tree as an unknown with a `Proposed:` before it appears in the report.
