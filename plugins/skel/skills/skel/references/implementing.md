# Implementing from a Skel tree

During development, `skel/` is the implementation plan. Every stand-in becomes exactly one file at the mirrored path. The links tell you what must exist first and what you might break.

## Before writing any code

1. Run `skel_check.py check skel/`. Fix the tree, not the code, until there are no errors. A broken link or a missing backlink means the plan itself is inconsistent.
2. Run `skel_check.py unknowns skel/`. Sort the unknowns:
   - **Blocking** unknowns change an interface, a schema, or a file's existence. Ask the user about these before implementing the affected file and anything that depends on it. Present them grouped, with each one's consequence and what it unlocks, so the user can answer efficiently.
   - **Local** unknowns affect only a function body, such as a tuning constant. You may implement with a clearly marked, conservative default only if the user agrees. Record the choice in the skel and remove the unknown.
3. If any stand-in is abstract (`.code`, `.data`, `.iac`), adapt it first; see `abstract-systems.md`.
4. Run `skel_check.py order skel/` to get the build order. Dependencies come first. Files in the same step that form a cycle should be implemented together, and a cycle is often a sign that an interface should be extracted. Mention it to the user.

## Realizing one stand-in

For each file in order:

1. Re-read its stand-in, plus the stand-in sections it `Depends on`. Fragment links point at the exact symbols. Also skim its `Referred by` entries so you know which callers' expectations you must satisfy.
2. Generate the file at the mirrored path (`skel/a/b.py.skel.md` becomes `a/b.py`), and follow the structure exactly:
   - Each `# module` becomes the file. Each `## class` becomes a class. Each `### function` becomes a method and each `## function` a free function. Each `## symbol` becomes a constant, type, or enum.
   - Use the names in the headings unchanged.
   - Make `Inputs` and `Returns` the signature. `State changes` say which side effects are allowed; perform no others. `Access` decides visibility (public or private, exported or not).
   - Handle each listed failure mode explicitly.
   - Treat prose guidance as implementation instructions.
3. Add a one-line header comment pointing back to the stand-in, for example `# Spec: skel/a/b.py.skel.md`. Keep docstrings short and derived from the stand-in. Don't paste the whole spec; the stand-in stays the source of intent.
4. Write tests from the stand-in. Every failure mode and every `State changes` statement is a test case, and data `## Schema` blocks become validation fixtures.
5. Run `skel_check.py status skel/ --root .` to track progress.

## When implementation reveals something

Don't let code and skel drift. The skel is updated first:

- **A new dependency** means you add `Depends on:` to the stand-in, then run `fix-backlinks --write`.
- **A new file** means you write its stand-in before writing it.
- **A changed contract** means you update the stand-in, then follow its `Referred by:` links and check each referrer's assumptions. This check is the main payoff of bidirectional links, so don't skip it.
- **A new unknown** means you add a formal `*UNKNOWN*:` and stop to ask if it is blocking.
- **A resolved unknown** means you replace it with the decided specification and delete the marker.

Rerun `check` after every batch of skel edits.

## Existing code

`status` lists code and IaC files that have no stand-in. To bring existing code under Skel, write stand-ins that describe what the code does, mark undocumented behavior as unknowns rather than guessing intent, and link dependencies. A `Depends on:` can also point directly at an existing file outside `skel/` when that file is out of scope.

## Reporting to the user

After each implementation batch, report:

- which files were realized
- which unknowns remain, and which of those block what
- any contract changes that rippled to referrers
- any cycles that `order` found
