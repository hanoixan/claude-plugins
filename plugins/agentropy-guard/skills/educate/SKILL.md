---
name: educate
description: Give the user one short architecture note when agentropy-guard's Stop hook asks, and follow up on their answer. Use only when a hook names an item for it.
---

# Architecture notes

`GUARD` is `python3 "SKILL_DIR/../../scripts/guard.py"` (`SKILL_DIR` is the folder holding this file).

The hook names one ledger item that is important, probably unknown to the user, and relevant to what they just did.
Give at most one note per hook request:

1. `GUARD item get ID` for its summary and evidence.
2. Write one line tied to what the user just did, then the question:
   > 💡 *Architecture note:* payment retries live in the queue worker, not in `billing`, which is why your change
   > here didn't affect them. Want a short visual explainer?
   With question-refiner installed, exempt the question first (reason "architecture note"); it trades nothing off.
3. `GUARD told ID --level mentioned`.

The user's answer arrives with their next prompt (a hook reminds you):
- yes → follow the arch-report skill, then `GUARD told ID --level report_generated --report PATH`;
- "I know" → `GUARD respond ID --response acknowledged`;
- not now → `GUARD respond ID --response snoozed`;
- no, or annoyance → `GUARD respond ID --response dismissed` (two dismissals in a row double the gap between notes);
- a question about it → answer in chat, then `GUARD told ID --level explained`.

When the hook says a turn changed an important item silently, the note is simply what changed, in one line, and
`GUARD told ID --level mentioned`. When the user mentions an item themselves, `GUARD seen --item ID --signal
user_prompt_mentioned` is recorded by the hook; when you summarise a change to an item in your reply, record
`GUARD seen --item ID --signal agent_summarized`.
