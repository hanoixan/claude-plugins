---
role: product | test | manifest
---
# data: <name>

<What this data is, who reads it, and why it has this shape.>

- **Source:** hand-authored | generated — <by what> | external — <from where>
- **Required:** always | conditional — <condition> | optional — <what is lost>
- **Failure modes:** <malformed input, drift, missing file, size blowups>
- **Depends on:** none | [<producer or upstream>](<path>)
- **Referred by:** [<Reader.symbol>](<path>)
- **Unknowns:** none

## Schema

```<jsonc | yaml | text | proto | sql>
<schema in the most convenient notation for the format>
```

## Generation

<Only if Source is generated. Describe the full pipeline from inputs to this file: where inputs come from, each transformation, how often it runs, and how output is validated. Link every tool, e.g. [build_index](../tools/build_index.py.skel.md).>

```bash
<development usage: the command to regenerate, fixture or sample flags>
```
