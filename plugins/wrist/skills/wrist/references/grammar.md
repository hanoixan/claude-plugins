# wrist grammar (normative)

`wrist_check.py check` enforces every rule marked **(checked)**.

## 1. Layout and naming

- Every file the work will contain has a stand-in at `wrist/<path>.wrist.md`, mirroring the project root. **(checked)** `wrist/work/the-lamp.md.wrist.md` stands in for `work/the-lamp.md`.
- The profile fixes the file shape. A required file with no stand-in, or a stand-in outside the shape, is an error. **(checked)** The story file is named from the slug in `PREMISE.md`.
- `wrist/PREMISE.md` is the one file that is not a stand-in. `wrist/.stamps` is written by `stamp`; do not edit it.
- Stand-ins take no front matter. A function (synopsis, outline, characters, misc, story) comes from the profile's file shape, not from the file. **(checked, warning)**

## 2. Headings and fields

- Each stand-in has exactly one level-1 heading, typed for its function: `# synopsis: <name>`, `# outline:`, `# characters:`, `# misc:`, `# story:`. **(checked)**
- Children are level-2 headings of the types the function declares (outline: `beat`; characters: `character`; misc: `place`, `object`, `concept`; story: `scene`). No deeper typed headings. **(checked)**
- Untyped headings may be used anywhere for organization.
- A field is a line `- **Label:** value` (the bold, the bullet and the colon placement are flexible). Fields belong to the nearest typed heading.
- Required fields per heading come from `profiles/<name>/profile.json`. **(checked)** For the short story: synopsis (Logline, Ending, Theme); outline (Structure) with beat (Purpose, Change); character (Wants, Flaw, Voice); place, object and concept (Facts); story (Point of view, Length) with scene (Purpose, Length, Must include, Must avoid).
- Every stand-in answers, anywhere in the file: `Required:` (`always`, `conditional: <when>` or `optional: <what is lost>`), `Rules:` (what the realization must follow), `Depends on:`, `Referred by:`, and unknowns (`*UNKNOWN*:` entries or `Unknowns: none`). Write `none` explicitly. **(checked)**
- Free prose under a heading is notes only; more than the profile's `max_prose_words` is a warning. **(checked, warning)** Fenced text does not count.

## 3. Links

```markdown
- **Depends on:** [Ines Vale](../character.md.wrist.md#character-ines-vale) (appears)
- **Referred by:** [scene: The mark](./work/the-lamp.md.wrist.md#scene-the-mark)
```

- Paths are relative to the file holding the link; a `#fragment` is the GitHub-style slug of a heading (`## character: Ines Vale` is `#character-ines-vale`). **(checked)**
- A dependency on another stand-in needs the matching `Referred by:` in the target, and the reverse. **(checked)** Write `Depends on:`, then run `fix-backlinks --write`.
- An optional relation word in parentheses after the link names the relation: for the short story `appears`, `mentions`, `sets up`, `pays off`, `realizes`. An unlisted word is a warning. **(checked, warning)**
- `Depends on:` may point at an external URL; `Referred by:` may not.

## 4. Unknowns

One line per unknown.

```markdown
*UNKNOWN*: [short-name] <what is unknown>. Kind: blocking | local. Proposed: <default>. Consequence: <what stays blocked>. Unlocks: <what becomes writable>.
*UNKNOWN*: Follows [short-name]. Consequence: <what the open decision means here>.
```

- `Kind:` is required; `Proposed:` is required for `local`. Names are unique across the tree and `PREMISE.md`. A follower must name a declared unknown. **(checked)**
- A **blocking** unknown changes what a file contains or whether it exists; a **local** one affects only a detail and carries a proposal.
- Anything you chose that the user did not state is an unknown with a `Proposed:`.
- Informal markers (TBD, TODO, FIXME, ???) outside fences are warned about. **(checked, warning)**

## 5. PREMISE.md

Front matter between `---` lines; one `- **<question-id>:** answer` line per profile question.

| Key | Meaning |
|---|---|
| `profile` | the profile in use **(checked)** |
| `title`, `slug` | required; the slug is lower-case words joined by hyphens **(checked)** |
| `author`, `language` | title page and metadata; `author` is needed to publish; `language` defaults to `en` |
| `trim`, `font` | optional PDF trim size (a Typst paper name) and font family |
| `questions_generation`, `questions_realization`, `questions_publishing` | `done` once that phase's questions were asked |
| `review_done` | `yes` once the review pass is finished |

A required question with no answer is an error; a deferrable one is a warning. An `*UNKNOWN*:` in the answer counts as an answer. **(checked)**

## 6. Fences

Every fence opens with three or more backticks (or tildes) and a language tag; use `text` for plain text. **(checked)** Fenced content is ignored for headings, fields, links and unknowns.

## 7. What a profile can add

A profile (`profiles/<name>/profile.json`) decides the file shape and what every stand-in must hold. Beyond the short story's fixed files it can declare:

- **`premise_keys`**: the `PREMISE.md` front matter keys it reads, each `bool` (`yes` or `no`, default no) or `int` (a whole number within `min` and `max`, optionally `required`). A wrong or missing required value is a `check` error that names the key. A question whose id is a premise key counts as answered when the front matter has the key.
- **`when`** on a file entry: the file exists only when that bool key is yes (`forward: yes` makes `work/forward.md`).
- **`family`** on a file entry: the file expands into one per number from 1 to the int key's value, with `{n}` in the path replaced by the number zero-padded to the width of the count. `check` requires exactly those stand-ins, so changing the count means changing the tree.
- **`required_when_realized`**: fields a stand-in must hold once its realized file exists. For a novel chapter this is `Established:`; `stamp` refuses a chapter without it and `gate publishing` reports it. Text on the same line, or on the lines that follow it up to a blank line, counts; an empty field does not.
- **`sequence`**: each file of a family should link to the one before it with the relation `continues`; `check` warns when it does not.
- **`heading_field`**: the field (for the novel, `Heading:`) whose value is the exact first line of the realized file, for example `# 7. The Long Wait`. `gate publishing` reports a realized file that starts with something else.
- **`title_page`**: whether the published book has a separate title page (default true; the short story sets it false).
- **`publish`**: an object with a `style` name that picks how the work is published: `story`, `book`, `screenplay` or `poem`. Without it the style is inferred: `book` when the profile has a `sequence` function, otherwise `story`. A profile with `style: screenplay` is written in Fountain (see `fountain.md`) and published in screenplay layout.
- **`form`**: for a poem profile, an object with the paths `structure` and `poem`, both listed in `files`. The structure file is a skeleton in the grammar of `psg.md`, the poem is plain verse (`verse.md`), and the `verse` command and `gate publishing` check the poem against the skeleton. A profile with `style: poem` is published in poem layout.
- **`lint_format`**: `prose` (the default) or `fountain`. It decides which scopes a lint pattern may use: `narration` or `anywhere` for prose; `action` (action lines only), `dialogue` (dialogue and parentheticals) or `anywhere` for Fountain.
