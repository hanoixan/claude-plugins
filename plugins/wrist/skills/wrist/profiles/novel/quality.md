# Quality for a novel

The target is a book an editor or a prize jury would stop for. These lists name what to avoid. Copy the
ones that apply into each stand-in's `Rules:` during generation; check the work against all of them during
realization. The searchable items are in `lint.json` (run `wrist_check.py lint`); the rest need a reader's
judgment, per chapter and across the whole book.

## Clichés and stock moves

Openings
- The chosen one, the farm boy, the orphan who learns of a destiny.
- Waking up, an alarm clock, a mirror description, the weather, the sun rising.
- A prologue that explains the world, the prophecy or the history.
- A dream used as a first scene, or a flashback before the book has earned one.

Characters
- The mentor who dies so the hero can grow.
- The villain who explains the plan, or who monologues before the final move.
- An ensemble in which everyone speaks in the author's voice.
- The love interest who exists only to be rescued, or lost.
- Names that sound alike, or that all start with the same letter.

Plot
- A coincidence that solves the central problem.
- A secret kept only because no one asks the obvious question.
- The ally who turns out to be the traitor, with no earlier sign.
- A last-minute rescue by an arriving stranger or an unplanted skill.
- An epilogue that ties every thread, or that tells the reader what to feel.

Prose
- Bodily clichés (shivers, held breaths, racing hearts) and named emotions ("a wave of sadness").
- Stalling gestures (sighs, deep breaths, nods) used between lines of dialogue.
- Adverb-propped dialogue tags; characters telling each other what both know.
- Information delivered in dialogue ("as you know").
- "Suddenly", "meanwhile", "little did she know", "everything was about to change".

## Marks of low quality

- A sagging middle: the second act repeats the obstacle at the same size.
- No midpoint turn, so the book runs in one direction from the inciting incident to the end.
- Stakes that do not escalate, or are announced rather than felt.
- A protagonist who makes no decision in the second act.
- Subplots that start and stop without resolving, or resolve by accident.
- Point-of-view slips: a character knows what only another could know.
- Chapters that all end the same way (always a cliffhanger, always a quiet reflection).
- Verbal tics repeated across chapters (a gesture, a phrase, a kind of simile).
- Exposition in blocks, or backstory before the reader needs it.
- Characters who change because the plot says so, not because of a choice.
- Time and place that blur: the reader cannot say where a chapter is or how long has passed.
- Names, dates, injuries and facts that disagree between chapters.
- An ending that summarizes, or that stops without landing.

## Judgment checklist

Work through this in the review pass, with the realized text and the stand-ins open. Do it once per chapter as
you finish it, and again for the whole book before `review_done: yes`. Mark an item only when you have
checked it against the text.

Per chapter
- [ ] The chapter's first line belongs to this chapter and creates a question or a pressure.
- [ ] The chapter changes something: a fact, a relationship, a plan, a risk.
- [ ] The point of view is the one the stand-in names, and never slips.
- [ ] The chapter ends differently from the chapter before it.
- [ ] Every item in `Must include:` is present and no `Must avoid:` item appears.
- [ ] Nothing in the text contradicts the `Established:` fields of earlier chapters, unless a stand-in names the contradiction as deliberate.
- [ ] The `Established:` field of this chapter lists every new fact, date, injury and promise the text fixed.
- [ ] No fact appears in the text that no stand-in holds.

Whole book
- [ ] There is a midpoint turn, and the second half is not the first half again.
- [ ] Stakes escalate from act to act and are paid, not announced.
- [ ] The protagonist makes a costly decision in the second act.
- [ ] Every subplot resolves, or is left open on purpose and says so in a stand-in.
- [ ] Each main character speaks differently from the others and from the narration.
- [ ] No coincidence solves the central problem.
- [ ] The ending is earned by what came before and does not state the theme.
- [ ] No verbal tic repeats across chapters more than twice.
- [ ] The length is within about ten percent of the target.
- [ ] `wrist_check.py lint` reports no hits, or every hit is deliberate.
