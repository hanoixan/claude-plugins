---
name: do-next
description: Use when the user asks to work through a queue of prompts stored in NEXT.md - confirms the set, asks every prompt's questions and codifies every plan up front, then runs them one at a time, archiving each to DONE.md. Takes an optional count of prompts, or a section to take a whole group at once, `--yes` (or `-y`) to show the set and go on without asking to confirm it, and `--subagents` (or `-s`) to keep the main conversation's context small by sending broad planning reads and the heavier prompts to subagents. Also use when the user asks for more of the queue while a run is already in flight - the new prompts join the live run without it losing its place.
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
`./.do-next-run.md` says `state: active` (see "The run file"), or when this
conversation is still in steps 1 to 4 of a run whose file is not written yet. If
a run is live, go to "Adding to a live run" instead of starting a new one, and
announce it that way.

**With `--yes`, say so in the announcement:** "Using do-next to take the next 3
prompts from NEXT.md, with --yes: the set is shown below and the run goes on
without asking."

**With `--subagents`, say so too:** "Using do-next to take the next 3 prompts from
NEXT.md, with --subagents: work that would fill this conversation goes to
subagents."

**An `active` file this conversation did not write is an interrupted run,** left
by a session that was closed, crashed, or could not finish updating it. Do not
resume it on trust. Reconcile it first: a prompt whose text is already in
`DONE.md` is `done`, whatever the file says; a prompt still in `NEXT.md` and not in
`DONE.md` is not done. Then show the user the reconciled state (what is done,
what is left, any progress note and pending question) and ask whether to resume
it or abandon it. Abandoning sets its state to `stopped` and leaves it as a record.

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
/do-next 3 --yes          the top three, shown but not asked about (also -y)
/do-next section -s       the next section, its heavy work in subagents (also --subagents)
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

### Taking the set without asking: `--yes`

`--yes`, or its short form `-y`, as a word of its own anywhere in the argument,
says the user trusts the selection: step 2 shows the set and goes straight on,
without asking to confirm it. Take it out before reading the rest of the argument,
which is then read exactly as above, so `/do-next -y section Cleanup` and
`/do-next section Cleanup --yes` mean the same. A section whose name really is
`-y` or `--yes` is given quoted. Only these two spellings count: a bare `yes`
could be a section name, and is read as one.

**It skips one question and nothing else.** With `--yes`:

- **The set is still shown,** every prompt, grouped by section, exactly as step 2
  shows it, so the user sees at once what was taken and can interrupt before
  anything changes (steps 3 and 4 change nothing).
- **An argument that cannot be resolved still stops and asks** (a word that is not
  `section`, a zero, a name that matches no section or several). `--yes` trusts the
  selection, never a guess about what the argument meant.
- **The clarifying questions of step 3 are still asked.** They are about how to do
  the work, not which work to do.
- **Everything else that asks still asks:** a decision above the threshold in step 6,
  an irreversible action the prompt does not name, a pending question, and whether
  to resume or abandon an interrupted run.

It comes only from the argument of this call. It does not carry to a later run, or
to prompts added later to this one unless that request carries it too, and it is
never inferred from a "yes" elsewhere in the conversation or from anything in
`NEXT.md`.

### Saving the main context: `--subagents`

`--subagents`, or its short form `-s`, as a word of its own anywhere in the
argument, asks the run to **keep the main conversation's context small**, by
handing work to subagents **where that saves more than it costs**. It is read like
`--yes`: taken out before the rest of the argument is read, combined freely with a
count, a section and `--yes` (`/do-next 3 -y -s`), and only these two spellings
count; a section whose name really is `-s` or `--subagents` is given quoted.

Its purpose is the main context, nothing else, so it is applied selectively:

- **Planning reads through Explore subagents.** In steps 3 and 4, broad code
  reading (surveying a subsystem, finding every caller, tracing a flow across many
  files) goes to read-only Explore subagents, which return their conclusions. A
  targeted read of one known file stays in the main agent: delegating it would
  cost more than reading it.
- **Each prompt is marked `delegated` or `inline`** in step 4, by what it would
  put into the context that a subagent could keep out.
