# The verse format, the verse command and its estimates

## The poem file

The realized poem (`work/<slug>.md`) is plain verse:

- If the poem is titled (`titled: yes` in `PREMISE.md`), the first line is `# Title` and the next line is blank.
  The title must equal the `title:` in `PREMISE.md`. An untitled poem has no title line.
- A stanza is the lines between blank lines; one blank line is enough (more are ignored).
- One line of verse per line of the file. Never wrap a long line by hand: the typesetter hangs a wrapped line.
- Each leading space (a tab counts four) indents the line by half an em, so `    stepped` is indented two ems.
  Spaces inside a line collapse to one.
- Nothing is markup: `*`, `_`, `#`, `1.`, `>` and `[` are literal characters. Smart punctuation is not applied; type the
  quotes and dashes you want.

## `wrist_check.py verse WRIST_DIR [--root .] [--json]`

Reads `structure.md`, the structure stand-in and the poem. Output is one line per finding,
`file:line: error|estimate: message`, then a count. Exit 1 on any error.

Errors (exact):

- the skeleton does not parse (the message gives the line and column), or breaks a rule R0 to R12;
- the structure stand-in's `Form:`, `Lines:` or `Stanzas:` disagrees with the skeleton (`Form:` is the `named` form,
  or `custom`);
- the skeleton says `named "x"` and differs from the catalog form x;
- the poem has a title line that `titled` does not allow, or lacks one it requires, or the title differs from the
  premise title;
- the poem has a different number of stanzas, or of lines in a stanza, or in all, than the skeleton;
- a refrain's lines are not the same word for word (comparing without case, spacing, curly quotes or punctuation at
  the ends of the line);
- a line with `ends @list[k]` does not end with item k.

If the skeleton has errors the poem is not checked. `gate publishing` blocks on every error.

Estimates (advisory, always labelled, never blocking). They are rough and English only:

- syllables: a vowel-group counter, less a silent final e, es or ed. A binary foot meter (iamb, trochee, spondee)
  expects the feet times 2, one more allowed (a feminine ending); a ternary one (anapest, dactyl, amphibrach) the
  feet times 3, from two fewer to one more; `syllables N..M` expects that range; a `stress` pattern expects its
  length;
- a `stop` line with no punctuation at the end, a `run` line ending a sentence, a `caesura` line with no pause;
- rhyme: lines under one tag whose last words end differently as spelled. This misses rhymes spelled differently
  (only sky, high and a few like them are joined) and counts an eye rhyme (gone, stone) as a rhyme. Also a rhyme
  word used twice;
- refrain and `ends` lines are exempt from the repeated-word check.
