# wrist: poem profile design (cycle 4)

Date: 2026-10-04. Status: draft for review. Builds on the foundation, novel and screenplay specs in the same folder.
Sources: the user's `poem-grammar-spec.md` (PSGv2) and `poetry-prompt-rules.md`, both read for this revision.

## Purpose

Add the `poem` profile to wrist, the last of the four. A poem is planned as a **skeleton**: a document in the user's
poem grammar (PSGv2) that fixes the form, the rhetorical shape and the kind of material each slot must hold. The
poem is then written into that skeleton. wrist supplies four things:

1. **A fixed PSGv2** (called PSGv2.1 here): the user's grammar with its defects repaired, so that sestinas,
   villanelles, pantoums and sonnets are expressible and checkable.
2. **A catalog of standard forms** as tested PSGv2.1 skeletons that the agent copies and adapts.
3. **A `verse` command** that parses a skeleton, checks its well-formedness rules, and checks the finished poem
   against it: exact things are errors, estimates are advisory.
4. **A verse text format, reader and `poem` publishing style** that set verse as verse (line breaks and indentation
   kept, never justified or reflowed), plus the **quality bar** taken from the user's prompt rules.

## Decisions taken with the user

| Question | Decision |
|---|---|
| Grammar | PSGv2 is the language of `structure.md`, fixed (PSGv2.1): explicit refrain and end-word labels, tags that can be fresh per repetition, a corrected stress notation, standard forms shipped as tested skeletons. Roles, unit kinds and the closing-statement rule become optional (`strict roles;`), off by default. |
| Checks | Exact checks are errors; syllable, stress, rhyme and caesura checks are advisory estimates. |
| Verse text | Plain verse read by a custom pandoc Lua reader. |
| Who writes `structure.md` | The agent, in PSGv2.1; the checker reads it and also compares it to the catalog form it names. |
| Quality bar | `poetry-prompt-rules.md` is adopted as `quality.md`, the review checklist and advisory lint. |
| Title | Optional, off by default. |

## The grammar: PSGv2.1

PSGv2 is kept as written except for the changes below. The full grammar is published in
`references/psg.md` (the user's text with these changes applied and its defects fixed).

### Fixes

| # | Defect in PSGv2 | PSGv2.1 |
|---|---|---|
| 1 | `refrain X from (line) every N` cannot express a villanelle (lines 1, 6, 12, 18 and 3, 9, 15, 19) or a pantoum, and Example D tags every line `A`. | `refrain NAME at P1, P2, ...;` with explicit 1-based line positions in the expanded poem. The first position is the source and holds the units; every later position is the same line, word for word. A line is in at most one refrain. Line identifiers (`line_A`) are dropped. |
| 2 | The sestina rotation `@end_words[$n + k]` is a cyclic shift, not 123456, 615243 and so on, and nothing forces the end word to end the line. | Arithmetic is removed from hints. A line may end with `ends @list[k]` (index k, 0-based): the line's last word is exactly that list element. The sestina is written out with its true rotation. `@list[$n]` indexes modulo the list length. |
| 3 | Tags are global (R6), so `quatrain, 3, A B A B` makes all twelve lines share two sounds, and R6's "use fresh letters" is impossible with `Count` above 1. | `Rhyme ::= "none" \| "fresh"? Tag+`. `fresh` renames the tags per repetition, so each repeated stanza has its own sounds. Tags are `A`..`Z` (not only `A`..`H`) and `x`. |
| 4 | `stress "/10/10"` mixes a slash with the documented `1`/`0` digits, and its description (four syllables) does not match the string. | `stress` uses `1` (stressed) and `0` (unstressed) only: `stress "1010"`. |
| 5 | R3 says role patterns "must match", then a note says they are "a minimum". | Role patterns are exact full matches, checked only under `strict roles;`. The ghazal note is removed. |
| 6 | The numbering jumps from section 2 to 4; `caesura` is "0-indexed foot" with no definition. | Renumbered. `caesura N` is after the N-th foot, counting from 1, and applies only to foot meters. |
| 7 | Haiku, tanka and limerick need syllable counts, which `Meter` cannot say. | `Meter` gains `syllables N` and `syllables N..M`. |
| 8 | Shapes stop at `quatrain`. | `Shape` gains `quintain` (5), `sestet` (6), `septet` (7) and `octave` (8). |
| 9 | `Count` may be a range or `..*`, which leaves the line count open. | A realized `structure.md` has exact counts (R11). Ranges are for catalog entries, which the agent resolves. |
| 10 | The `Form` token names the stanza shape, so a skeleton cannot say which standard form it follows. | The stanza's shape token is `Shape`. A new declaration `named "villanelle";` says which catalog form the skeleton follows. |

### Made optional

Roles (`setup`, `develop`, `turn`, `resolve`) and the unit kinds with their tests stay as planning vocabulary and are
accepted on any line or stanza. R3 (role patterns), R4 (one turn) and R5 (earned statements) run only when the
skeleton says `strict roles;`, and the rule that a poem ends on a `statement` is a `strict roles;` rule too. This
keeps PSGv2's rhetorical core for authors who want it, without hard-coding "image, then claim" (which the quality
rules argue against: no closing explanation, break the symmetry).

