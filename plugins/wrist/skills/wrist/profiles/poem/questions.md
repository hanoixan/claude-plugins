# Premise questions: poem

Ask these in the premise phase, a few at a time, in plain language. A `required` question must be answered or
recorded as an `*UNKNOWN*:` before generation; a `deferrable` question may be left out (write `none (skipped on
purpose)` so `check` stops warning about it). The id is the key used in `wrist/PREMISE.md`.

One answer decides what is printed, so it goes in the `PREMISE.md` front matter as well: `titled` (`yes` or `no`,
default `no`). A question whose id is a front matter key counts as answered when the front matter has the key.
The front matter `title:` is always needed: when `titled` is `yes` it is the title printed above the poem, and
when `no` it is only a working title for the file names and the metadata.

## The poem

- [required] subject: What is the poem about, in a sentence? Name the concrete thing, place or moment it starts from, not the theme.
- [required] form: Which form (see forms.md: sonnet-shakespearean, sonnet-petrarchan, villanelle, sestina, pantoum, haiku, tanka, limerick, triolet, ballad, couplets, blank-verse, free-verse), `custom`, or "choose for me"?
- [required] tone: What tone should the poem hold, and where may it turn?
- [required] audience: Who is it for (yourself, a person, an occasion, a readership)?
- [required] length: How long, in lines? If the form fixes it, say "the form's own".

## What you already know

- [deferrable] speaker: Who is speaking, and to whom?
- [deferrable] occasion: Is it written for an occasion (a date, an event, a person)?
- [deferrable] rhyme: Any preference on rhyme and meter (rhymed, unrhymed, strict, loose)?
- [deferrable] images: Which images, objects or sounds should be in it?
- [deferrable] avoid: What do you want kept out (subjects, words, images, tones)?
- [deferrable] titled: Does the poem carry a title? Answer `yes` or `no`; the default is no, and if yes, give the title.
- [deferrable] epigraph: An epigraph, with its source?
- [deferrable] dedication: A dedication?
- [deferrable] keep: Is there a detail, word or digression that matters to you for reasons the poem need not give, and that must stay even if an editor would cut it?
