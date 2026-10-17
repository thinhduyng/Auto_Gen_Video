# Remotion Prompt Editor Implementation Plan

Goal: Edit whole scenes through prompts and uploaded images, using Qwen and local Remotion rendering.
Spec: ../specs/2026-10-17-remotion-prompt-editor-design.md

Architecture: Persist editable scene-local bundles separately from disposable render directories.
A Qwen adapter returns validated scene replacements; a renderer rebuilds absolute timings and
produces immutable previews. Acceptance and publication are explicit operations.

Global constraints: Remotion only; 30 fps; flexible duration; no local AI models except existing
TTS; no LTX; no generated executable code; credentials never logged or committed.

## Commit 1: Qwen interpreter and revision backend
- [x] Write and run failing unittest cases for boundary selection, timeline rebasing, scoped
  replacements, image validation, revision recovery, and sanitized provider errors.
- [x] Implement factory/editor_models.py, editor_llm.py, editor.py: typed edit plans,
  persistent per-scene source/audio/assets, baseline import, job-scoped image uploads,
  revision submission/status/retry/accept/publication, and background processing.
- [x] Integrate editor API router and protect legacy rerun. Test invalid/stale inputs and
  idempotent submission. Add server-side editor environment settings to .env.example.
- [x] Run backend tests and commit the coherent backend with design documentation.

## Commit 2: Remotion revision rendering
- [x] Test scene timing rebasing with changed speech and retained image beats/diagram cues.
- [x] Add persistent sources to ordinary Remotion renders and editor revision rendering.
  Preserve unchanged scene audio; synthesize changed narration; rebuild all timestamps.
- [x] Add bounded scene animation presets and duration holds; support uploaded image assets.
- [x] Verify TypeScript and source media metadata; commit renderer. Chrome boundary-frame
  verification was attempted but blocked by host socket restrictions.

## Commit 3: Scene editor UI and end-to-end verification
- [x] Add editor dialog, player time markers, scene selection, image attachments, prompt,
  revision status/preview/accept/discard/retry/publish controls and refresh recovery.
- [x] Test actual ASGI API flow and browser logic against deterministic mocked responses.
  Node VM tests cover submit/discard/resubmit/accept; real-browser testing remains blocked.
- [ ] Complete live Qwen and browser-render verification. Requests were attempted but DNS
  and local sockets are blocked by this execution environment. Speech-duration changes
  are tested with deterministic speech fixtures; actual VieNeu integration awaits host access.
- [x] Run full tests, document configuration/limitations, review diff for secrets, commit UI.

Review focus: Exact scene boundaries; missing legacy assets; concurrent or stale revisions;
provider errors containing credentials; narration longer than requested visual duration.
All five require regression coverage. No automatic fallback to Gemini for interpretation.

Execution: Inline in this session, as authorized by the user's develop/test/commit request.
Use a feature branch in the existing checkout to retain ignored local media and credentials.


## Execution results

- Backend and renderer commits: 99bc1b5, 5007ff3. Third commit groups UI, documentation,
  smoke command, and review-driven regressions, matching the requested commit granularity.
- Original origami video imported with nine scenes, all images recovered, original audio
  retained, and 103.933333-second timeline. All nine source scenes validate and compile.
- New editor tests cover HTTP serialization, request idempotency, retry without another LLM
  call, image normalization, timing/phrase/cue rebasing, malformed plans, source protection,
  and interrupted or failed metadata writes.
- Independent review found shared-diagram fading, missing flow direction, malformed diagram
  validation, repeated discarded request IDs, rerun/import races, and floating-point frame
  rounding. Each has a regression test and a correction. Review follow-up found missing-type
  KeyError; it is now a repairable validation error with coverage.
- Full Python suite was attempted: socket-dependent server tests error, and TestClient hangs
  even with a trivial FastAPI application because its cross-thread wakeup socket is denied.
  The remaining offline suite passes. No claim of a fully green unrestricted suite or
  successful live Qwen/Chrome test is made.
- Reproduce on the user's unrestricted machine with the commands in README's editor section.
  The live smoke command never accepts or publishes a revision automatically.