### Grammar (changed productions only)

```
Poem      ::= "poem" "{" Decl* Stanza+ "}"
Decl      ::= Named | Title | Strict | Breaks | Rule | Refrain
Named     ::= "named" String ";"
Title     ::= "title" String ";"            (* informational; the checker ignores it *)
Strict    ::= "strict" "roles" ";"
Breaks    ::= "breaks" "flexible" ";"       (* the stanza division is not compared to the catalog form *)
Refrain   ::= "refrain" Identifier "at" Integer ("," Integer)+ ";"
Stanza    ::= "stanza" "(" Shape "," Count "," Rhyme ("," Role)? ")" "{" Line+ "}"
Shape     ::= "couplet" | "tercet" | "quatrain" | "quintain" | "sestet" | "septet" | "octave" | "free"
Rhyme     ::= "none" | "fresh"? Tag+
Line      ::= "line" "(" Meter "," Ending ("," "caesura" Integer)? "," Tag ("," "ends" Word)? ")" "{" Unit* "}"
Word      ::= "@" Identifier "[" Integer "]"
Meter     ::= Foot Integer | "syllables" Integer (".." Integer)? | "free" | "stress" String
Tag       ::= "A" | ... | "Z" | "x"
```

### Well-formedness rules (PSGv2.1)

Checked in order; all errors are reported with a line number in `structure.md`.

- **R0 References.** Every `@name` in a hint or `ends` resolves to a `let`; an `ends` index is in range; `$n` appears
  only in a stanza whose `Count` is above 1.
- **R1 Rhyme length.** The rhyme tag sequence has one tag per line and equals the line tags; `none` means every line is
  `x`.
- **R2 Shape.** A shape's line count is exact (`free`: at least 1).
- **R3 Role patterns, R4 One turn, R5 Earned statements.** As in PSGv2, only under `strict roles;`.
- **R6 Tags.** Tags are global across the expanded poem unless the stanza's rhyme is `fresh`.
- **R7 Line count.** The expanded line count is the sum of shape line counts times counts.
- **R8 Refrains.** Positions are within the expanded poem, each line is in at most one refrain, and every position of a
  refrain has the same meter, ending and tag as the first.
- **R9 Stress (advisory).** The checker estimates a `stress` line's syllables against the pattern's length. It cannot
  estimate which syllables are stressed (it has no pronouncing dictionary), so the pattern itself is for the poet.
- **R10 Caesura (advisory).** A line with `caesura N` contains a punctuation pause or dash.
- **R11 Concrete (new).** Counts in `structure.md` are exact; the stanza `Count` has no range.
- **R12 Ends (new).** In the poem, every line carrying `ends @list[k]` ends with item k of the list.

## The catalog

`profiles/poem/forms/<name>.psg` holds each standard form as a PSGv2.1 skeleton with `named "<name>";` and, where
the form allows, ranges. The first catalog:

| File | Notes |
|---|---|
| `sonnet-shakespearean` | three quatrains (`C D C D` and so on) and a couplet, `iamb 5`; breaks are conventional but flexible |
| `sonnet-petrarchan` | octave `A B B A A B B A` and sestet `C D E C D E`; breaks flexible |
| `villanelle` | 19 lines, refrains at 1, 6, 12, 18 and 3, 9, 15, 19 |
| `sestina` | six sestets rotating `ends @end_words[k]` as 123456, 615243, 364125, 532614, 451362, 246531, then an envoi of three lines |
| `pantoum` | stanzas of four whose lines 2 and 4 recur as lines 1 and 3 of the next; the circle closes |
| `haiku`, `tanka` | `syllables 5`, `7`, `5` (and `7`, `7`) |
| `limerick`, `triolet`, `ballad`, `couplets`, `blank-verse`, `free-verse` | with ranges for the open ones |

Terza rima, ghazal and rondeau are out of this cycle. Their refrain-and-radif rules and interlocking rhyme need
checks the grammar does not yet express; PSGv2's own ghazal example does not enforce them.

Each catalog file is a test fixture: it must pass R0 to R12, have the line count its name implies, and (for the named
forms) match a table of expected refrain positions and rhyme tags written independently in the test.

## The profile

### File shape

```text
structure.md
work/<slug>.md
```

`structure.md` is the realized skeleton (PSGv2.1 text). `work/<slug>.md` is the poem in verse format.

