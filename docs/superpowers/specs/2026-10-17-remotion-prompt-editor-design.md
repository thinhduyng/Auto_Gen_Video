# Remotion prompt editor

## Outcome and agreed scope

Add an editor to the existing Video Factory web app. A user opens a completed
Remotion video, marks a time range, enters a natural-language request, optionally
attaches images, and receives a rendered revision to preview and accept.

Edits apply to whole overlapping scenes. Replacement scenes may be shorter or
longer; synchronization and smooth playback matter more than preserving the
original duration. Use a remote multimodal LLM to interpret requests and the
existing local Remotion/FFmpeg renderer to produce video. The editing interpreter
uses the user's Qwen API, independently of Gemini's existing drafting and asset
selection integrations. VieNeu remains the configured speech engine. Do not introduce LTX, local image/video models, or
generated executable code.

## Approach

Use a validated edit plan over the canonical script, asset manifest, and a small
set of animation settings. This reuses the existing scene templates and narration
pipeline and makes edits reproducible. Compared with direct MP4 manipulation,
this preserves editable text and diagrams. Compared with LLM-generated React,
it limits changes to operations the renderer can reliably support.

Start with Remotion only. Other engine outputs remain available through the
existing app; they do not participate in this editing flow.

## User flow

1. Open Edit on a completed Remotion result. Show its video and scene list.
2. Set start/end from the playhead or editable timestamp fields. Highlight all
   scenes overlapping the half-open interval [start, end). A boundary exactly at
   the next scene's start does not select that next scene. Show the expanded
   whole-scene range before submission; reject empty or out-of-bounds ranges.
3. Enter a request and optionally attach JPEG, PNG, or WebP images. Show image
   thumbnails and allow removal. Images can be replacement assets or references;
   their intended role is part of the edit request.
4. Submit once. Show interpreting, preparing assets/audio, rendering, and ready
   states, or a useful error. Persist the request and revision identity so browser
   refresh does not create another LLM call or render.
5. Show a plain-language change summary, actual affected scenes, and resulting
   duration alongside the preview. The original stays accessible.
6. Accept the revision as the editor's current version, discard it, or start a
   follow-up edit based on it. Publishing remains an explicit existing user
   action, extended to select the desired revision.

## Supported changes

- Change displayed text while retaining narration unless explicitly requested.
- Replace background images with uploaded images or a requested stock asset.
- Replace selected scene content/layout using supported canonical scene types.
- Replace a selected scene with multiple supported scenes, or combine the selected
  contiguous scenes, when requested; this is confined to the selected scene block.
- Change animation through explicit presets: fade, slide, zoom, and staggered
  reveals, with bounded timing parameters. Preserve current styling by default.
- Rewrite selected narration when requested, using the same configured voice.
- Adjust scene pacing with bounded visual hold time and animation timing. A
  visual-only edit does not implicitly truncate or speed up speech.

An uploaded reference image does not imply AI image synthesis. Use it directly
when requested, or use its visual context to choose supported layout/text/style
changes. Unsupported custom animation or new imagery requests return a clear
limitation rather than silently claiming success.

## Edit interpretation and validation

Use an editor-specific Qwen API adapter. Configure `EDITOR_LLM_BASE_URL`,
`EDITOR_LLM_API_KEY`, and `EDITOR_LLM_MODEL` server-side, independently of the
existing Gemini configuration. Use the user's Qwen deployment and exact model
identifier; do not hardcode a hosted provider, endpoint, or model name. Default
transport is an OpenAI-compatible chat-completions interface, subject to checking
the user's actual Qwen endpoint before implementation. No OpenAI service or SDK
is required by that protocol choice. Do not fall back to Gemini when editing
credentials are missing or Qwen fails; show a configuration or provider error.
Existing Gemini drafting and asset selection features retain their configuration.

Image understanding requires the selected Qwen model and endpoint to accept image
inputs. Keep uploaded replacement assets usable with a text-only model by passing
their IDs and user descriptions in the edit plan; show that visual reference
interpretation is unavailable instead of silently treating an unseen image as
understood. For a vision-capable endpoint, send normalized images in its supported
multimodal format. Validate structured responses in the backend regardless of
whether the endpoint offers JSON mode or schema-constrained output. Verify the
endpoint, model identifier, image support, and response format during setup;
provider smoke tests are separate from deterministic tests.

Send the request, selected stable scene IDs, relevant source scene data, adjacent
scene context, supported operations, and optional normalized images. Do not send
the complete movie by default. Scene content and uploaded images are input data,
not instructions to execute code or access files.

The response is a typed plan containing a summary and a replacement scene block,
asset references, animation settings, and any explicit narration/pacing changes.
Resolve assets by server-issued IDs. The model cannot choose filesystem paths,
run shell commands, change global voice/settings, or modify unselected scenes.

Validate scene requirements, diagram references, cue-to-narration matches, text
limits, finite duration bounds, selected-scene scope, and asset ownership before
creating render work. A validation failure may get one bounded repair attempt;
then show a clear error without altering the current revision. No fallback to an
unrelated rewrite of the whole video.

## Revision and asset model

