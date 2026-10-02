# module: <module_name>

<What this module is for and why it exists as a separate unit. Include design intent and any guidance for the implementing agent.>

- **Owns:** <what this module is the source of truth for>
- **Access:** <how other modules reach it: import, injection, singleton, and so on>
- **Required:** always | conditional — <condition> | optional — <what is lost>
- **Failure modes:** <known ways this breaks, and the expected handling>
- **Depends on:** [<Symbol>](<./relative/path.ext.skel.md#class-symbol>)
- **Referred by:** [<Symbol>](<./relative/path.ext.skel.md#function-name>)

*UNKNOWN*: <what is unknown>. Consequence: <what is blocked or at risk>. Unlocks: <what becomes specifiable>.

## class: <ClassName>

<Responsibility, invariants, lifecycle.>

- **Inputs:** <construction parameters and their meaning>
- **State changes:** <instance state and the invariants that hold between calls>
- **Owns:** <resources, child objects>
- **Access:** <who creates it, who calls it, threading or ordering rules>

### function: <method_name>

<Behavior in prose. Edge cases.>

- **Inputs:** <param: meaning, constraints, type if known>
- **Returns:** <result, its meaning, error results>
- **State changes:** <externally visible mutations, or none>
- **Access:** <callers and call constraints>
- **Failure modes:** <optional, per function>

```<lang>
<only if code is the clearest way to state the contract>
```

## function: <free_function>

- **Inputs:** ...
- **Returns:** ...
- **State changes:** ...
- **Access:** ...
