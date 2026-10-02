# Abstract systems

Skel can describe a subsystem before any host project, language, or platform is chosen. Examples are an undo system, a plugin architecture, offline sync, auth and session handling, a job queue, or feature flags. The result is a reusable design that you adapt to a concrete project later by answering its unknowns. A complete worked example lives in `assets/examples/undo-system/`; read it before writing your first abstract system.

## Authoring

1. **Write SYSTEM.md first.** Include scope (especially what is *out* of scope), a glossary, and the global decisions. In an abstract system, most global decisions are unknowns: language, runtime, concurrency model, persistence medium, and any host capability you are assuming.
2. **Use placeholder extensions.** Name stand-ins `.code`, `.data`, or `.iac`, and lay them out by concern (`skel/undo/`, `skel/integration/`, `skel/infra/`), not by any framework's conventions.
3. **Draw the host boundary explicitly.** Give the system a small interface stand-in that the host implements (in the example, `document_target`) and an integration stand-in that describes the glue the host writes (`host_binding`). Everything host-specific sits behind those two. Their unknowns are the adaptation questions.
4. **Describe signatures by meaning.** Write "`limit`: max steps or bytes retained", not `limit: int`. When the type matters to the design, record it as an unknown instead of picking one.
5. **Put persistence behind an `.iac` stand-in.** Even "maybe store it in a file" becomes a `# infrastructure:` with `## resource:` data requirements, so adapters see retention, size, and privacy requirements.
6. **Mark conditional parts.** Optional features (persistence, coalescing) get `Required: conditional — ...` and an unknown asking whether they are wanted. Each one's consequence says what to delete if the answer is no.
7. **Check it.** Run `skel_check.py check skel/`. Abstract trees must pass the full grammar; the checker only reports placeholders, it doesn't excuse them.

## Adapting to a project

1. Copy the system's `skel/` contents into the project's `skel/` tree, or start a new one.
2. Run `skel_check.py unknowns skel/` and walk the user through the answers. Do the host-boundary unknowns first, because they usually determine the language and layout.
3. Delete parts that were answered "not needed". Remove the stand-ins, then remove the links to them. Use `check` to find the dangling ones.
4. Write a mapping file from placeholder paths to real project paths and extensions, then apply it with `skel_mv.py` (its full path is in the Tools section of `SKILL.md`):

   ```bash
   python3 /full/path/to/skel_mv.py skel --map map.txt --dry-run
   python3 /full/path/to/skel_mv.py skel --map map.txt
   ```

   ```text
   # map.txt
   skel/undo/history.code.skel.md            skel/src/editor/undo/history.ts.skel.md
   skel/undo/history_snapshot.data.skel.md   skel/src/editor/undo/history_snapshot.json.skel.md
   skel/infra/history_store.iac.skel.md      skel/infra/undo_store.tf.skel.md
   ```

   `skel_mv.py` rewrites every relative link in the tree, including SYSTEM.md, so cross-references survive the move.
5. Make the stand-ins concrete. Replace meaning-only types with real ones, name the host's real classes in the integration stand-in, and link to existing host files where they exist.
6. Run `check`, then follow `implementing.md`.
