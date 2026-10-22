---
name: arch-report
description: Build a self-contained, two-page HTML explainer for one agentropy-guard ledger item, with a block diagram and a sequence diagram, and publish it. Use when the user says yes to an architecture note, or asks for one.
---

# The architecture report

`GUARD` is `python3 "SKILL_DIR/../../scripts/guard.py"` (`SKILL_DIR` is the folder holding this file).

1. Gather: `GUARD item get ID`, `GUARD graph --json`, and the evidence files.
2. Copy `template.html` (beside this file) to `.agentropy-guard/reports/ID.html` and fill every `{{SLOT}}`:
   - `TITLE`, and `WHY`: one sentence on why the user should care;
   - `BLOCK_DIAGRAM`: where it lives in the system, drawn as `diagram-guide.md` says, the item's components in the
     accent colour, agent-negotiated interfaces dashed;
   - `SEQUENCE_SECTION`: a `<section>` with a sequence diagram when behaviour over time matters, else empty;
   - `CONSEQUENCES`: 3 to 5 `<li>` items, "what this means for you";
   - `ORIGIN`: how it got this way (agent decision? when? which files?);
   - `EVIDENCE`: `<li>` items of file paths and commits;
   - `COUNTERMOVE_SECTION`: a `<section>` on how to change it, when there is a countermove, else empty;
   - `GENERATED`: today's date and the item id.
   Keep it to about 900 words plus the two diagrams; no external requests (inline CSS and SVG only).
3. `GUARD pages .agentropy-guard/reports/ID.html`. Over two pages (exit 2): trim the prose, never the diagrams, and
   check again. "skipped" means no headless Chrome: say the page count was not checked.
4. Publish it as a private artifact when the Artifact tool is available, and give the user the link; otherwise give
   the file path. Then `GUARD told ID --level report_generated --report .agentropy-guard/reports/ID.html`.