### Stand-in functions

| Function | Heading | Fields | Children |
|---|---|---|---|
| structure | `structure` | Form, Lines, Stanzas, Rhyme, Meter | none |
| poem | `poem` | Subject, Speaker, Tone, Turn, Ending, Must include, Must avoid, Must keep | none |

- `Form` is the catalog name or `custom`. `Lines` and `Stanzas` are counts; `Rhyme` and `Meter` are notes. The
  structure stand-in's `Form:` must equal the skeleton's `named` declaration (or `custom` when it has none), and
  `Lines` and `Stanzas` must equal the expanded skeleton. These are errors.
- `Turn` says where the poem changes direction; `Ending` says how it lands; `Must keep` names a detail, word or
  digression that stays even though an editor would cut it, without the poem explaining it (the prompt rules'
  "one rule that matters").
- `Form`, `Lines` and `Stanzas` are `required_when_realized` fields of the structure stand-in. `poem` is `prose: true`
  (published and linted); `structure` is not. The poem stand-in depends on the structure
  stand-in with the relation `realizes`.
- Settings: `title_page` false, `form` `{"structure": "structure.md", "poem": "work/{slug}.md"}`, `publish`
  `{"style": "poem"}`, `lint_format` `prose`, `limits.max_prose_words` 120, relations `appears`, `mentions`,
  `sets up`, `pays off`, `realizes`.

### Premise keys and the title

One optional premise key, `titled` (bool, default false). The front matter `title:` is still required: it is the
working title used for the slug, the file names and the metadata. When `titled` is true, the poem's first line is
`# Title` and the title is printed. When false, the poem has no title line, nothing is printed above it, and the
working title stays in the metadata. `verse` checks that the first line matches `titled`, and that a printed title
equals the front matter `title:`.

### Premise questions

Required: subject (what the poem is about), form (a catalog name, `custom`, or "choose for me"), tone, audience,
length (lines, or the form's own). Deferrable: speaker (who speaks, to whom), occasion, rhyme and meter preferences,
images and motifs, words or images to avoid, `titled` (default no, and if yes the title), epigraph, dedication,
`keep` (the detail that stays). When the author does not pick a form the skill proposes one and records it as an
`*UNKNOWN*:` with `Proposed:`.

### Forms reference (`forms.md`)

For each catalog form: what it is, where it fits, its rules in words, and what to watch for.

## The `verse` command

`wrist_check.py verse WRIST_DIR [--root .] [--json]` reads `structure.md`, the structure stand-in and the poem.

- **Missing files and broken skeletons:** a missing `structure.md` is an error and ends the run; a missing poem is an
  error after the skeleton is checked; a skeleton with rule errors leaves the poem unchecked (the message says so).
- **The skeleton:** parsed with a recursive-descent parser (`wrist_verse.py`), expanded (counts, refrains, `ends`,
  `fresh` tags), and checked against R0 to R12. A parse error reports the line and column and what was expected.
  The structure stand-in's `Form`, `Lines` and `Stanzas` fields are compared as above. If `named` is present the
  expansion is compared with the catalog form: line count, rhyme tags, refrain positions, `ends` pattern and meter
  must match; stanza division must match unless the catalog form is marked flexible; ranged counts must fall within
  the range. These are errors.
- **The poem against the skeleton, exactly:** the title line matches `titled`; the same number of stanzas, with the
  same number of lines in each; blank lines between stanzas only; every refrain's lines identical (after lower
  case, collapsed white space, and punctuation stripped at the line ends); every `ends` element's lines ending in
  the same word. These are errors.
- **Advisory estimates** (never errors, each shown as an estimate): a line's syllables against its meter or
  `syllables` target (an English vowel-group counter; feet convert at 2 syllables for iamb, trochee and spondee and 3
  for anapest, dactyl and amphibrach, allowing one extra at a feminine ending); lines of one rhyme tag that do not
  rhyme (final vowel group and what follows); a rhyme word used twice for rhyme (excluding refrain and `ends`
  lines); R9 (syllable count only); R10; and `stop` lines that end with no punctuation or `run` lines that end with a full stop.
- Exit 1 on errors, 0 otherwise. `gate publishing` runs the exact checks and blocks on any error; estimates never
  block.

## The verse reader

`publish/poem/verse.lua` is a pandoc custom reader for plain verse.

- If the poem is titled, the first line is `# Title`, then a blank line. A `# ` line anywhere else is verse.
- A stanza is the lines between blank lines. Each becomes a `Div` of class `stanza` holding a line block, one line of
  verse per line, trailing white space removed.
- Each leading space becomes an en space (U+2002), so indentation survives the typesetter.
- Nothing in a line is markup (`*`, `_`, `#`, `1.`, `>`, `[` are literal); smart punctuation is not applied.
- `wrist_verse.py` applies the same rules for the checker, and the two are tested against a shared case file.

