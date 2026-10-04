# Poem forms

Each form is a skeleton in `forms/<name>.psg`. Copy it into `structure.md`, keep its line count, rhyme scheme,
refrains and meter (the `named` line makes `verse` check that you did), and add `image[...]`-style unit hints
if you want them. `references/psg.md` is the grammar. A form is a promise to the reader, kept or broken on
purpose: if the poem needs a different shape, say `custom` and write your own skeleton.

## sonnet-shakespearean
Fourteen lines of iambic pentameter: three quatrains (A B A B, C D C D, E F E F) and a couplet (G G). The argument
usually turns at line 9 or in the couplet. Fits an argument or a change of mind. Watch: the couplet that only
sums up, and rhymes that bend the sense. The stanza breaks may be moved.

## sonnet-petrarchan
An octave (A B B A A B B A) and a sestet (C D E C D E, or C D C D C D), in iambic pentameter, turning at line 9.
Fits a problem and its answer. Watch: English has fewer rhymes, so the A and B sounds tire. The breaks may be moved.

## villanelle
Nineteen lines in five tercets and a quatrain on two rhymes. Line 1 returns as lines 6, 12 and 18; line 3 as lines
9, 15 and 19. Fits an obsession or a thing that cannot be put down. Watch: the refrains must change meaning as the
poem goes, or the form is only repetition. Refrains keep their meter and tag.

## sestina
Six sestets and a three-line envoi, all on six end words that rotate (123456, 615243, 364125, 532614, 451362,
246531); the envoi here ends on words 5, 3 and 1. Fits a subject with six facets. Put the six words in the `let`
list. Watch: choose words that bend (a noun that is also a verb); avoid abstractions.

## pantoum
Four quatrains in which lines 2 and 4 of each stanza return as lines 1 and 3 of the next; the last stanza closes the
circle with lines 3 and 1 of the first. Unrhymed here. Fits memory and circling. Watch: repeated lines must read
differently in a new place.

## haiku
Three lines of 5, 7 and 5 syllables: an image, a cut, a second image. Watch: the syllable count is the least of it.

## tanka
Five lines of 5, 7, 5, 7, 7 syllables; the third line often turns.

## limerick
Five lines rhymed A A B B A, with three beats in the long lines and two in the short. Comic.

## triolet
Eight lines on two rhymes; line 1 returns as lines 4 and 7, line 2 as line 8. Fits a short thought that changes.

## ballad
Rhymed quatrains, lines 2 and 4 rhyming, alternating four and three beats; each stanza has its own rhyme. Fits a story.

## couplets
Pairs of rhymed lines, each pair with its own rhyme. Watch: the sing-song.

## blank-verse
Unrhymed iambic pentameter, any length. Fits speech and argument.

## free-verse
Any lines, any stanzas, no meter, no repeated lines. Watch: the line break must still do work.
