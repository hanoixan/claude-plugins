---
name: do-next
description: Use when the user asks to work through a queue of prompts stored in NEXT.md - confirms the set, asks every prompt's questions and codifies every plan up front, then runs them one at a time, archiving each to DONE.md. Takes an optional count of prompts, or a section to take a whole group at once. Also use when the user asks for more of the queue while a run is already in flight - the new prompts join the live run without it losing its place.
---

# do-next

Work through a queue of prompts kept in `./NEXT.md`. Confirm the set before
anything else, ask all of its questions and write all of its plans up front,
then run the prompts one at a time, archiving each to `./DONE.md` as it
finishes.

**Announce at start:** "Using do-next to take the next prompt from NEXT.md."
When taking several, say how many: "Using do-next to take the next 3 prompts
from NEXT.md." When taking a section, name it and give its size: "Using do-next
to take the 'Cleanup' section, 4 prompts, from NEXT.md." When a run is already
live, say so: "Using do-next to add 2 prompts to the run in progress; prompt 2 of
4 is paused at its next step."

**Check for a live run first,** before announcing anything: a run is live when
`./.claude/do-next-run.md` says `state: active` (see "The run file"), or when this
conversation is still in steps 1 to 4 of a run whose file is not written yet. If
a run is live, go to "Adding to a live run" instead of starting a new one, and
announce it that way.

## The argument

`do-next` takes one optional argument, which selects **how much of the queue to
take**. It defaults to one prompt, which is the ordinary behaviour and what you
get when no argument is given.

```
/do-next                  one prompt
/do-next 3                the top three prompts, in order
/do-next section          every prompt in the next section
/do-next section 2        every prompt in the next two sections
/do-next section Cleanup  every prompt in the section named Cleanup
```

A count must be a positive whole number. A section name may be quoted or bare,
and it matches the text of a `#` line after the `#` markers, trimmed, compared
without regard to case.

**Stop and ask** rather than guessing whenever the argument is anything else: a
word that is not `section`, a zero, a negative, a decimal, a name that matches
no section, or a name that matches more than one. Taking the wrong amount of the
queue is expensive in both directions. Too little looks like the skill ignored
the request, and too much spends effort the user did not authorise.

A plain count ignores section boundaries: `/do-next 3` takes three prompts even
when a `#` line sits between the second and the third.

If the queue holds fewer prompts than were asked for, take what is there and say
so. That is not an error.

**What the argument changes is how much gets planned and run, not how it runs.**
The prompts still execute one at a time, in order, and each is still archived the
moment it is finished.

## The queue format

`./NEXT.md` holds prompts separated by a line containing exactly `--`, and those
prompts may be grouped into sections by lines beginning with `#`:

```
# Groundwork
Do the first thing.
--
Do the second thing.
It can span many lines.

# Cleanup
Do the third thing.
```

Both `./NEXT.md` and `./DONE.md` live at the **project root**, which is the
current working directory. Do not go hunting up or down the tree for them.

### Prompt separators

**A separator is a line whose trimmed content is exactly `--`**, two hyphens and
nothing else. A `---` line is NOT a separator: `---` is a markdown horizontal
rule and a frontmatter fence, and treating it as one would split a prompt in
half.

**Split with the same rule when you READ and when you ARCHIVE.** Trailing
whitespace on a separator line is invisible and common. Read with a trimmed
match and archive with an exact `\n--\n` and the two disagree: the reader sees
two prompts, the archiver sees one, and the second prompt is filed as done and
deleted from the queue without ever being run. That has happened.

### Section dividers

**A divider is a line whose trimmed content starts with `#`.** It closes the
section above it and opens a new one, so a `--` immediately before a `#` line is
optional and its absence is not an error. Sections do not nest: `##` and `###`
divide exactly as `#` does, and a deeper heading is a new sibling section rather
than a child.

A divider's text names the section. Use the name when you confirm the set, when
you report progress, and when you archive. **Never inject it into a prompt.**
Each prompt must stand on its own, and a description that silently became part
of the work would make the queue mean something different when read than when
run.

If `./NEXT.md` has no `#` line at all, the whole file is one section with no
name, and everything below behaves as it always did.

### Which section is next

