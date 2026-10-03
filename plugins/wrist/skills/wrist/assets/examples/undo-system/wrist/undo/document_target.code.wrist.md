---
role: product
---
# module: document_target

The narrow interface the host application exposes so commands can mutate the document without depending on the host's concrete model. Keeping this boundary small is what makes the undo system portable: everything host-specific lives behind it.

- **Owns:** nothing; this is an interface definition.
- **Access:** imported by command implementations; implemented once by the host.
- **Required:** always.
- **Failure modes:** host implementation raises during mutation; see `Command.apply`.
- **Depends on:** none
- **Referred by:** [Command](./command.code.wrist.md#class-command)
- **Referred by:** [host binding](../integration/host_binding.code.wrist.md#function-bind_undo)

*UNKNOWN*: Shape of the host's document model (tree, flat records, text buffer). Kind: blocking. Consequence: `DocumentTarget` can only be described as an opaque handle plus change notification. Unlocks: typed accessor methods and more precise command payloads.

## class: DocumentTarget

An opaque handle to the editable document plus a change-notification hook. Commands receive it as an argument; they never store it, so history can outlive a document reload as long as the host re-binds.

- **Inputs:** constructed by the host; no inputs defined by this system.
- **State changes:** none of its own; mutations are the host model's.
- **Owns:** nothing.
- **Access:** passed into `Command.apply` / `Command.revert` by `UndoHistory`; never global.
- **Referred by:** [history_test](./history_test.code.wrist.md)

### function: notify_changed

Called after any command mutates the document so the host can re-render and recompute derived state.

- **Inputs:** a change description (opaque to this system; produced by the command).
- **Returns:** nothing.
- **State changes:** host-defined (re-render, dirty flag).
- **Access:** called by commands at the end of `apply` and `revert`, exactly once per call.
