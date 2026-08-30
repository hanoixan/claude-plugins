# economy-of-words

A Claude Code plugin that strips filler, framing and self-appraisal from replies.

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
/plugin marketplace add hanoixan/claude-economy-of-words
/plugin install economy-of-words@economy-of-words
```

Requires `jq` on `PATH`. Without it the hook exits quietly and only the skill works.

## Editing the rules

The hook reads `${CLAUDE_PLUGIN_DATA}/rules.txt` when that file exists, and the
bundled `hooks/rules.txt` otherwise. Copy the bundled file to the plugin's data
directory and edit it there; plugin updates will not overwrite it.

## Where the rules came from

The phrase list is not generic writing advice. It was derived by counting tics
across a real 870-reply Claude Code session: 1407 em-dashes, 1163 bold spans,
330 "Now the…" transitions, 102 "actually", 78 "Let me check…" narrations, and
66 trailing "which is exactly why…" clauses.

## License

MIT
