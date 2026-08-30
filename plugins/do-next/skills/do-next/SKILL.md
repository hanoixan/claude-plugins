---
name: do-next
description: Use when the user asks to work through a queue of prompts stored in NEXT.md - runs the top prompt after confirmation, then moves it to DONE.md and offers the next one. Takes an optional count to run several in one go.
---

# do-next

Work through a queue of prompts kept in `./NEXT.md`, confirming before starting
and archiving each one to `./DONE.md` as it is finished.

**Announce at start:** "Using do-next to take the next prompt from NEXT.md."
When running a batch, say how many: "Using do-next to take the next 3 prompts
from NEXT.md."

## The argument

`do-next` takes one optional argument: **how many prompts to take from the head
of the queue**. It defaults to **1**, which is the ordinary behaviour and what
you get when no argument is given.

```
/do-next        one prompt
/do-next 3      the top three, in order
```

The argument must be a positive whole number. If it is anything else — a word, a
zero, a negative, a decimal — **stop and ask** rather than guessing. Running the
wrong number of prompts is expensive in both directions: too few looks like the
skill ignored them, too many spends effort they did not authorise.

If the queue holds fewer prompts than were asked for, take what is there and say
so. That is not an error.

**What the argument changes is the GATE, not the work.** The prompts are still
executed one at a time, in order, and each is still archived the moment it is
finished. What batching buys is one confirmation instead of several — see step 2.

## The queue format

`./NEXT.md` holds prompts separated by a line containing exactly `--`:

```
Do the first thing.
--
Do the second thing.
It can span many lines.
--
Do the third thing.
```

**The separator is a line whose trimmed content is exactly `--`** — two hyphens,
nothing else. A `---` line is NOT a separator: `---` is a markdown horizontal
rule and a frontmatter fence, and treating it as one would split a prompt in
half. If the file has no `--` line at all, the whole file is a single prompt.

**Split with the same rule when you READ and when you ARCHIVE.** Trailing
whitespace on a separator line is invisible and common. Read with a trimmed
match and archive with an exact `\n--\n` and the two disagree: the reader sees
two prompts, the archiver sees one, and the second prompt is filed as done and
deleted from the queue without ever being run. That has happened.

Both files live at the **project root** — the current working directory. Do not
go hunting up or down the tree for them.

## The loop

### 1. Read the top prompts

Read `./NEXT.md`. Split it on `--` lines and take the first **N** prompts, where
N is the argument (default 1). Keep them in order; the first one in the file is
the first one to run.

Stop and tell the user if:
- `./NEXT.md` does not exist,
- it is empty or holds only whitespace and separators.

There is nothing to do in either case; say so plainly rather than inventing work.

### 2. Ask before running them

Show the user **every** prompt you are about to run — all N of them, in order,
not a summary and not just the first — and ask whether to proceed.

**This is a hard gate.** Do not begin the work, explore the codebase, or invoke
another skill until they say yes. If they decline, stop — leave `NEXT.md`
untouched and do not run any of them.

One confirmation covers the batch they were shown, because asking for N is
itself the instruction to batch the gate. It does **not** carry to a later batch:
the next `do-next` asks again, however the last one went.

If they approve only some of what you showed, run those and leave the rest
queued in their original order.

### 3. Follow each prompt, in order

Treat each prompt as if the user had typed it. That includes the normal skill
rules: if a skill applies to what the prompt asks for, invoke it.

Run them **one at a time, to completion, in queue order**. Do not start the
second before the first is finished and archived. They share a working tree and
may well depend on each other — a later prompt frequently assumes the earlier
one landed, and a batch is not permission to interleave them.

### 4. Stop on any trouble

If anything goes wrong, **stop and ask the user** before continuing. "Anything"
means any point at which you would otherwise guess, work around a blocker,
narrow the scope, or hand back something partial:

- a test fails, a build breaks, a command errors
- the prompt is ambiguous and two readings mean different work
- a required file, credential, service, or dependency is missing
- the work turns out much larger than the prompt implies

Do not press on and report the trouble afterwards. The point of the gate is that
the user gets to redirect before the effort is spent.

A prompt stopped this way is **not** complete: leave it and everything after it
in `NEXT.md`, and leave `DONE.md` alone for it.

**In a batch, trouble stops the batch.** Do not skip the failed prompt and carry
on with the next one — the later prompts were queued against a tree where this
one succeeded. Report which ones completed, which one stopped, and what remains.

### 5. Archive each finished prompt

Only once that prompt is genuinely complete and verified — and **before starting
the next one in the batch**, never all together at the end. A batch interrupted
half way must leave a queue that says exactly what is left.

1. **Get the current time from the system**, never from memory:

   ```bash
   date '+%Y-%m-%d %H:%M:%S %z'
   ```

   Your context may carry today's *date*, but it never carries the *time* — a
   timestamp written from memory is fabricated. Run the command. Run it again
   for each prompt in a batch: they finished at different times, and copying the
   first one's timestamp onto the rest makes the log say something untrue.

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

Append before removing, in that order. If something dies between the two steps,
that ordering leaves a duplicate entry, which is a nuisance; the reverse order
loses the prompt entirely.

Preserve the rest of both files byte for byte — never reformat, reflow, or
reorder the prompts still queued.

### 6. Offer the next one

Report what was done — for a batch, what each prompt produced, not one lumped
summary — then ask whether to run the next prompt from the top of `./NEXT.md`.
If they say yes, go back to step 1. If they say no, stop.

Mention how many prompts are left, so the user knows the size of what remains.

## Red flags

| Thought | Reality |
|---------|---------|
| "They invoked do-next, so they've already approved the prompt" | They approved reading the queue. Step 2 gates the prompt's contents, which they may not have seen since writing it. |
| "This prompt is trivial — no need to confirm" | The gate never scales with the task. Show it, ask, wait. |
| "They asked for 3, so I'll show the first and get going" | Step 2 shows all three. They are approving what they are about to spend effort on, and they cannot approve what they have not seen. |
| "They said 3, so the next 3 are approved too" | The batch they were shown is approved. The next batch is a new question. |
| "A batch means I can run them in parallel" | They share a working tree and usually depend on each other. One at a time, in order, each finished before the next starts. |
| "Prompt 2 of 3 failed, I'll skip it and do 3" | The later prompts assume the earlier ones landed. Trouble stops the batch. |
| "I'll archive the whole batch at the end" | Then an interruption leaves a queue that lies about what is done. Archive each as it finishes. |
| "One `date` reading is fine for the batch" | They finished at different times. Re-run it per prompt. |
| "It mostly worked; I'll archive it and flag the caveat" | A prompt with a caveat is not complete. Stop at step 4 and let the user decide. |
| "I'll archive it now so I don't forget" | Archiving before the work is done loses the prompt if the work then fails. |
| "`---` is close enough to `--`" | It is not. `---` is a horizontal rule; splitting on it will cut a prompt in half. |
| "I'll grep for the separator to read, and slice on `\n--\n` to archive" | Two matchers, one file. A separator with a trailing space passes the first and fails the second, and a prompt gets archived unrun. Use one rule in both places. |
| "I know roughly what time it is" | You do not. Run `date`; a remembered timestamp is a made-up one. |
