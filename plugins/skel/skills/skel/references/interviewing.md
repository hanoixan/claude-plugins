# Interviewing the user

Every question skel asks the user goes through an interview round: open questions while gathering intent, the
unknowns at the end of a draft, blocking unknowns before and during building, adaptation questions for an abstract
system, and role or pairing questions from `infer-roles`. A round records each question, its choices and the
answer in `skel/.interviews.md`, and marks the choice the user is predicted to take with `*`, from concerns the user
has rated in `skel/.interview-weights.md`. Both files are committed with the tree.

Run the script by its full path, as in `SKILL.md`'s Tools section (`SKILL_DIR` is the folder holding `SKILL.md`):

```bash
python3 "SKILL_DIR/scripts/interview.py" parse skel
```

`--by NAME` names the person answering; it defaults to `git config user.name`. If that is not set, ask the user
their name once and pass it on every command for the rest of the session.

## A round

1. **Draft it** in `skel/.interview-round.md`. If `.gitignore` does not list `skel/.interview-round.md`, add it.
   Start the file with `# skel interview round` and number its questions from `Q1`:

   ```text
   # skel interview round

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

   - Each unknown is one question, the local ones included. Give it 2 to 4 choices. Its `Proposed:` is the choice
     whose label ends `(Recommended)`; a blocking unknown with no proposal gets the one you would recommend.
   - `header:` is the short label shown with the question (12 characters at most); `select:` is `single` or `multi`.
     Keep ` · ` out of the header and `**` out of labels.
   - Annotate every choice now, before anything is asked: `concern:` is one sentence, the main worry the user would
     have if they took it; `raises:` and `addresses:` are `<tag> <severity>` pairs, severity 1 (minor), 2 (real) or
     3 (major). Every choice raises at least one concern; `addresses: none` is allowed. Use the tags in
     `.interview-weights.md` (or `references/interview-tags.md` before that file exists); write `NEW:<tag>` only
     when nothing fits. Judge choices against the `## Principles` in `skel/SYSTEM.md` when it has them.
   - The draft holds the round's state. If the conversation is compacted or interrupted, continue from it.
   - If `parse` warns that records in `.interviews.md` are not annotated (a log written by hand), annotate them
     before the round, without looking at their answers: give a subagent only those questions with the `<sel>` and
     `*` marks removed, and add the lines it returns. With no subagent, annotate from such a stripped copy yourself
     and say in the report that those annotations may not be blind.

2. **Map tags and rate concerns:** run `python3 "SKILL_DIR/scripts/interview.py" concerns skel`.
   - For each tag with no concern, decide whether an existing concern covers it
     (`python3 "SKILL_DIR/scripts/interview.py" tag skel NEW:offline C10`) or it needs a new one
     (`... tag skel NEW:offline --new "offline use" "the system works without a network."`).
   - Ask the user to rate each concern they have not rated, four per question set, 0 to 10: offer 10 (decisive), 7,
     4 and 1, and say that any value can be typed. Use the concern's name and meaning in the question. Store the
     answers: `python3 "SKILL_DIR/scripts/interview.py" rate skel C10=10 C8=1`. These rating questions are not
     logged.

3. **Predict:** `python3 "SKILL_DIR/scripts/interview.py" predict skel`. It marks each question's predicted choice
   with `*` and writes `prediction:`, `concern-only:` and, on a question that touches a trade-off the user has gone
   against before, `<probe>` and `probes:`. It refuses an unannotated choice, an unmapped tag or an unrated concern,
   and names the command that fixes each.

4. **Ask** the questions in draft order. Copy each question, label and description from the draft word for word:
   the log records the draft, so anything reworded when asked is not what the log says was asked. To change the
   wording, edit the draft and run `predict` again before asking.
   - With a multiple-choice tool (AskUserQuestion in Claude Code): four questions per call; the predicted choice's
     label starts with `* `; `(Recommended)` stays in its label; the predicted choice's description ends with
     `(predicted, lead N)`, N being the `gap` from `prediction:`.
   - In plain chat: number the questions, letter the choices, show the same marks, and accept answers like
     `1b, 2a, 3: <text>`.

5. **Record:** `python3 "SKILL_DIR/scripts/interview.py" record skel --answers "Q1=2, Q2=Other, Q3=none"`.
   - Answers are choice numbers in draft order (`Q4=1+3` for several on a multi-select question), `Other` for a
     typed answer, or `none` when the user declines.
   - For a typed answer, first add it to that question in the draft as `- **Other**: <the user's words>` with its
     own `concern:`, `raises:` and `addresses:` lines, map any new tag, then record.
   - `record` writes `<sel>`, marks a `<tracer>` where the answer differs from the stated-ratings prediction, numbers
     the questions after the log's last, appends the round to `.interviews.md` and deletes the draft.

6. **Apply** the answers to the tree as you would any decision: write the decided text in place of each unknown and
   delete it and its followers, then run `skel_check.py check skel`. A declined question leaves its unknown open.

7. **Report** in a few lines: what `record` printed (each answer, new tracers and their trade-offs), the hit rates
   from `python3 "SKILL_DIR/scripts/interview.py" hits skel`, which model predicted, and, once there is a fit, the
   weights `python3 "SKILL_DIR/scripts/interview.py" fit skel` shows as moved, with its warnings. Never present a
   fitted weight that carries an overfit warning as the user's preference.

Every question is still asked in this version, however confident the prediction.

## The files

**`skel/.interviews.md`** is one record per question, in the order asked, written by `record`:

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
axis: C8 effort vs C10 reliability
```

- `<sel>` marks the choice taken and `*` the one predicted; `<sel>` comes first.
- `<tracer>`: the answer went against `concern-only:`, the prediction from the stated ratings alone. `axis:` names
  the concern the answer gained most against the one it gave up most.
- `<probe>` (with `probes:`): when asked, the question touched a trade-off with an earlier tracer.
- `answer: none (declined)` marks a question the user declined.
- Don't edit recorded rounds, apart from adding annotation lines that are missing.

**`skel/.interview-weights.md`** holds the concerns, shared by everyone on the repository, and each person's ratings:

```text
## C10 reliability
meaning: it keeps working, and keeps its data, when something fails.
tags: reliability
rating: 10 · by: Sean Dunn · 2026-10-17
```

The latest `rating:` line per person counts. `tag` and `rate` write it; the first one creates it from
`references/interview-tags.md`.

## How a prediction is made

Each choice scores the sum of weight × severity over what it addresses, minus the same over what it raises, where
a tag's weight is its concern's rating. The highest score is predicted (on a multi-select question, every choice
that scores above zero). Ties go to the recommended choice, then the first.

From five tracers, `predict` fits the weights to the person's answered single-choice questions: a softmax choice
model that also learns how much the person favours the recommended choice, pulled back toward the stated ratings.
Tracers move it most, because they are the answers the stated ratings got wrong. The hit rates count only
predictions logged before each answer, so they are a fair measure of both the stated ratings and the fit.