**The next section is the one containing the head of the queue.** If the first
non-whitespace line at the head is not a `#` line, then everything from the head
down to the first `#` line is a section with no name, and that unnamed section is
the next one. A run of `/do-next section` takes it.

A named section runs **where it sits**. The sections above it stay queued,
untouched, and in their original order. `/do-next section` on a later run takes
whichever section then holds the head.

## The run

### 1. Resolve the set

Read `./NEXT.md`. Split it into sections on `#` lines and into prompts on `--`
lines, then select the prompts the argument asks for. Keep them in queue order;
the first one in the file is the first one to run.

Stop and tell the user if:
- `./NEXT.md` does not exist,
- it is empty, or holds only whitespace, separators and dividers,
- the argument names a section that is not there.

There is nothing to do in any of those cases. Say so rather than inventing work.

### 2. Confirm the set

Show the user **every** prompt you are about to run, in order, grouped under its
section name. Not a summary, not just the first, not just a count. Then ask
whether to proceed.

**This is a hard gate, and it is the only approval of the set.** Confirming the
set authorises the questions in step 3, the plans in step 4, and all of the work
that follows. Nothing after this point asks the user to approve the set again,
so the set the user sees here is the whole of what they are agreeing to. The
run comes back to the user only for a decision above the threshold in step 6,
an irreversible action, or something it cannot supply. Do not begin the
questions, explore the codebase, or invoke another skill until they say yes.

If they decline, stop. Leave `NEXT.md` untouched and run nothing.

If they approve only some of what you showed, take those and leave the rest
queued in their original order.

Approval covers this set only. It does not carry to a later run, however this
one went.

### 3. Ask every question, up front

Walk the confirmed prompts in order and ask each one's clarifying questions
before any prompt runs. The user answers once, in one sitting, and is then free
to leave.

**Ask cumulatively, never in isolation.** By the time you reach prompt 3 you
know what prompts 1 and 2 are going to do, so ask prompt 3's questions in that
light. A later prompt's questions frequently depend on an earlier prompt's
answers, and treating each prompt as though it stood alone is the failure this
phase exists to prevent. Build the picture forward.

If a prompt's answers reveal that it is unnecessary, already done, or in
conflict with an earlier prompt, say so and ask whether to drop it.

**Change nothing during this phase.** Reading files and running read-only
commands is how you form good questions. Edits, migrations, installs and commits
wait for step 5.

### 4. Codify every plan, up front

Write a plan for each prompt, in order, and put all of them in the run file
before any work starts.

Each plan carries the prompt text, the answers from step 3, the steps to take,
and how the result gets verified. Write plan N knowing what plans 1 through
N-1 intend to leave behind, so plan N builds on their outcome instead of
assuming the tree as it stands right now.

With each plan, record its **baseline** (the git commit and changed-file list
now) and its **assumptions** (the files, interfaces, behaviours and facts it
relies on, each specific enough to check later). Step 5 checks them before the
prompt starts, to catch what changed between planning and work.

Still change nothing. This phase produces text, not commits.

### 5. Run each prompt, in order

Run them **one at a time, to completion, in queue order**. Do not start the
second before the first is finished and archived. They share a working tree and
usually depend on each other, and a batch is not permission to interleave them.

Treat each prompt as if the user had typed it. That includes the normal skill
rules: if a skill applies to what the prompt asks for, invoke it.

**Re-read the run file when each prompt's turn arrives,** not the conversation:
the file is the record, and the conversation may have been compacted or
interrupted since the plan was written. Mark the prompt `running`.

**Then check the plan against the project as it now stands.** The plan was
written before the earlier prompts ran, and the project may also have changed
from outside the run.

1. List what changed since the plan's baseline: `git diff --stat <baseline commit>`
   and `git status --porcelain`. Outside a git repository, compare the
   modification times of the files the plan names.
2. Sort each change. **Expected:** made by a prompt of this run, as its plan said
   it would. **Outside the run:** the user's edits, another session, a tool, or a
   prompt of this run that went beyond its plan.
3. Take each of the plan's assumptions in turn and decide: still true, changed in
   a way the plan absorbs, or broken.
4. If every assumption holds, start. If any does not, the plan needs adjusting:
   that is a decision after the question phase, and step 6 decides it. Write the
   adjusted plan back to the run file before any work starts.

