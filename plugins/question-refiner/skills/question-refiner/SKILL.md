---
name: question-refiner
description: Ask the user questions as recorded rounds. Before asking, annotate each choice with the concerns it raises and addresses, predict the answer from the person's ratings, and log the answer, so later predictions improve. Use this skill whenever you are about to ask the user anything, in the question tool or in plain chat, for any plugin or task; when a hook refuses an AskUserQuestion call; when a SessionStart note reports skel 3.1.0 interview data to move; or when the user asks about their interview history, hit rates or weights.
---

# Asking through question-refiner

Every question you ask the user goes through a round: whatever plugin or task it comes from, and whether it is asked
with the question tool or in plain chat. A round records each question, its choices and the answer, and marks the
choice the user is predicted to take with `*`, from concerns the user has rated. A hook refuses an AskUserQuestion
call whose questions have not been predicted or exempted, and names the step that is missing.

Run the script by its full path (`SKILL_DIR` is the folder holding this file):

```bash
python3 "SKILL_DIR/scripts/refiner.py" parse
```

Its files live in `.question-refiner/` at the git root (the working directory outside a repository); `--dir DIR`
overrides that. `--by NAME` names the person answering; it defaults to `git config user.name`. If that is not set,
ask the user their name once and pass it on every command for the rest of the session. History is kept per name: a
changed `user.name` starts a new history, so pass `--by` with the old name to keep using the old one.

If `refiner.py` cannot run (no `python3`; the gate then says so), ask directly, as if this plugin were not installed,
and tell the user once that question-refiner needs `python3`.

## Questions with no trade-off

A confirmation, a menu of next steps, or asking for a name trades no concern against another, so predicting it
teaches nothing. Exempt it, then ask it:

```bash
python3 "SKILL_DIR/scripts/refiner.py" exempt --question "Merge or open a PR?" --reason "a menu, no trade-off"
```

The line goes to `.question-refiner/exempt.md` and the gate lets that question through for 10 minutes. Ask it with
exactly the text you exempted. Anything with real alternatives the user might weigh differently is not exempt.

## First use: choosing domains

The concerns come from `references/concerns.md`, a catalog tagged by domain: software, infrastructure, product,
fiction, nonfiction, research, planning. Before the first round, infer the domains that fit the work and confirm
them. This question is exempt, with the reason "choosing domains", since there are no weights to predict from yet.

1. Ask one single-select question, "Use the inferred domains: software, product?", with **Use these (Recommended)**
   and **Change them**. When the inference is right, that is one click.
2. Only on **Change them**: ask two multi-select questions in one call, the first four domains and then the other
   three (the tool allows four options per question). End the labels of the inferred domains with "(inferred)": the
   tool cannot pre-check a box, so the label is the pre-fill.
3. In plain chat: one message listing the seven domains, `[x]` on the inferred and `[ ]` on the rest, ending "reply
   ok, or name what to add or drop".

Then create the weights:

```bash
python3 "SKILL_DIR/scripts/refiner.py" domains add software product
```

It copies every concern those domains list, once each. Later work in another domain adds its concerns the same way;
numbers already given never change. `domains` with no arguments lists the domains in use.

## A round

