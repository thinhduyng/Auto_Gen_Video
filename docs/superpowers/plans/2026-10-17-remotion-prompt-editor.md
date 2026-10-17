# Remotion Prompt Editor Implementation Plan

Goal: Edit whole scenes through prompts and uploaded images, using Qwen and local Remotion rendering.
Spec: ../specs/2026-10-17-remotion-prompt-editor-design.md

Architecture: Persist editable scene-local bundles separately from disposable render directories.
A Qwen adapter returns validated scene replacements; a renderer rebuilds absolute timings and
produces immutable previews. Acceptance and publication are explicit operations.

Global constraints: Remotion only; 30 fps; flexible duration; no local AI models except existing
TTS; no LTX; no generated executable code; credentials never logged or committed.

## Commit 1: Qwen interpreter and revision backend
- [ ] Write and run failing unittest cases for boundary selection, timeline rebasing, scoped
  replacements, image validation, revision recovery, and sanitized provider errors.
- [ ] Implement factory/editor_models.py, editor_llm.py, editor.py: typed edit plans,
  persistent per-scene source/audio/assets, baseline import, job-scoped image uploads,
  revision submission/status/retry/accept/publication, and background processing.
- [ ] Integrate editor API router and protect legacy rerun. Test invalid/stale inputs and
  idempotent submission. Add server-side editor environment settings to .env.example.
- [ ] Run backend tests and commit the coherent backend with design documentation.

## Commit 2: Remotion revision rendering
- [ ] Test scene timing rebasing with changed speech and retained image beats/diagram cues.
- [ ] Add persistent sources to ordinary Remotion renders and editor revision rendering.
  Preserve unchanged scene audio; synthesize changed narration; rebuild all timestamps.
- [ ] Add bounded scene animation presets and duration holds; support uploaded image assets.
- [ ] Verify TypeScript, media metadata and representative boundary frames; commit renderer.

## Commit 3: Scene editor UI and end-to-end verification
- [ ] Add editor dialog, player time markers, scene selection, image attachments, prompt,
  revision status/preview/accept/discard/retry/publish controls and refresh recovery.
- [ ] Test API flow and browser behavior against deterministic mocked Qwen responses.
- [ ] Exercise a small real Qwen request using configured credentials; render an origami
  revision and test longer/shorter narration where speech service is available.
- [ ] Run full tests, document configuration/limitations, review diff for secrets, commit UI.

Review focus: Exact scene boundaries; missing legacy assets; concurrent or stale revisions;
provider errors containing credentials; narration longer than requested visual duration.
All five require regression coverage. No automatic fallback to Gemini for interpretation.

Execution: Inline in this session, as authorized by the user's develop/test/commit request.
Use a feature branch in the existing checkout to retain ignored local media and credentials.