**Keep the progress note current.** After each step of the plan, and always
before pausing to ask anything, write into the prompt's entry what has been done,
which step is next, and anything half-finished. If the run is interrupted, this
note is how it resumes.

### 6. Decide, or pause, after the question phase

Every question that matters should have been asked in step 3. Some cannot be:
the project changes between planning and work, and some concerns, ambiguities and
knowledge gaps only appear once the work starts. This step decides them all the
same way, so the user is not called back for things that are cheap to change
later.

**Errors are work, not trouble.** A failing test, a broken build or a command
that errors is part of the prompt's work: diagnose it and fix it. Only when
fixing it needs a choice (which of two behaviours is intended, whether the test
or the code is wrong) does it become a decision.

**For every decision after the question phase:** a broken plan assumption, an
unknown met during the work, or an error whose fix needs a choice:

1. **Write the options** exactly as you would present them to the user, with one
   marked recommended. The recommended option is "the most probable decision";
   the two are the same thing. Never take an option you would not have
   recommended.
2. **Ask what reversing the recommended option would cost** if it later turned
   out wrong. **Pause and ask the user only when reversing it would require:**
   - **a major redesign:** changing an interface, data format, architecture or
     user-visible behaviour that other prompts in the run, or existing code
     outside it, depend on; or
   - **lost work across items:** redoing more than one completed prompt, or most
     of the work remaining in the run.
3. **Otherwise take the recommended option without pausing,** record it in the
   decision log (see "The run file"), and carry on.
4. **When you do pause,** write the progress note first, then show the user the
   same option list with the same recommendation, and wait. The run is paused,
   not stopped: their answer resumes it.

**Two things stay outside the threshold:**

- **Irreversible or outward actions** (pushing, deleting data that has no copy,
  publishing, sending messages, spending money) are always asked about, whatever
  the threshold says.
- **What you cannot supply stops the run.** A missing credential, service, file
  or permission leaves no option to take. Mark the prompt `stopped`, set the run
  file's state to `stopped`, and report what is needed. The stopped prompt and
  everything after it stay in `NEXT.md`, and `DONE.md` is left alone for them.
  Trouble of this kind stops the run: do not skip the prompt and carry on with
  the next one, because the later plans assume this one landed.

