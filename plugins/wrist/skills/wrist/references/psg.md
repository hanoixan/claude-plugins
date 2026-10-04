# The poem grammar: PSGv2.1

`structure.md` is a **skeleton**: a document in this grammar that fixes a poem's form, its rhetorical shape and the
kind of material each slot holds, before any verse is written. It is PSGv2 (the poem skeleton grammar) with its
defects repaired; the changes are listed at the end. `wrist_check.py verse` parses it, checks the rules below and
checks the poem against it. The standard forms are ready-made skeletons in `profiles/poem/forms/`: copy one, keep
its `named "<form>";` line, and add what the poem needs. Write `custom` in the stand-in's `Form:` for a skeleton
of your own.

## Syntax

Terminals are in double quotes. `?` optional, `+` one or more, `*` zero or more, `|` alternatives. White space between
tokens is insignificant. Comments are `(* ... *)`.

```text
Poem      ::= "poem" "{" Decl* Stanza+ "}"
Decl      ::= Named | Title | Strict | Breaks | Rule | Refrain
Named     ::= "named" String ";"                  (* the catalog form this skeleton follows *)
Title     ::= "title" String ";"                  (* informational; ignored by the checker *)
Strict    ::= "strict" "roles" ";"                (* turn on the role rules R3 to R5 *)
Breaks    ::= "breaks" "flexible" ";"             (* the stanza division is not compared to the catalog form *)
Rule      ::= "let" Identifier "=" Value ";"
Value     ::= String | "[" (String ("," String)*)? "]"
Refrain   ::= "refrain" Identifier "at" Integer ("," Integer)+ ";"

Stanza    ::= "stanza" "(" Shape "," Count "," Rhyme ("," Role)? ")" "{" Line+ "}"
Shape     ::= "couplet" | "tercet" | "quatrain" | "quintain" | "sestet" | "septet" | "octave" | "free"
Count     ::= Integer (".." (Integer | "*"))?
Rhyme     ::= "none" | "fresh"? Tag+
Role      ::= "setup" | "develop" | "turn" | "resolve"

Line      ::= "line" "(" Meter "," Ending ("," "caesura" Integer)? "," Tag ("," "ends" Word)? ")" "{" Unit* "}"
Meter     ::= Foot Integer | "syllables" Integer (".." Integer)? | "free" | "stress" String
Foot      ::= "iamb" | "trochee" | "anapest" | "dactyl" | "spondee" | "amphibrach"
Ending    ::= "stop" | "run"
Tag       ::= "A" | "B" | ... | "Z" | "x"
Word      ::= "@" Identifier "[" Integer "]"

Unit      ::= Kind "[" String "]" ";"?
Kind      ::= "image" | "action" | "statement" | "pivot" | "question" | "address"
String    ::= '"' character* '"'                  (* a double quote inside is written \" *)
Identifier ::= letter (letter | digit | "_")*
Integer   ::= digit+
```

## What the pieces mean

| Piece | Meaning |
|---|---|
| `Shape` | The number of lines in the stanza: couplet 2, tercet 3, quatrain 4, quintain 5, sestet 6, septet 7, octave 8, `free` at least 1. |
| `Count` | How many times the stanza repeats: `3` exactly three; `2..5` two to five; `2..*` two or more. In `structure.md` the count is exact (R11); ranges belong to catalog entries. |
| `Rhyme` | One tag per line, in order. `none` means every line is `x`. Tags are poem-wide sound classes: lines sharing a tag rhyme, across stanzas. `x` is unrhymed. `fresh` renames the tags in each repeat, so every repeated stanza has its own sounds. |
| `Meter` | `iamb 5` is iambic pentameter (a foot name and a number of feet); `syllables 5` or `syllables 7..9` counts syllables; `free` fixes nothing; `stress "1010"` gives a pattern of stressed (1) and unstressed (0) syllables. Meter is a target: the checker only estimates it. |
| `Ending` | `stop` ends at a syntactic pause; `run` runs on (enjambment). |
| `caesura N` | A pause after the N-th foot, counting from 1, for foot meters. |
| `ends @list[k]` | The line's last word is exactly item k (counting from 0) of the `let` list. This is how a sestina's end words are fixed. |
| `refrain NAME at P1, P2, ...;` | The lines at these positions (counted from 1 in the whole poem) are the same line, word for word. The first position holds the units. All positions must have the same meter, ending and tag. A line is in at most one refrain. |
| `let` | A named string or list, referred to in hints as `@name` or `@name[k]`, and by `ends`. `@name[$n]` indexes by the stanza's repeat number, modulo the length of the list. |
| `named "form"` | The skeleton follows that catalog form; `verse` reports every difference (line count, rhyme scheme up to renaming letters, refrain positions, `ends` pattern, meter, and unless `breaks flexible;` the stanza division). |
| `Unit` | A slot for content of the given kind, with a hint in your own words (3 to 10 words). Units are optional. Do not copy a hint into the poem. |

