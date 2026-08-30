# hanoixan-claude-plugins

A Claude Code plugin marketplace.

## economy-of-words

Strips filler, framing and self-appraisal from replies.

It ships two things that work together:

- **A skill** (`/economy-of-words`) — the full reference: reply shape, the banned
  phrase list, a typography budget, rewrites and a red-flags checklist.
- **A `UserPromptSubmit` hook** — a 150-word condensation of the same rules,
  injected on every turn.

The hook is the point. A skill body is sent into the conversation once, when it is
invoked, and then sits at a fixed position in the history while hundreds of later
replies demonstrate the opposite style. The hook re-states the rules at the end of
the context window on every single turn, so they never decay.

## Install

```
/plugin marketplace add hanoixan/claude-plugins
/plugin install economy-of-words@hanoixan-claude-plugins
```

Requires `jq` on `PATH`. Without it the hook exits quietly and only the skill works.

## Editing the rules

The hook reads `${CLAUDE_PLUGIN_DATA}/rules.txt` when that file exists, and the
bundled `plugins/economy-of-words/hooks/rules.txt` otherwise. Copy the bundled file to the plugin's data
directory and edit it there; plugin updates will not overwrite it.

## Where the rules came from

The phrase list is not generic writing advice. It was derived by counting tics
across a real 870-reply Claude Code session: 1407 em-dashes, 1163 bold spans,
330 "Now the…" transitions, 102 "actually", 78 "Let me check…" narrations, and
66 trailing "which is exactly why…" clauses.

## do-next

Works through a queue of prompts kept in `./NEXT.md`, one at a time, confirming
before it starts and archiving each finished prompt to `./DONE.md` with a
timestamp read from the system clock.

```
/do-next        one prompt
/do-next 3      the top three, in order
```

Prompts are separated by a line containing exactly `--`. A batch buys one
confirmation instead of several; it does not buy parallelism, and trouble in any
prompt stops the batch with the queue left honest about what remains.

```
/plugin install do-next@hanoixan-claude-plugins
```

## License

MIT
