---
name: question-refiner-auto
description: Set or show the predicted probability at or above which question-refiner answers a question with its prediction, after the user confirms, instead of asking it. 0 answers every eligible question this way; 100, the default, turns it off.
argument-hint: "[0-100]"
disable-model-invocation: true
---

# Setting the auto-answer threshold

Run, with the argument the user gave (`SKILL_DIR` is the folder holding this file):

```bash
python3 "SKILL_DIR/../question-refiner/scripts/refiner.py" auto $ARGUMENTS
```

Show the output. With a number, it is the user's new threshold: from the next round, a single-select question that
is not a probe, whose predicted choice is at least that likely, is shown for confirmation instead of asked. Nothing
is answered this way before the user has answered 8 questions.

With no number, the output is the current threshold and the tally line. If the tally has a suggestion, say that it
is the misses' mean probability plus two standard deviations: few wrong predictions were that confident.
