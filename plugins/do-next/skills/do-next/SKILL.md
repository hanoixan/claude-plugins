---
name: do-next
description: Use when the user asks to work through a queue of prompts stored in NEXT.md - confirms the set, asks every prompt's questions and codifies every plan up front, then runs them one at a time, archiving each to DONE.md. Takes an optional count of prompts, or a section to take a whole group at once.
---

# do-next

Work through a queue of prompts kept in `./NEXT.md`. Confirm the set before
anything else, ask all of its questions and write all of its plans up front,
then run the prompts one at a time, archiving each to `./DONE.md` as it
finishes.

**Announce at start:** "Using do-next to take the next prompt from NEXT.md."
When taking several, say how many: "Using do-next to take the next 3 prompts
from NEXT.md." When taking a section, name it and give its size: "Using do-next
to take the 'Cleanup' section, 4 prompts, from NEXT.md."

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

**This is a hard gate, and it is the only gate in the run.** Confirming the set
authorises the questions in step 3, the plans in step 4, and all of the work
that follows. Nothing after this point asks for approval again, so the set the
user sees here is the whole of what they are agreeing to. Do not begin the
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

Write a plan for each prompt, in order, and put all of them in the scratch file
before any work starts.

Each plan carries the prompt text, the answers from step 3, the steps to take,
and how the result gets verified. Write plan N knowing what plans 1 through
N-1 intend to leave behind, so plan N builds on their outcome instead of
assuming the tree as it stands right now.

Still change nothing. This phase produces text, not commits.

### 5. Run each prompt, in order

Run them **one at a time, to completion, in queue order**. Do not start the
second before the first is finished and archived. They share a working tree and
usually depend on each other, and a batch is not permission to interleave them.

Treat each prompt as if the user had typed it. That includes the normal skill
rules: if a skill applies to what the prompt asks for, invoke it.

**Re-read the plan when its turn arrives, and check it against the tree as it
now stands.** The plan was written before the earlier prompts ran, so it may no
longer fit.

- If it still fits, follow it.
- If it does not, that is trouble under step 6. Stop and ask. Do not quietly
  rewrite an approved plan into a different one.

The exception is an explicit instruction in this run to press through blockers,
such as "don't stop for problems" or "improvise and keep going". Under that
instruction, work out the best solution the prompt's stated intent and
constraints allow, record in the scratch file what you changed and why, and carry
on.

### 6. Stop on any trouble

If anything goes wrong, **stop and ask the user** before continuing. "Anything"
means any point at which you would otherwise guess, work around a blocker,
narrow the scope, or hand back something partial:

- a test fails, a build breaks, a command errors
- the plan no longer matches the tree
- a required file, credential, service, or dependency is missing
- the work turns out much larger than the prompt and its plan implied

Do not press on and report the trouble afterwards. The gate in step 2 bought the
user one decision up front, and this step is how they get another when the run
diverges from what they approved.

A prompt stopped this way is **not** complete: leave it and everything after it
in `NEXT.md`, and leave `DONE.md` alone for it.

**Trouble stops the run.** Do not skip the failed prompt and carry on with the
next one, because the later prompts and their plans were written against a tree
where this one succeeded. Report which prompts completed, which one stopped, and
what remains.

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
   then the prompt text, then a `--` line. Create `DONE.md` if it does not exist.

   ```
   [2026-08-24 09:42:13 -0400]
   Do the first thing.
   --
   ```

   The brackets keep the timestamp from being mistaken for part of the prompt,
   and the trailing `--` keeps `DONE.md` splittable the same way `NEXT.md` is.

3. **Then** remove that prompt and its trailing `--` line from the top of
   `./NEXT.md`, leaving the next prompt at the top.

4. **When that prompt was the last one in its section**, move the section's `#`
   line to `DONE.md` as well, directly after the prompt you just archived, and
   remove it from `NEXT.md`. `DONE.md` then keeps the grouping that `NEXT.md`
   had.

Append before removing, in that order. If something dies between the two steps,
that ordering leaves a duplicate entry, which is a nuisance; the reverse order
loses the prompt entirely.

Preserve the rest of both files byte for byte. Never reformat, reflow, or reorder
the prompts and dividers still queued.

### 8. Report and offer what is next

Report what was done, prompt by prompt, not as one lumped summary. Say how many
prompts remain and how many sections they span, so the user knows the size of
what is left. Then ask whether to keep going.

Delete the scratch file once every prompt in the run is archived.

## The scratch file

The run's questions, answers and plans live in `./.claude/do-next-run.md`, one
file per run. It exists because the plans are written long before some of them
run, and a plan that survives only in the conversation is lost to a compaction
or a crash, which wastes the whole front-loaded phase.

It holds, for each prompt in the run: its position, its section name, its text,
the answers from step 3, the codified plan from step 4, a status of pending,
running, done or stopped, and any deviation recorded under the press-through
instruction in step 5.

Write it at the end of step 4, before any work begins. Update a prompt's status
as it starts and as it is archived.

Delete it when the run completes with every prompt archived. **Leave it in place
when a run stops**, so the user can see where the run halted and what the
remaining plans said. A later `do-next` that finds one reports it before doing
anything else, then starts its own run fresh; a stale plan file is a record, not
a queue.

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
| "The plan no longer fits, so I'll adjust it and move on" | Stop and ask, unless this run told you to press through blockers. An approved plan quietly rewritten is work the user never saw. |
| "They said press through, so I don't need to record what I changed" | The scratch file records every deviation. Improvising is permitted; hiding it is not. |
| "A batch means I can run them in parallel" | They share a working tree and usually depend on each other. One at a time, in order, each finished before the next starts. |
| "Prompt 2 of 4 failed, I'll skip it and do 3" | The later prompts and plans assume the earlier ones landed. Trouble stops the run. |
| "I'll archive the whole run at the end" | Then an interruption leaves a queue that lies about what is done. Archive each as it finishes. |
| "One `date` reading is fine for the run" | They finished at different times. Re-run it per prompt. |
| "It mostly worked; I'll archive it and flag the caveat" | A prompt with a caveat is not complete. Stop at step 6 and let the user decide. |
| "I'll archive it now so I don't forget" | Archiving before the work is done loses the prompt if the work then fails. |
| "The section heading explains the prompt, so I'll pass it along" | A divider's text is a label, never part of a prompt. |
| "This heading is inside a prompt, so it won't count as a divider" | It will. Any line starting with `#` divides, wherever it sits, so a prompt that needs a markdown heading in its body will be split. |
| "`---` is close enough to `--`" | It is not. `---` is a horizontal rule, and splitting on it will cut a prompt in half. |
| "I'll grep for the separator to read, and slice on `\n--\n` to archive" | Two matchers, one file. A separator with a trailing space passes the first and fails the second, and a prompt gets archived unrun. Use one rule in both places. |
| "I know roughly what time it is" | You do not. Run `date`; a remembered timestamp is a made-up one. |
| "The run stopped, so I'll clear the scratch file" | A stopped run leaves it, so the user can see where it halted. |
