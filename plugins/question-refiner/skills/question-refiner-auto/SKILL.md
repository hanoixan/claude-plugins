---
name: question-refiner-auto
description: Set or show the handoff point, the calibrated probability at or above which question-refiner recommends letting the agent answer the rest of a round, answers you then review before they are applied. 85 is the default; 100 turns the recommendation off.
argument-hint: "[0-100]"
disable-model-invocation: true
---

# Setting the handoff point

Run, with the argument the user gave (`SKILL_DIR` is the folder holding this file):

```bash
python3 "SKILL_DIR/../question-refiner/scripts/refiner.py" auto $ARGUMENTS
```

Show the output. With a number, it is the user's new handoff point. From the next round, questions are asked
lowest `p` first, and once every question left could be handed off, the user is offered "Answer the rest";
it is marked recommended when every one left has a calibrated `p` at or above this number. Handed-off answers are
listed for the user to review before they are applied. Nothing is recommended before the user has answered 20
questions, and high-stakes questions, probes and multi-select questions are always asked.

With no number, the output is the current handoff point and the tally line. If the tally has a suggestion, say that
it is the highest threshold the user's own answers back: at least 10 answers at or above it, right at least that
often at a 95% lower bound. `python3 "SKILL_DIR/../question-refiner/scripts/refiner.py" calibration` shows how
often predictions at each probability were right.
