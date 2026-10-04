# Fountain in wrist

The act files of a screenplay are written in Fountain, the plain-text screenplay format. wrist reads Fountain 1.1 with its own pandoc reader (`publish/screenplay/fountain.lua`). Write the way a screenwriter would; the reader decides what each line is.

## Elements

- **Scene heading:** a line starting `INT.`, `EXT.`, `EST.`, `INT./EXT.`, `INT/EXT` or `I/E` (any case), with a blank line before and after: `INT. FERRY DECK - NIGHT`. Force one that does not start that way with a leading `.`: `.THE BEACH`. A `..` start is not forced.
- **Action:** every other paragraph. One action beat per paragraph, four lines or fewer, present tense, only what the camera can see. A leading `!` forces action: `!MARIT`.
- **Character:** an upper-case line (letters, digits, and an optional extension in brackets such as `(V.O.)`, `(O.S.)`, `(CONT'D)`) with a blank line before it and dialogue right after it, no blank line between. Force a mixed-case name with a leading `@`: `@McCLOUD`. An upper-case line with no dialogue after it is action.
- **Dialogue:** the lines after a character cue, up to the blank line.
- **Parenthetical:** a line wrapped in brackets inside dialogue: `(quietly)`. Use sparingly.
- **Transition:** an upper-case line ending `TO:` with a blank line before and after (`CUT TO:`), or forced with a leading `>`: `> Burn to white.`
- **Centered:** `> THE END <`.
- **Page break:** a line of three or more `=`, for example `===`.
- **Emphasis:** `*italic*`, `**bold**` and `_underline_` (underline is typeset as italic).

## Line breaks

Every line break you type is kept, in action and in dialogue (Fountain takes every carriage return as intent). Write each action paragraph and each speech on one line, and break a line only where you want it broken: stacked beats, lyrics, a verse.

## Dropped

Notes `[[like this]]`, boneyard `/* like this */` (either may span lines), sections (lines starting `#`), synopses (lines starting a single `=`) and a Fountain title page (`key: value` lines at the very start of the text: Title, Credit, Author, Authors, Source, Notes, Draft date, Date, Contact, Copyright, Revision) are removed. The title page is built from `PREMISE.md` instead.

## wrist's own line

`@@ACT ONE@@` on a line of its own is a marker the publisher writes into `output/` before each act when `act_headings: yes`. Never write it into an act file; Fountain applications treat it as action.

## Not supported

Not supported: dual dialogue (`^` after a character) is read as ordinary sequential dialogue. Scene numbers (`#12#` at the end of a heading) are dropped. Revision marks and locked pages are not supported.
