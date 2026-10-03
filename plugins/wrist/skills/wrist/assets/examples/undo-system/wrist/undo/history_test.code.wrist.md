---
role: test
---
# module: history_test

Behaviour tests for the undo history, written against the `Command` and `UndoHistory` contracts so that they hold for any host. Each failure mode listed on those stand-ins is one case here.

- **Owns:** the test cases and a recording fake of `DocumentTarget`.
- **Access:** run by the host project's test runner; nothing else imports it.
- **Required:** always.
- **Failure modes:** a test that passes against the fake but not against the real document model. Keep the fake's behaviour to what `DocumentTarget` promises.
- **Depends on:** [UndoHistory](./history.code.wrist.md#class-undohistory)
- **Depends on:** [Command](./command.code.wrist.md#class-command)
- **Depends on:** [DocumentTarget](./document_target.code.wrist.md#class-documenttarget)
- **Referred by:** none known
- **Unknowns:** none

## function: test_undo_then_redo_restores_the_document

- **Inputs:** a fresh history over the fake target, and three pushed commands.
- **Returns:** nothing; the test fails on a mismatch.
- **State changes:** none outside the test.
- **Access:** the test runner.