**Press through.** If this run was told to press through ("don't stop for
problems", "improvise and keep going"), never pause, even when the threshold
would ask. Take the recommended option, log it with `above threshold`, and list
it first in the reports. The two exceptions above still apply.

### 7. Archive each finished prompt

Only once that prompt is genuinely complete and verified, and **before starting
the next one**, never all together at the end. A run interrupted half way must
leave a queue that says exactly what is left.

1. **Get the current time from the system**, never from memory:

   ```bash
   date '+%Y-%m-%d %H:%M:%S %z'
   ```

   Your context may carry today's *date*, but it never carries the *time*, so a
   timestamp written from memory is fabricated. Run the command. Run it again for
   each prompt: they finished at different times, and copying the first one's
   timestamp onto the rest makes the log say something untrue.

2. **Append** to `./DONE.md`: the timestamp on its own line in square brackets,
   then the prompt text, then, if any decision was taken without asking, a
   `Decisions taken without asking:` line followed by one `- ` line per decision
   (what was decided, and the main alternative), then a `--` line. Create
   `DONE.md` if it does not exist.

   ```
   [2026-08-24 09:42:13 -0400]
   Do the first thing.
   Decisions taken without asking:
   - Kept the old config key as an alias rather than removing it outright.
   --
   ```

   The brackets keep the timestamp from being mistaken for part of the prompt,
   and the trailing `--` keeps `DONE.md` splittable the same way `NEXT.md` is.

3. **Then** remove that prompt and its `--` line from `./NEXT.md`, **found by its
   text, not by its position**: the prompt whose text, trimmed of leading and
   trailing white space and compared line by line, equals the archived one. The
   user may have added prompts above it or edited others during the run, so the
   top of the file is not necessarily this prompt. If the text is no longer
   there (the user edited or deleted it), remove nothing, and say so in the
   report; the prompt is still archived.

4. **When no prompt of that section is left in `NEXT.md`**, move the section's
   `#` line to `DONE.md` as well, directly after the prompt you just archived,
   and remove it from `NEXT.md`. `DONE.md` then keeps the grouping that `NEXT.md`
   had.

5. Mark the prompt `done` in the run file.

Append before removing, in that order. If something dies between the two steps,
that ordering leaves a duplicate entry, which is a nuisance; the reverse order
loses the prompt entirely.

Preserve the rest of both files byte for byte. Never reformat, reflow, or reorder
the prompts and dividers still queued.

### 8. Report and offer what is next

After each prompt, say what it did and list the decisions it took without asking,
each with its main alternative, so the user can reverse any of them.

At the end of the run, report what was done, prompt by prompt, not as one lumped
summary. List every decision taken without asking, grouped by prompt, with any
`above threshold` ones first. Report any prompt whose text was no longer in
`NEXT.md` when it was archived. Say how many prompts remain and how many sections
they span, so the user knows the size of what is left. Then ask whether to keep
going.

Delete the run file once every prompt in the run is archived.

## Adding to a live run

The user may ask for more of the queue while a run is in flight: they type
`/do-next` (with any argument) while a prompt is running, or while the run is
still asking its questions. The run must take the new prompts on without losing
its place.

1. **Reach a safe point.** Finish the tool call in progress and do not start
   another step of the running prompt. Write its progress note.
2. **Resolve the new set** from `NEXT.md` with the usual argument rules, leaving
   out every prompt already in the run (matched by text). If nothing new is left,
   say so and resume.
3. **Confirm the new set.** Show every new prompt, grouped by section, and ask.
   The prompts already in the run were approved before and are not shown again.
   If the user declines, leave `NEXT.md` as it is and resume.
4. **Ask the new prompts' questions,** cumulatively over every plan still pending
   and the running prompt: the new prompts are planned against the project as
   those prompts will leave it. If an answer conflicts with a pending plan, raise
   it now. This is a question phase, so asking is expected and the threshold in
   step 6 does not apply.
5. **Write the new plans,** with their baselines and assumptions, and append them
   to the run file after the prompts already pending, in queue order.
6. **Resume.** Re-read the run file and continue the running prompt from its
   progress note.

If the run is still in its own question or planning phase when the new request
comes, the new prompts join that set: confirm them, ask their questions with the
rest, and plan everything together.

## The run file

The run's questions, answers, plans and progress live in `./.claude/do-next-run.md`,
one file per run. It exists because the plans are written long before some of them
run, and a plan that survives only in the conversation is lost to a compaction
or a crash, which wastes the whole front-loaded phase. **It is the source of
truth for the run:** re-read it whenever a prompt starts, whenever the run resumes
after a pause or an added set, and whenever you are unsure where the run is.

It starts with a header:

```text
state: active
started: 2026-10-09 14:02:11 -0400
```

and holds, for each prompt in the run:

- its position, its section name, its text, and the answers from step 3;
- its plan from step 4;
- **baseline:** the git commit (`git rev-parse HEAD`) and the changed-file list
  (`git status --porcelain`) when the plan was written; outside git, the paths and
  modification times of the files the plan names;
- **assumptions:** the files, interfaces, behaviours and facts the plan relies on,
  one per line, each specific enough to check (a path, a signature, "the config
  key `x` exists");
- **status:** `pending`, `running`, `done` or `stopped`;
- **progress** (the running prompt): what is done, which step is next, anything
  half-finished;
- **decision log:** one entry per decision taken without asking:

  ```text
  decision: <what was decided>
  options: <option A (recommended, taken)> | <option B> | <option C>
  why: <why the recommended option is the most probable>
  reversal: <what changing it later would cost, and why that is below the threshold>
  ```

  An entry taken under press-through is marked `above threshold`.

**A live run is never overwritten.** A file whose state is `active` is a live
run: a new `/do-next` adds to it (see "Adding to a live run"). A file whose state
is `stopped`, or that has no state line (written by an earlier version of this
skill), is a record of an earlier run, even though its later prompts are still
`pending`: report it before doing anything else, then start the new run fresh.

Write it at the end of step 4, before any work begins, with the state `active`.
Update a prompt's status as it starts, stops and is archived.

Delete it when the run completes with every prompt archived. **When a run stops,
set the state to `stopped` and leave the file in place**, so the user can see
where it halted and what the remaining plans said.

If the project has a `.gitignore`, add `.claude/do-next-run.md` to it. The file
is a working note for one run, not part of the project's history.

## Red flags

| Thought | Reality |
|---------|---------|
| "They invoked do-next, so they've already approved the prompts" | They approved reading the queue. Step 2 gates the contents, which they may not have seen since writing them. |
| "This prompt is trivial, no need to confirm" | The gate never scales with the task. Show it, ask, wait. |
| "They asked for a section, so I'll show the name and get going" | Step 2 shows every prompt in it. They cannot approve what they have not seen. |
| "They confirmed the set, so I'll confirm the plans too" | Step 2 is the only gate. A second approval round defeats the point of front-loading, which is that the user answers once and leaves. |
| "I'll ask this prompt's questions when its turn comes" | Every question is asked in step 3. A question that waits for step 5 puts the user back in the chair mid-run. |
| "I'll ask each prompt's questions on its own terms" | Ask cumulatively. Prompt 3's questions depend on what prompts 1 and 2 will have done. |
| "The questions are done, so I can start the first prompt" | Step 4 writes every plan first. The plans are what make the later prompts coherent. |
| "I'm only reading files, so a quick fix along the way is fine" | Steps 3 and 4 change nothing. Work starts at step 5. |
| "The plan no longer fits, so I'll adjust it and move on" | Write the options, mark the one you would recommend, and apply the threshold. Below it, take the recommendation and log it; above it, pause and ask. Never adjust a plan without a log entry. |
| "This is ambiguous, so I'd better ask" | Only if reversing your recommended option would mean a major redesign or lost work across items. Otherwise take it and log it; the user answered once so they could leave. |
| "Reversing this would mean a redesign, but I'm fairly sure, so I'll just do it" | Above the threshold you pause, however sure you are, unless this run said press through. |
| "I'll take the safer option rather than the one I'd recommend" | The option taken is always the one you would have recommended to the user. If the safer option is better, recommend it. |
| "The test failed, so the run stops" | Errors are work. Fix it; only a fix that needs a choice is a decision, and the threshold decides it. |
| "They said press through, so I don't need to record what I changed" | Every decision taken without asking goes in the decision log, and press-through ones are reported first. Improvising is permitted; hiding it is not. |
| "A batch means I can run them in parallel" | They share a working tree and usually depend on each other. One at a time, in order, each finished before the next starts. |
| "Prompt 2 of 4 stopped, I'll skip it and do 3" | The later prompts and plans assume the earlier ones landed. A stop stops the run. |
| "A run file is here, so I'll start fresh" | Only a stopped or finished run is a record. A live one is added to, never overwritten. |
| "I remember where the run was" | Re-read the run file. The conversation may have been compacted or interrupted since. |
| "They called do-next mid-run, so I'll drop what I'm doing" | Reach a safe point, write the progress note, add the new prompts, then resume the running prompt where it was. |
| "The top prompt in NEXT.md is the one I just finished" | Remove a prompt by its text. The user may have added or edited prompts during the run. |
| "I'll archive the whole run at the end" | Then an interruption leaves a queue that lies about what is done. Archive each as it finishes. |
| "One `date` reading is fine for the run" | They finished at different times. Re-run it per prompt. |
| "It mostly worked; I'll archive it and flag the caveat" | A caveat is a decision: apply step 6. If it is below the threshold, finish the work and log the choice; a prompt is archived only when it is complete. |
| "I'll archive it now so I don't forget" | Archiving before the work is done loses the prompt if the work then fails. |
| "The section heading explains the prompt, so I'll pass it along" | A divider's text is a label, never part of a prompt. |
| "This heading is inside a prompt, so it won't count as a divider" | It will. Any line starting with `#` divides, wherever it sits, so a prompt that needs a markdown heading in its body will be split. |
| "`---` is close enough to `--`" | It is not. `---` is a horizontal rule, and splitting on it will cut a prompt in half. |
| "I'll grep for the separator to read, and slice on `\n--\n` to archive" | Two matchers, one file. A separator with a trailing space passes the first and fails the second, and a prompt gets archived unrun. Use one rule in both places. |
| "I know roughly what time it is" | You do not. Run `date`; a remembered timestamp is a made-up one. |
| "The run stopped, so I'll clear the run file" | A stopped run leaves it, marked `stopped`, so the user can see where it halted. |