1. **Draft it** in `.question-refiner/round.md`. The first time, add `.question-refiner/round.md` to `.gitignore`.
   Start the file with `# question-refiner round` and number its questions from `Q1`:

   ```text
   # question-refiner round

   ## Q1
   Where is undo history kept between sessions?
   header: History · select: single
   - **Not kept (Recommended)**: history lives in memory and ends with the session.
       concern: a crash loses every step the user could have undone.
       raises: reliability 2
       addresses: impl-effort 2, privacy 1
   - **A file beside the document**: survives a restart; one more format to version.
       concern: another file format to keep compatible forever.
       raises: impl-effort 2, privacy 1
       addresses: reliability 3
   ```

   - Each decision is one question with 2 to 4 choices. When the asking plugin has a proposal (skel's `Proposed:`),
     it is the choice whose label ends `(Recommended)`; otherwise mark the one you would recommend.
   - `header:` is the short label shown with the question (12 characters at most); `select:` is `single` or `multi`.
     Keep ` · ` out of the header and `**` and ` | ` out of labels.
   - `stakes: high · <reason>` marks a high-stakes question: its choices are hard to reverse, expensive,
     outward-facing (published, sent, shared) or security-sensitive. It is asked first and never handed off.
   - `after: Q<n>` marks a question that depends on question n's answer; it stays right after that one.
   - Annotate every choice now, before anything is asked: `concern:` is one sentence, the main worry the user would
     have if they took it; `raises:` and `addresses:` are `<tag> <severity>` pairs, severity 1 (minor), 2 (real) or
     3 (major). Every choice raises at least one concern; `addresses: none` is allowed. Use the tags in
     `.question-refiner/weights.md`; write `NEW:<tag>` only when nothing fits. Judge choices against the project's
     stated principles where it has them: `## Principles` in `skel/SYSTEM.md`, `CLAUDE.md`, a design document.
   - The draft holds the round's state. If the conversation is compacted or interrupted, continue from it.
   - If `parse` warns that records in `interviews.md` are not annotated (a log written by hand), annotate them before
     the round, without looking at their answers: give a subagent only those questions with the `<sel>` and `*`
     marks removed, and add the lines it returns. With no subagent, annotate from such a stripped copy yourself and
     say in the report that those annotations may not be blind.

2. **Map tags and rate concerns:** run `python3 "SKILL_DIR/scripts/refiner.py" concerns`.
   - For each tag with no concern: if `concerns` names a catalog concern for it, pull that in
     (`python3 "SKILL_DIR/scripts/refiner.py" tag NEW:pacing --catalog`); if a concern in the weights covers it, map
     it there (`... tag NEW:offline C10`); otherwise create one
     (`... tag NEW:offline --new "offline use" "the system works without a network."`). New concerns are expected as
     work reaches new ground.
   - Ask the user to rate each concern they have not rated, four per question set, 0 to 10: offer 10 (decisive), 7,
     4 and 1, and say that any value can be typed. Use the concern's name and meaning in the question. These rating
     questions are exempt, with the reason "rating concerns". Store the answers:
     `python3 "SKILL_DIR/scripts/refiner.py" rate C10=10 C8=1`.

3. **Predict:** `python3 "SKILL_DIR/scripts/refiner.py" predict`. It marks each question's predicted choice with
   `*`, adds the person as `by:` on the meta line (`record` refuses anyone else), and writes `prediction:`,
   `scores:`, `concern-only:`, `round-id:` and, on a question that touches a trade-off the user has gone against
   before, `<probe>` and `probes:`. It refuses an unannotated choice, an unmapped tag or an unrated concern, and names
   the command that fixes each. The first `predict` after an upgrade backfills `scores:` on older records.
   - On a single-select question, the prediction line gives `p`: the calibrated chance the user takes the predicted
     choice (see "How a prediction is made").
   - It sorts and renumbers the round: high-stakes questions first, then those never handed off (multi-select,
     probes, the audit), then the rest, each lowest `p` first, with `after:` questions kept behind theirs.
   - `handoff: p 91% ≥ 85` marks a question the user's handoff point covers: single-select, not high-stakes, not a
     probe, `p` at least the threshold, once the user has answered 20 questions. The default is 85; the user sets it
     with `/question-refiner-auto`, and 100 is off. Never run `auto` with a number yourself: only the user chooses
     how much is answered for them. `python3 "SKILL_DIR/scripts/refiner.py" auto`, with no number, shows it.
   - `audit: yes` marks one such question when few recent answers sit above the threshold. Ask it like any other.
     Don't say which question is the audit: the user answering it as usual is the point.

4. **Ask in order, offer the handoff, review.** Ask the questions in draft order. Copy each question, label and
   description from the draft word for word: the log records the draft, and the gate matches the question text
   exactly. Ask a probed question without its `<probe>` mark. To change the wording, edit the draft and run
   `predict` again before asking.
   - A high-stakes question is asked first, with `<!> ` before its text, so the user sees the stakes.
   - With a multiple-choice tool (AskUserQuestion in Claude Code): four questions per call; the predicted choice's
     label starts with `* `; `(Recommended)` stays in its label; the predicted choice's description ends with
     `(predicted, lead N)`, N being the `gap` from `prediction:`.
   - When questions would remain after a call and every one of them could be handed off (single-select, not
     high-stakes, not a probe, not the audit), the call's last slot is the handoff question instead: exempt, with
     the reason "handoff", "Answer the remaining N yourself? About X.X expected wrong.", X.X being the sum of
     (100 − p)/100 over them, with the choices **Answer the rest** and **Keep asking**. **Answer the rest** ends
     `(Recommended)` when every remaining question has `handoff:`. Choosing it earlier is the user's call.
   - After **Answer the rest**, review: exempt and ask one single-select question, "Use the predicted answers for
     these N questions?", with the reason "reviewing handed-off answers" and the choices **Use these
     (Recommended)** and **Change some**. List each handed-off question, its predicted answer, and the recommended
     answer when different, in the **Use these** option's description, in the option's preview, or in a message
     that ends the turn before the question is asked. On **Change some**: With one handed-off question, **Change
     some** means asking it; with two to four, ask which as one exempt multi-select question, one option per
     question; with more than four, split them across multi-select questions in one call, four options at most
     each, all exempt. Ask the ones chosen normally.
   - In plain chat: number the questions, letter the choices, show the same marks, and accept answers like
     `1b, 2a, 3: <text>`. Offer the handoff as "reply `rest` to let me answer the remaining N", and the review as
     a list ending "reply ok, or the numbers to change".

5. **Record:** `python3 "SKILL_DIR/scripts/refiner.py" record --answers "Q1=2, Q2=Other, Q3=none"`.
   - Answers are choice numbers in draft order (`Q4=1+3` for several on a multi-select question), `Other` for a
     typed answer, or `none` when the user declines.
   - `Q3=kept` records a handed-off answer the user kept in the review, as the prediction, with `handoff: kept`.
     A handed-off question the user changed is recorded by its choice number and named in `--handoff "Q3"`, which
     writes `handoff: changed`. Neither counts as a human answer in the hit rates; a changed one trains the fit.
     `Q3=auto`, from rounds drafted before 1.2.0, means kept.
   - For a typed answer, first add it to that question in the draft as `- **Other**: <the user's words>` with its
     own `concern:`, `raises:` and `addresses:` lines, map any new tag, then record.
   - `record` writes `<sel>`, marks a `<tracer>` where the answer differs from the stated-ratings prediction, numbers
     the questions after the log's last, appends the round to `interviews.md` and deletes the draft. It refuses a
     round already in the log; if it says so, delete the left-over draft.

6. **Apply** the answers where the questions came from, as that plugin or task says (skel writes each decision in
   place of its unknown). A declined question stays open there.

7. **Report** in a few lines, starting with the tally line, which `record` prints last
   (`python3 "SKILL_DIR/scripts/refiner.py" tally` shows it at any time): what `record` printed (each answer, new tracers and their trade-offs), the hit rates
   from `python3 "SKILL_DIR/scripts/refiner.py" hits`, which model predicted, and, once there is a fit, the weights
   `python3 "SKILL_DIR/scripts/refiner.py" fit` shows as moved, with its warnings. Never present a fitted weight
   that carries an overfit warning as the user's preference.

Every question is asked unless the user hands it off, and every handed-off answer is shown to the user to review
before it is applied. The tally line reads like `Predictions: 41 of 50 recent (82%), 160 of 190 all (84%) · lapse
18% · handoff at 85 (suggested: 87)`.

## The files

**`interviews.md`** is one record per question, in the order asked, written by `record`:

```text
## Q14
<tracer> Where is undo history kept between sessions?
header: History · round: 3 · select: single · asked: 2026-10-17 10:42:11 -0400 · by: Sean Dunn
- * **Not kept (Recommended)**: history lives in memory and ends with the session.
    concern: a crash loses every step the user could have undone.
    raises: reliability 2
    addresses: impl-effort 2, privacy 1
- <sel> **A file beside the document**: survives a restart; one more format to version.
    concern: another file format to keep compatible forever.
    raises: impl-effort 2, privacy 1
    addresses: reliability 3
prediction: Not kept (Recommended) · score 12 · gap 4 · model: fitted+rec
concern-only: Not kept (Recommended)
axis: C10 reliability vs C8 effort
round-id: 3f91df49
```

- `<sel>` marks the choice taken and `*` the one predicted; `<sel>` comes first.
- `<tracer>`: the answer went against `concern-only:`, the prediction from the stated ratings alone. `axis:` names
  the concern the answer gained most against the one it gave up most.
- `<probe>` (with `probes:`): when asked, the question touched a trade-off with an earlier tracer.
- `answer: none (declined)` marks a question the user declined. `handoff: kept` or `handoff: changed` marks a
  handed-off answer; `answer: confirmed` and `auto:`, from before 1.2.0, read as kept.
- `stakes:`, `after:` and `audit: yes` stay as drafted; `after:` is renumbered into the log.
- `scores:` holds each offered choice's score when predicted, the input to calibration; `· backfilled` marks scores
  computed later for an older record, from earlier records only.
- `p 81%` on the prediction line is the predicted choice's calibrated probability, on single-select questions.
- `round-id:` is the same on every question of a round. `record` refuses a draft whose round is already logged.
- Don't edit recorded rounds, apart from adding annotation lines that are missing; `predict` and `backfill` add
  `scores:` to older records, the one other edit.

**`weights.md`** holds the domains, the concerns, shared by everyone on the repository, and each person's ratings:

```text
domains: software

## C10 reliability
meaning: it keeps working, and keeps its data, when something fails.
tags: reliability
rating: 10 · by: Sean Dunn · 2026-10-17
```

A `threshold: 80 · by: Sean Dunn · 2026-10-24 · calibrated` line after `domains:` is a person's handoff point; a
line without `calibrated` was set before 1.2.0 and reads as the default, 85. The latest `rating:` and `threshold:`
line per person counts. `domains add` creates the file; `tag` and `rate` change it.

**`exempt.md`** is one line per exempt question: when, by whom, the question and why. `hits` and `fit` never read it.

`interviews.md`, `weights.md` and `exempt.md` are committed; `round.md` is not.

## How a prediction is made

Each choice scores the sum of weight × severity over what it addresses, minus the same over what it raises, where
a tag's weight is its concern's rating. The highest score is predicted (on a multi-select question, every choice
that scores above zero). Ties go to the recommended choice, then the first.

From five tracers, `predict` fits the weights to the person's answered single-choice questions: a softmax choice
model that also learns how much the person favours the recommended choice, pulled back toward the stated ratings.
Tracers move it most, because they are the answers the stated ratings got wrong. The hit rates count only
predictions logged before each answer, so they are a fair measure of both the stated ratings and the fit.

`p` is calibrated: the probability of the predicted choice is (1 − ε) × softmax(β × scores) plus ε shared over
the offered choices and a typed answer. ε, the lapse rate, is the share of answers the scores do not explain; β
scales the scores. Both are fitted to the user's human answers (not handed-off ones) from the logged scores,
starting from a pessimistic prior, so `p` means how often such a prediction has been right.
`python3 "SKILL_DIR/scripts/refiner.py" calibration` shows `p` against the hit rate by range;
`python3 "SKILL_DIR/scripts/refiner.py" backfill` fills in older records' scores, which `predict` also does. The
tally's suggestion is the highest threshold the user's answers back: at least 10 answers at or above it, right at
least that often at a 95% lower bound.

## Moving skel 3.1.0 data

skel 3.1.0 kept this loop's files in its tree, as `.interviews.md` and `.interview-weights.md`. When the store has
no log yet, a SessionStart note names any such folder; ask the user, as an exempt question with the reason
"migrating data", whether to move it. On yes:

```bash
python3 "SKILL_DIR/scripts/refiner.py" import skel
```

It copies the files into `.question-refiner/`, keeps the originals, and writes `.interview-moved.md` beside them so
nothing asks again. It refuses a store that already has a log or weights. Until the data is moved, `domains add`
refuses. If the user says not now, exempt that session's questions with the reason "migrating data deferred", and
ask again next session. Use `domains add ... --fresh` only when the user chooses a fresh start: it starts new
weights and marks the old files as set aside for good.
