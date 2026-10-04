# Quality for a screenplay

The target is a script an agent, a reader or a jury would stop for. These lists name what to avoid. Copy the ones that
apply into each stand-in's `Rules:` during generation; check the work against all of them during realization. The
searchable items are in `lint.json` (run `wrist_check.py lint`); the rest need a reader's judgment, per act and across
the whole script.

## Clichés and stock moves

Openings
- Waking up, an alarm clock, a mirror shot, a dream, a voice-over that explains the world, a sunrise.
- Opening on a flashback to the event that explains everything.
- A cold open that is only noise before the real film starts.

Description
- "We see", "we hear" and camera directions (PAN, ZOOM, CLOSE ON, ANGLE ON) in a spec script.
- What a character thinks, remembers, knows or decides, which the camera cannot show.
- Stock reactions: eyes widen, heart pounds, a single tear, a smirk, a sigh.
- Action blocks of five lines or more.

Dialogue
- On-the-nose lines that state the feeling ("I feel so alone").
- "As you know" exposition, and characters telling each other what both know.
- Stock lines: "We need to talk", "It's quiet. Too quiet."
- Every character speaking in the writer's voice.

Plot
- The mentor who dies so the hero grows, the villain who explains the plan, the last-second rescue.
- A coincidence that solves the problem.
- A final image that states the theme.

## Marks of low quality

- Pages over or under the runtime (a page is about a minute); a first act that takes a third of the script.
- An act turn that lands off its page (for a feature, the first turn near page 25 to 30, the midpoint near 60, the second turn near 85 to 90).
- Scenes that do not turn: nothing is different at the end of them.
- Dialogue with no subtext: every line says exactly what the character means.
- Unfilmable description; narration of thought in action lines.
- Slug lines that rename the same place (KITCHEN in one scene, THE KITCHEN in the next, CAMERON'S KITCHEN after that).
- A protagonist who makes no decision in the second act.
- Information delivered in dialogue instead of shown.
- Characters who are named but never matter; a cast of voices that sound alike.
- An ending that explains.

## Judgment checklist

Work through this in the review pass, with the realized Fountain and the stand-ins open. Do it once per act as you
finish it, and again for the whole script before `review_done: yes`. Mark an item only when you have checked it
against the text.

Per act
- [ ] The act's first scene belongs to this act and creates a question or a pressure.
- [ ] Every scene changes something: a fact, a relationship, a plan, a risk.
- [ ] Every scene heading (the slug line) uses a location's `Slug:` exactly as the misc stand-in writes it.
- [ ] Action blocks are four lines or fewer and describe only what the camera can see.
- [ ] Each speaker's lines sound different from the others'.
- [ ] No line states a feeling that an action or an image could carry; there is subtext.
- [ ] Every item in `Must include:` is present and no `Must avoid:` item appears.
- [ ] Nothing contradicts the `Established:` fields of earlier acts, unless a stand-in names the contradiction as deliberate.
- [ ] The act's `Established:` field lists every new fact, date, injury, prop and promise the text fixed.
- [ ] No fact appears in the text that no stand-in holds.

Whole script
- [ ] The page count is within about ten percent of the runtime.
- [ ] The act turns fall near the pages the structure gives them.
- [ ] Stakes escalate from act to act and are paid, not announced.
- [ ] The protagonist makes a costly decision in the second act.
- [ ] Setups are paid off and nothing is planted without a payoff.
- [ ] No coincidence solves the central problem.
- [ ] The final image answers the opening image and does not state the theme.
- [ ] `wrist_check.py lint` reports no hits, or every hit is deliberate.