## Publishing the poem

- **Style:** `poem` (`publish/poem/`). No separate title page.
- **PDF:** A5 by default (`trim:` overrides), Libertinus Serif at 11 pt with generous leading, margins that give the
  poem room, flush left, never justified or reflowed, indentation kept. A line too long for the page wraps with a
  hanging indent. A stanza that fits on a page is not split. The page number shows from the second page.
- **Heading block** (in the EPUB the contents need a heading first, so the dedication follows the title there):
  a `dedication:` in italic, the title if `titled` (bold), the author as an italic byline, and an
  `epigraph:` in italic. An untitled poem prints the byline and the verse with no title.
- **EPUB:** the same elements as classed blocks and a stylesheet; no separate title page; the navigation lists the
  working title as metadata, and no title appears on the page of an untitled poem.
- **Pipeline:** `pandoc --from verse.lua`, a filter that adds the heading block, and for the PDF a template of
  layout functions.

## Quality data

`poetry-prompt-rules.md` is adopted:

- **`quality.md` and the judgment checklist:** one simile at most, the concrete and unglamorous detail, no closing
  line that explains the poem, break against the syntax, vary texture and rhythm, withhold emotion and significance,
  no flattery of the subject or the reader, bend allusions, refuse symmetry (for forms that do not require it), let
  something go unresolved, no one-word thematic section titles, no title that summarizes the poem, and the
  "unjustifiable choice" (`Must keep`). The review process is added to the skill: delete the last line and check
  whether the poem is better, rebreak half of the lines that end at a natural pause, replace every banned word with
  a specific object.
- **`lint.json`** (anywhere scope, each with a positive and a negative sample): the banned words and their close
  relatives (starlight, threshold, void, cathedral, hymn, cradle, unfold, becoming, luminous, tapestry, whisper,
  echo, shatter, dance, ache, infinite, sacred, silence, and "moment"), reflexive similes (`like a`, `as if`,
  `as though`), emotion told (wept, trembled, tears fell), stock rhymes, archaic diction (`thee`, `o'er`, `'twas`),
  and the sunset ending. All advisory. Form-required repetition (refrains, `ends` words, forced rhyme words) is exempt
  from the repeat-word rule.

## Skill and documentation

- `SKILL.md` names the fourth profile, the skeleton, the catalog, the verse format and the `verse` command.
- `references/psg.md` (the fixed grammar), `references/verse.md` (verse format, advisory heuristics);
  `references/grammar.md` and `publishing.md` gain the `form` setting and the poem style.
- Templates under `assets/templates/poem/`. The root README names the profile; the four are complete.

## Example and tests

- **Example:** `assets/examples/counting/`: a villanelle, skeleton and poem, so refrains and rhyme are exercised.
- **Grammar:** parser tests per production and per error, expansion tests (counts, refrains, `ends`, `fresh`), each
  rule R0 to R12 pass and fail, every catalog form (line count, independently written refrain and rhyme tables).
- **Checks:** every error and every advisory estimate; the stand-in comparison; the catalog comparison; the title
  rule; the gate.
- **Reader and heuristics:** a shared case file for the Lua reader and `wrist_verse.py`; the syllable counter on a
  word list; the rhyme key on pairs.
- **Publish:** command planning, real builds, the Typst the filter produces, and rendered pages looked at in the
  trial (the suite has no PDF reader).
- **Trial (required for done):** a fresh headless session writes a short poem through all four phases; the PDF is
  looked at; defects are fixed or recorded.

## Out of scope

Collections of poems (one poem per project); terza rima, ghazal and rondeau; concrete and visual poems; prose
poems; scansion beyond the syllable and stress estimates; non-English heuristics; audio; exporting to TEI.

## Open decisions

Choices I made that were not given by you, to confirm during review:

1. The ten PSGv2 fixes above, in particular `refrain at` positions, `ends @list[k]`, `fresh` tags and dropping line
   identifiers.
2. `strict roles;` makes R3 to R5 opt-in, off by default. PSGv2's own sonnet example (5.1) fails R3's turn pattern
   (`pivot statement` against `pivot (image | question) (address | image) statement`), so it is valid only with roles
   not strict.
3. `named` compares the skeleton to the catalog; stanza division is exact unless the catalog entry is flexible.
4. The sestina's envoi is three lines, not six end words.
5. Each leading space of a verse line becomes an en space; the default paper is A5.
6. A `# Title` is a title only on the first line, and only when `titled` is true; the working title in the front
   matter is always required.
7. Advisory syllable and rhyme heuristics are English only.
8. A stanza stays whole on a page only when it fits one.
9. The byline is printed above an untitled poem.
