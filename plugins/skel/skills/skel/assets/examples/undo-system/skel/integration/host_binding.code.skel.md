# module: host_binding

Glue the host writes once to connect the undo system to its document lifecycle and UI. Described here so the integration contract is explicit, even though the code lives in the host project.

- **Owns:** the lifetime pairing of one `UndoHistory` with one open document.
- **Access:** called by the host's document-open path.
- **Required:** always.
- **Failure modes:** edits that bypass `UndoHistory.push` (direct model mutation) are not undoable; enforce by making the model's mutators private to commands where the language allows.
- **Depends on:** [UndoHistory](../undo/history.code.skel.md#class-undohistory)
- **Depends on:** [DocumentTarget](../undo/document_target.code.skel.md#class-documenttarget)
- **Referred by:** none known

*UNKNOWN*: The host's shortcut/menu system. Kind: blocking. Consequence: `bind_undo` can't name concrete APIs. Unlocks: a concrete binding and UI tests.

## function: bind_undo

- **Inputs:** the opened document's `DocumentTarget` implementation; the host's command/shortcut registry.
- **Returns:** the `UndoHistory` instance for the host to keep with the document.
- **State changes:** registers undo/redo shortcuts and menu items whose enabled state follows `can_undo`/`can_redo`; marks document dirty on any history change.
- **Access:** once per document open; the returned history is released on document close (after `serialize`, if persistence is on).