- **The delegated prompts are run by subagents,** one per group (see "Groups and
  subagents"). The main agent still confirms the set, asks every question and
  writes every plan; a subagent runs, archives and reports its prompts by the
  same rules.

Without it, nothing is delegated by the run: every prompt runs in the main
conversation, as it describes, and a prompt may itself ask for subagents; that is
the prompt's work, not this flag. Like `--yes`, it comes only from the argument of
this call: it does not carry to a later run or to a set added later.

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
whether to proceed, unless the argument carried `--yes`.

**With `--yes`,** show the set in exactly the same way, say that it was taken with
`--yes`, and go straight on to step 3 without waiting. The set shown is still the
whole of what the run will do, and everything below about the gate holds: it has
been answered by the argument instead of by a reply.

**This is a hard gate, and it is the only approval of the set.** Confirming the
set authorises the questions in step 3, the plans in step 4, and all of the work
that follows. Nothing after this point asks the user to approve the set again,
so the set the user sees here is the whole of what they are agreeing to. The
run comes back to the user only for a decision above the threshold in step 6,
an irreversible action the prompt itself did not ask for, or something it
cannot supply. Do not begin the
questions, explore the codebase, or invoke another skill until they say yes (or,
with `--yes`, until the set has been shown).

If they decline, stop. Leave `NEXT.md` untouched and run nothing.

If they approve only some of what you showed, take those and leave the rest
queued in their original order.

Approval covers this set only. It does not carry to a later run, however this
one went.

### 3. Ask every question, up front

Walk the confirmed prompts in order and ask each one's clarifying questions
before any prompt runs. Ask every question that matters, cheap or not: the
threshold in step 6 is for what the question phase could not settle, never a
reason to skip a question here. The user answers once, in one sitting, and is then free
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

**With `--subagents`, send broad reading to Explore subagents** (read-only), and
ask each for the conclusion you need, not the file contents: "which callers pass
a null path, with file and line". Read one known file yourself. Independent
surveys can run at once. The questions are still yours to form and ask.

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

**With `--subagents`, mark each prompt `delegated` or `inline`,** with a one-line
reason, by what its work would put into the main context:

- **delegated:** work that fills context: builds and test runs, many files read or
  changed, debugging likely, long command output.
- **inline:** work that is small (a few lines in a known place, where starting a
  subagent that must re-read the skill, the run file and the code would cost more
  than it saves); work that is mostly main-session steps (see "Groups and
  subagents"); or work likely to need the user several times, since every pause
  passes through the main agent anyway.

When in doubt, mark it delegated: that is what the user asked for. In a delegated
prompt, also tag the plan's **main-session steps**. After writing the plans, list
the marks for the user, one line per prompt with its reason. This is not a gate:
the run goes on, and the user can change a mark before its group starts.

Still change nothing. This phase produces text, not commits.

### 5. Run each prompt, in order

In a group run by a subagent, steps 5 to 7 are the subagent's: see "Groups and
subagents". Everything they say holds for it.

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
2. **Ask what reversing the recommended option would cost** if the user turned
   it down **after the run has finished**, with every later prompt built on it.
   Judge by that cost, not by the kind of change. **Pause and ask the user only
   when reversing it then would require:**
   - **a major redesign:** reworking an interface, data format, architecture or
     user-visible behaviour that other prompts in the run, or existing code
     outside it, depend on, beyond a small, local edit to each dependent; or
   - **lost work across items:** redoing more than one prompt of the run, or
     most of the work remaining in it.
   A choice that a few lines in one or two places would undo is below the
   threshold, even if it touches an interface.
3. **Otherwise take the recommended option without pausing,** record it in the
   decision log (see "The run file"), and carry on.
4. **When you do pause,** write the progress note first, and with it the
   **pending question**: the full option list and the recommendation, in the run
   file. Then show the user the same list and wait. The run is paused, not
   stopped: their answer resumes it, and clears the pending question. If they
   end the run instead, set its state to `stopped`. If the conversation is
   compacted, or another `/do-next` arrives, before they answer, show the pending
   question again first; never take its recommendation by default.

**Three things stay outside the threshold:**

- **Irreversible or outward actions** (pushing, deleting data that has no copy,
  publishing, sending messages, spending money) are always asked about, whatever
  the threshold says, **unless the prompt itself asks for that action** ("commit
  and push", "publish the release"): the user approved that prompt in step 2, and
  that approval is the ask. An irreversible action the prompt does not name is
  still asked about.
- **What you cannot supply stops the run.** A secret or credential, an external
  service, or a permission that you cannot obtain leaves no option to take, and
  so does an error that survives three genuinely different fixes. Anything that
  does have options (a file the plan relied on that has been deleted or moved, a
  prompt that has grown well beyond its plan) is a decision for the threshold
  above, not a stop. Mark the prompt `stopped`, set the run
  file's state to `stopped`, and report what is needed. The stopped prompt and
  everything after it stay in `NEXT.md`, and `DONE.md` is left alone for them.
  Trouble of this kind stops the run: do not skip the prompt and carry on with
  the next one, because the later plans assume this one landed.
- **A refusal by the permission or safety check always pauses.** Never reword,
  split or reroute a refused action to get it past the check. Write the progress
  note and a pending question: what was refused, why the plan needs it, and the
  options (the user runs it themselves, for instance with `! <command>`; the user
  approves it and it is tried once more; the step is dropped and the plan
  adjusted; the run stops). Then ask, as in 4 above.

**Press through.** If this run was told to press through ("don't stop for
problems", "improvise and keep going"), never pause, even when the threshold
would ask. Take the recommended option, log it with `above threshold`, and list
it first in the reports. The three exceptions above still apply.

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
   another step of the running prompt. Write its progress note. If a subagent is
   running the current group, leave it running: the main agent is free, and the
   new set is planned alongside it.
2. **Resolve the new set** from `NEXT.md` **with every prompt already in the run
   left out first** (matched by text), then apply the usual argument rules to
   what remains: `/do-next 2` takes the next two prompts not yet in the run, and
   `/do-next section` takes the next section that still has prompts not in the
   run. If nothing new is left, say so and resume. If the run is paused on a
   pending question, show that question again before anything else.
3. **Confirm the new set.** Show every new prompt, grouped by section, and ask.
   The prompts already in the run were approved before and are not shown again.
   If the user declines, leave `NEXT.md` as it is and resume. If this request
   carried `--yes`, show them and go on without asking; the run's earlier `--yes`,
   if it had one, does not count for them.
4. **Ask the new prompts' questions,** cumulatively over every plan still pending
   and the running prompt: the new prompts are planned against the project as
   those prompts will leave it. If an answer conflicts with a pending plan, raise
   it now. This is a question phase, so asking is expected and the threshold in
   step 6 does not apply.
5. **Write the new plans,** with their baselines and assumptions (and, if this
   request carried `--subagents`, their marks), as **new groups** appended to the
   run file after every group already in it: one inline group without the flag,
   or groups cut by mark with it (see "Groups and subagents"). They run when the
   groups before them are done.
6. **Resume.** Re-read the run file and continue the running prompt from its
   progress note. If a subagent is running the current group, there is nothing to
   resume in the main agent: it goes back to relaying that subagent's reports.

If the run is still in its own question or planning phase when the new request
comes, the new prompts join that set: confirm them, ask their questions with the
rest, and plan everything together. Each prompt keeps its own call's flag: the new
prompts are marked only if their request carried `--subagents`, and are inline
otherwise, whatever the first call said.

## Groups and subagents

**A group is a run of consecutive prompts that share a runner:** the main agent
(**inline**) or one **subagent**. Without `--subagents`, a call's set is one inline
group. With it, the set is cut wherever the step 4 mark changes: consecutive
`delegated` prompts form one subagent group, consecutive `inline` prompts one
inline group, in queue order. A set added later to the live run forms groups of
its own the same way. Sections are within groups: a group holds whichever
prompts, of whichever sections, fall in it.

**Groups run one after another, in the order they were added.** They share one
working tree, so a group starts only when the one before it has finished, every
prompt archived. The main agent asks a new group's questions and writes its plans
at once, even while an earlier group is still running, and plans it against the
project as the earlier groups will leave it. An inline group after a subagent
group is run by the main agent when the subagent's group finishes.

**Main-session steps.** Some steps must not be left to a background agent that
nobody is watching, and the permission and safety checks may refuse them there,
or refuse to start a subagent whose brief hands them over:

- **irreversible or outward actions:** writing or migrating live or production
  data, deploying, publishing, pushing to a shared branch, deleting data that has
  no copy, sending messages, spending money;
- **steps that need the user present:** an interactive login, a secret or
  credential only they have, anything that would ask them for permission.

Step 4 tags these in each delegated plan. They stay the main agent's even when
the prompt names them: the subagent does the reversible work around them, and the
main agent takes each one itself (see "It returns at every boundary"). A prompt
that is mostly such steps is marked inline.

**Starting a subagent group.** When its turn comes, and its plans are in the run
file, the main agent starts one general-purpose subagent, on the session's model,
in the background, with a brief that gives:

- the path of the run file and the group to run (its number and its prompts);
- the path of this skill file, `SKILL.md` in this skill's base directory: the
  subagent reads "The run" (steps 5 to 7), "The queue format" and "The run file",
  and follows them as written, so there is one text of the rules, not two;
- what it may not do: ask the user anything directly (it cannot), take a
  main-session step (tagged, or one it meets that the plan missed), touch another
  group's entries in the run file, or start the next group.

The brief grants no main-session step, not even as "the plan says so": it names
them only as points to stop and return. **If the start is refused,** check the
brief against that rule. If it handed over a main-session step, the tagging
missed it: tag it, correct the brief, and start once more. If it did not, or the
second start is refused too, do not reword it again: tell the user, and offer to
run the group inline or stop the run.

The subagent re-reads the run file, then runs the group's prompts in order. It
may hand parts of a prompt to subagents of its own when its tools allow it and
the work divides; otherwise it does the work itself.

**It returns at every boundary,** and the main agent resumes it (by sending to the
same agent, its context intact) to go on:

- **after each prompt is archived,** with that prompt's report from step 8 (what it
  did, and every decision taken without asking with its main alternative). The
  main agent passes the report to the user, then resumes the subagent for the
  next prompt;
- **when it must pause** (a decision above the threshold, an irreversible action
  the prompt does not name, something it cannot supply): it writes the progress
  note and the pending question to the run file first, then returns the question.
  The main agent shows the user the same options, resumes the subagent with the
  answer, and the pending question is cleared. A stop is reported the same way,
  and stops the run as step 6 says;
- **before each main-session step:** it writes the progress note and the step
  (exactly what to run and how to check it) to the run file, then returns it. The
  main agent takes the step itself, on the plan's approval and by step 6's rules
  (an irreversible action the prompt does not name is still asked about), checks
  it, records the outcome in the run file, and resumes the subagent. If a check
  refuses the step, step 6's refusal rule applies: the main agent asks the user
  and never works around it;
- **when the group is done,** with the group's report. The next group then starts.
  The subagent never deletes the run file or writes the run's final report: those
  are the main agent's, at the end of the run (step 8), from the groups' reports.

**The main agent is free while a subagent works:** the user can talk to it, and
another `/do-next` adds a group (see "Adding to a live run") without interrupting
the subagent. The main agent never runs work of its own in the working tree while
a subagent group is running; a main-session step the subagent has returned for is
the one exception, since the subagent is waiting on it. If the user asks to stop the group, the main agent
stops the subagent, marks the group and the run `stopped`, and reports where it
halted.

**If the session ends while a subagent runs,** the subagent ends with it. The run
file then shows the group `running`: the next `/do-next` treats it as an
interrupted run, reconciles it against `DONE.md` and `NEXT.md`, and asks whether to
resume (in a new subagent, if the group was one) or abandon it.

## The run file

The run's questions, answers, plans and progress live in `./.do-next-run.md`, beside
`NEXT.md`,
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

(the `started` time read with `date '+%Y-%m-%d %H:%M:%S %z'`, never written from
memory). Then come the **groups**, in the order they were added, each under its
own heading, above the sections and prompts it holds:

```text
## group 2: subagent
state: running
agent: <the subagent's id or name, while it runs>
```

where the kind is `inline` or `subagent`, and the state `pending`, `running`, `done`
or `stopped`. While a subagent runs, **each writer keeps to its own part**: the
subagent changes only its group's entries, and the main agent only the group
headers and the groups it appends at the end. Change the file with edits to those
parts, never by writing the whole file anew, so neither overwrites the other.

Each group holds, for each of its prompts:

- its position, its section name, its text, and the answers from step 3;
- **confirmed:** `asked` when the user approved it in step 2 (or in step 3 of
  "Adding to a live run"), `--yes` when it was taken with `--yes`, so a stopped or
  interrupted run shows how each prompt was approved;
- its plan from step 4;
- **mark** (only with `--subagents`): `delegated` or `inline`, and its one-line
  reason;
- **main-session steps** (delegated prompts): each tagged step, with its state
  (`pending`, `handed back`, `done` or `refused`) and, once taken, its outcome;
- **baseline:** the git commit (`git rev-parse HEAD`) and the changed-file list
  (`git status --porcelain`) when the plan was written; outside git, the paths and
  modification times of the files the plan names;
- **assumptions:** the files, interfaces, behaviours and facts the plan relies on,
  one per line, each specific enough to check (a path, a signature, "the config
  key `x` exists");
- **status:** `pending`, `running`, `done` or `stopped`;
- **progress** (the running prompt): what is done, which step is next, anything
  half-finished;
- **pending question** (only while paused in step 6): the option list and the
  recommendation that were shown to the user, so the question survives a
  compaction or an interruption;
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
**If it cannot be written** (a permission prompt is declined, the folder is
protected), stop before any work starts and tell the user: without the run file
there is nothing to resume from and nothing to stop a second run starting
alongside this one. Do the same if a later update to it fails: pause, say which
update failed, and wait.
Update a prompt's status as it starts, stops and is archived.

Delete it when the run completes with every prompt archived. **When a run stops,
set the state to `stopped` and leave the file in place**, so the user can see
where it halted and what the remaining plans said.

Earlier versions of this skill kept the file at `./.claude/do-next-run.md`. A
file found there is a record of an earlier run: report it as above, and never
resume or overwrite it.

If the project has a `.gitignore`, add `.do-next-run.md` to it. The file
is a working note for one run, not part of the project's history.

## Red flags

| Thought | Reality |
|---------|---------|
| "They invoked do-next, so they've already approved the prompts" | They approved reading the queue. Step 2 gates the contents, which they may not have seen since writing them. |
| "This prompt is trivial, no need to confirm" | The gate never scales with the task. Show it, ask, wait. Only the user skips the question, by passing `--yes`; it is never skipped on your judgment. |
| "They asked for a section, so I'll show the name and get going" | Step 2 shows every prompt in it. They cannot approve what they have not seen. |
| "They passed `--yes`, so I don't need to show the set" | `--yes` skips the question, not the showing. Every prompt is shown, so a wrong pick is seen before anything changes. |
| "They passed `--yes`, so I'll skip the questions as well" | `--yes` covers the confirmation of the set only. Step 3's questions, the threshold pauses and irreversible actions still ask. |
| "The argument is unclear, but they said `--yes`, so I'll take the likeliest reading" | An argument that cannot be resolved stops and asks, `--yes` or not. It trusts the selection, never a guess. |
| "They used `--yes` last time, or said yes earlier" | `--yes` comes only from this call's argument. It is never carried over or inferred. |
| "`--subagents`, so the subagent can ask the questions" | It cannot reach the user. The main agent asks every question and writes every plan; the subagent runs, archives and reports. |
| "The subagent needs a decision, so it can take its best guess" | Above the threshold it writes the pending question and returns; the main agent asks the user and resumes it. A subagent is no licence to skip a pause. |
| "A subagent group is running, so I'll start the next group too" | Groups share the working tree. The next one starts when this one is done. |
| "A subagent is running, so I can make that small change myself" | Not in the working tree. The main agent plans and talks while a subagent group runs; the subagent does the work. |
| "`--subagents`, so every prompt goes to a subagent" | The flag is for the main context. A one-line fix costs more to delegate than to do; mark it inline. |
| "`--subagents`, so I'll have an Explore agent read this one file" | Only broad reading pays for a subagent. A known file is cheaper to read yourself. |
| "The prompt asks for the deploy, so the subagent can do it" | Irreversible, production and credential steps are main-session steps. The subagent returns before each; the main agent takes it. |
| "The check refused it; I'll phrase it differently" | A refusal pauses the run. Ask the user; never reword, split or reroute the action to get past the check. |
| "I'll write the subagent the rules it needs" | Give it the skill file's path. One text of the rules, not a copy that drifts. |
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
| "The file says active, so I'll pick up where it says" | If this conversation did not write it, reconcile it against DONE.md and NEXT.md, show the user, and ask whether to resume or abandon. |
| "The run is paused, and they sent something else, so I'll take my recommendation" | A pending question is answered by the user. Show it again; never default it. |
| "I can't write the run file, so I'll keep the state in my head" | Stop before any work. Without the file there is nothing to resume from. |
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
