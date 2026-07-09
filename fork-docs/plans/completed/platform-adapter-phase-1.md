# Completed Platform Adapter Phase 1

Status: complete in `4eaea95 Add platform open-files adapter`.

## Goal

Remove the Linux-only `/proc/<pid>/fd` dependency from Codex rollout discovery while keeping rollout selection rules in `core/codex.py`.

## Result

* Added `core/platform/`.
* Added `open_files(pid)`.
* Implemented Linux open-file discovery with `/proc/<pid>/fd`.
* Implemented macOS open-file discovery with `lsof -nP -p <pid> -Fn`.
* Changed Codex live rollout attachment to consume open file paths instead of a `/proc` fd directory.
* Kept newest-rollout selection and rollout validation in `core/codex.py`.

## Notes

The platform layer returns process facts only. It does not decide which rollout is current, which session is stale, or which card state to show.

Later adapter boundary rules are maintained in `fork-docs/decisions/platform-adapter-boundaries.md`.
