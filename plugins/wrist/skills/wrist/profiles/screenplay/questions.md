# Premise questions: screenplay

Ask these in the premise phase, a few at a time, in plain language. A `required` question must be answered or
recorded as an `*UNKNOWN*:` before generation; a `deferrable` question may be left out (write `none (skipped on
purpose)` so `check` stops warning about it). The id is the key used in `wrist/PREMISE.md`.

Two answers decide which files exist, so they go in the `PREMISE.md` front matter as well: `acts` (a whole number,
1 to 7) and `act_headings` (`yes` or `no`). A question whose id is one of these keys counts as answered when the
front matter has the key (the id `act-headings` stands for the key `act_headings`). Changing either later means
changing the tree.

## The film

- [required] genre: What is the genre or blend of genres (drama, comedy, thriller, horror, science fiction, romance, crime, animation, documentary-style)?
- [required] premise: What is the central situation, or the question the film turns on, in a paragraph?
- [required] ending: What shape should the ending take (closed, open, ironic, reversal, bittersweet, a final image that answers the opening)?
- [required] tone: What tone should the film hold, and where, if anywhere, may it shift?
- [required] story: Whose story is it, and what do they want? (The protagonist and the want that drives the script.)
- [deferrable] themes: What is the film about underneath the plot?

## The audience and the form

- [required] audience: Who is it for, including the rating it aims at (G, PG, PG-13, R, or the equivalent)?
- [required] format: Is it a feature, a short, or something else (a pilot, a stage-length piece)?
- [required] runtime: How long should it run, in minutes? A page is about a minute.
- [required] acts: How many acts? If you are not sure, I will propose a count from the runtime and the structure (a feature is usually three or four, a short one to three); the number is then fixed for the tree.
- [deferrable] act-headings: Should the script print ACT ONE-style headings? A feature does not; a TV-style or stage script does. Answer `yes` or `no`.
- [deferrable] comps: Which films would sit next to this one?

## The world and what you already know

- [deferrable] setting: Where and when does it take place?
- [deferrable] locations: Which locations must be used, and are there limits (a single location, a small budget, no visual effects)?
- [deferrable] characters: Which characters do you already want fixed, and what do you know about them?
- [deferrable] events: Which scenes or events must happen, and roughly where?
- [deferrable] fixed: Which lines, images or real details must appear exactly?
- [deferrable] structure: Do you have a structure in mind (see structures.md), or should one be proposed from the answers above?
- [deferrable] avoid: What do you want kept out (subjects, tropes, kinds of language)?
