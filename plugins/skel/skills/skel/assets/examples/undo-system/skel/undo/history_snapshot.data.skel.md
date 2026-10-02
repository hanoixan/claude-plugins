# data: history_snapshot

The persisted form of an `UndoHistory`, so undo survives closing and reopening a document.

- **Source:** generated, written at runtime by `UndoHistory.serialize`.
- **Required:** conditional, only if cross-session undo is a product requirement.
- **Failure modes:** schema drift between app versions (handled by `version`; unknown versions are discarded, never partially loaded); snapshot refers to a document revision that no longer matches (checked via `document_revision`).
- **Depends on:** none
- **Referred by:** [UndoHistory.serialize](./history.code.skel.md#function-serialize)
- **Referred by:** [history_store](../infra/history_store.iac.skel.md#resource-history_store)

*UNKNOWN*: [cross-session-undo] Whether cross-session undo is required. Kind: blocking. Consequence: if not, this stand-in, `serialize`, and the store resource are deleted. Unlocks: removing or committing to persistence.

## Schema

```jsonc
{
  "version": 1,                       // integer; bump on any breaking change
  "document_revision": "string",      // host's revision id the history applies to
  "cursor": 0,                        // index splitting undo (< cursor) from redo (>= cursor)
  "entries": [
    {
      "kind": "string",               // registered command type name
      "label": "string",              // describe() output, for menus before rehydration
      "payload": {}                   // command-specific; contract is an open unknown
    }
  ]
}
```

## Generation

Produced only by [UndoHistory.serialize](./history.code.skel.md#function-serialize) at document save/close. There is no offline pipeline. For development, generate fixtures by scripting a history in a test and serializing it:

```text
test helper: build_history(["insert:a", "insert:b", "group:[delete:1, insert:x]"]).serialize() -> fixtures/history_v1.json
```