### Roles and units (planning vocabulary)

Roles say what a stanza is for: **setup** establishes the scene with concrete material and a first claim;
**develop** extends it; **turn** is the volta, reversing or reframing what came before; **resolve** is a short close.
Unit kinds, each with a test: `image` (a concrete phrase a reader could draw), `action` (a verb of the body),
`statement` (an abstract claim arising from an image earlier in the stanza), `pivot` (a reversal, with a contrastive
word or an undermining question; deleting it should change the poem), `question` (left open), `address` (a
second-person plea or command). Roles and units are accepted anywhere. They are *checked* only under `strict roles;`.

## Rules

Checked by `verse`, each reported with the line of `structure.md` it concerns. R9 and R10 are advisory.

- **R0 References.** Every `@name` in a hint or `ends` names a `let`; an `ends` index is inside the list; `$n` appears
  only in a stanza repeated more than once.
- **R1 Rhyme length.** The rhyme has one tag per line and equals the line tags; `none` means all `x`.
- **R2 Shape.** A shape's line count is exact (`free`: at least 1).
- **R3 Role patterns** (strict roles only). A stanza's units, read in order, match its role exactly:
  setup `image image (action | image) statement`; develop `(image | action)+ statement?`; turn
  `pivot (image | question) (address | image) statement`; resolve `image statement`. Every stanza needs a role, and
  the poem ends on a statement.
- **R4 One turn** (strict roles only). Exactly one stanza is the turn.
- **R5 Earned statements** (strict roles only). A statement follows an image in its own stanza.
- **R6 Tags** are poem-wide unless the stanza's rhyme is `fresh`.
- **R7 Line count.** The expanded poem has the sum of shape lines times counts.
- **R8 Refrains.** Positions are inside the poem and rise; a line is in one refrain; the lines of a refrain share
  meter, ending and tag.
- **R9 Stress** (advisory). `verse` estimates syllables against the pattern's length. It cannot estimate which
  syllables are stressed (it has no pronouncing dictionary), so the pattern itself is for you and the reader.
- **R10 Caesura** (advisory). A line with `caesura N` has a pause (comma, dash or colon) inside it.
- **R11 Concrete.** Counts in `structure.md` are exact.
- **R12 Ends.** In the poem, every line with `ends @list[k]` ends with item k of the list.

## Using it

1. Decide the form first, quickly, and do not revisit it while writing. Copy a catalog skeleton when the form is one
   of them. Decide, for a poem of your own: stanzas and counts, shapes, meter, rhyme, refrains and `let` lists, and
   (if you want them) roles with exactly one turn.
2. Write the skeleton and run `wrist_check.py verse` until the skeleton has no errors. The only error left is that
   the poem file does not exist yet.
3. Write the poem into the skeleton. If a line fails, revise the line, not the skeleton.
4. Run `verse` again. Errors must be fixed; estimates are for your judgment.

## What changed from PSGv2

`refrain ... every N` became `refrain NAME at P1, P2, ...;` (a villanelle and a pantoum could not be written);
`@list[$n + k]` arithmetic became explicit `ends @list[k]` lines (the sestina rotation was only a cyclic shift);
`fresh` was added (tags were global, so a repeated stanza could not have its own rhymes); tags run A to Z instead of
A to H; `stress` takes only `1` and `0` (the old examples used a slash); role patterns are exact and optional
(`strict roles;`); `syllables` meters and the shapes `quintain` to `octave` were added; `named` and `breaks flexible`
were added; line identifiers were dropped; ranged counts are for catalog entries only (R11); R11 and R12 are new.