Store editor data under the job's Remotion directory in separate revision folders,
outside the destructive legacy rerun path. Each revision records its parent,
source spec snapshot, stable scene IDs, request, normalized plan, owned assets,
timeline, per-scene narration/word timings, state, logs, thumbnail, and video.
Use atomic metadata writes and serialize conflicting state changes. A revision
always targets the exact parent shown when submitted; stale browser requests
must not silently edit a newer parent.

The original completed result is the baseline. Never overwrite it or the
published copy during editing. Legacy rerun must refuse to remove an engine
directory containing editor revisions, or preserve the editor store before any
cleanup. Acceptance and publication are distinct pointers. Follow-up edits use
the chosen revision's timeline, not the original timestamps.

Copy all required visual and audio inputs into persistent job-owned storage.
Remotion public-directory assets may be staged for rendering and cleaned up
afterward, but persistent revision sources must survive. Unselected scenes reuse
the parent's source assets and speech; do not randomly search for replacements
or regenerate their narration during each edit. Keep appropriate source credits
with each asset and carry them into publication.

For image uploads, check actual decoded format, file size and pixel limits;
normalize orientation and encoding and assign random server IDs. Reject SVG and
arbitrary paths/URLs as uploaded image assets. Apply the same path containment
rules used for jobs to revisions and assets.

## Timing and smoothness

Build scene timing from actual speech duration plus configured lead, gap, hold,
and tail values. Reuse cached or persisted per-scene speech for unchanged scenes;
generate new speech only for explicitly changed narration. Preserve voice
selection and speaking configuration across a revision.

When duration changes, rebuild all downstream scene offsets, word and phrase
timestamps, diagram cues, image beats, and total frame count from scene-local
data. Never patch only the final video's duration. Quantize scene boundaries
consistently at 30 fps and ensure all frames are covered exactly once in the
scene schedule. Clamp entrance/exit animation to the actual scene duration.

A visual-only shorter scene must still contain all its retained narration; if
the request cannot fit, explain the conflict instead of cutting speech. Longer
visual holds leave narration at its natural pace. Do not introduce automatic
speech time-stretching in this version.

Render the full revised Remotion composition initially. Keep the existing visual
style and supported entrance/exit behavior, with bounded presets for changes.
Smoothness means synchronized speech/captions, no accidental black frames or
overlapping speech, readable animation, and coherent adjacent scene boundaries;
it does not promise that arbitrary creative requests will look good without
preview and iteration.

## Existing origami video migration

Target job: 20261010-131144-origami-khoa-hoc-vu-tru. Its selected Remotion output
is 1080x1920, 30 fps, approximately 103.93 seconds, with nine scenes and VieNeu
narration. The original spec and Remotion props retain scene and word timings.

Remotion removes its staged images and narration WAV after rendering. The sibling
HyperFrames composition retains narration and image assets. Baseline import must
match assets using the recorded manifests/timing and file identity rather than
assume the sibling output is identical. Check the TTS and photo caches as well.
If exact per-scene speech is unavailable, recover it from the retained narration
or original MP4 using recorded audio boundaries; preserve existing word timings.
Use original audio as the unchanged baseline reference. Do not silently synthesize
a different voice or substitute unrelated images.

If a required original visual cannot be recovered, expose that missing asset and
require a replacement for that scene before promising a faithful source rerender.
The original MP4 remains usable regardless of import outcome.

## Backend and frontend boundaries

- Editor service: baseline import, persistent assets, typed requests/plans,
  validation, revision transitions, and acceptance.
- Qwen adapter: separately configured API transport, capability-aware multimodal
  request construction, and bounded response parsing.
- Remotion integration: persistent source inputs, animation configuration,
  scene-local timing reconstruction, and revision rendering.
- API: editor bootstrap/timeline, image upload, submit/status/list revisions,
  accept revision, and revision-aware publication. Background jobs expose status
  rather than keeping a rendering HTTP request open.
- Web UI: scene-aware range selection, prompt/images, progress, summary, preview,
  and version navigation within the current job detail screen.

Reuse the existing render worker infrastructure with explicit revision tasks;
do not route edits through jobs.rerun. Persist interrupted tasks as recoverable
failures on startup. Retrying render reuses the saved plan and assets without
calling the LLM again. Retrying a failed interpretation is an explicit action.

## Verification and acceptance

- Time ranges map correctly at exact boundaries and across multiple scenes.
- Plan validation blocks edits outside scope, invalid cue references, unsupported
  operations, and unknown asset IDs. Uploads cannot escape their storage directory.
- A longer or shorter replacement moves following scenes and their captions,
  image beats, and diagrams consistently, without dropping narration.
- Visual-only edits reuse speech; unchanged scenes retain assets and text.
- Revisions survive refresh/restart and retries do not duplicate interpretation.
  Existing results and published videos survive failures, edits, and rerun attempts.
- Use mocked LLM responses for deterministic integration tests and a short real
  Remotion render for media verification. Check frame rate, output duration,
  audio alignment and representative frames around edited scene boundaries.
- Exercise the origami import, one image/text change, one animation change, and a
  narration replacement with a different length. A live provider smoke test is
  conditional on configured credentials/network and is reported separately.

## Exclusions

No LTX or other generative video integration, new local model, free-form generated
React/JavaScript, arbitrary exact-second visual overrides, professional multitrack
timeline, or automatic changes to scientific claims. Full rerendering is accepted
for the initial implementation; incremental rendering is a later optimization.
