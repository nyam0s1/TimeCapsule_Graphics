# Current project status

Consolidated for publication on **16 November 2026**.

## Saved deliverable

- File: `TimeCapsule.blend`
- Saved-source SHA256: `05abeff689f13e4e8b8a92d5f36951fbcc5b84100211431030b2dff3e8b0e5f0`
- Latest saved authoring pass: TC14 shovel shape, 14 November.
- Planned duration: 7200 frames / 24fps = 300 seconds.
- Saved production configuration: Blender EEVEE, 1920x1080, 32 samples, motion blur enabled.
- Visible presentation: objects/environment; the historical human is hidden.

## Completed work

The saved scene includes the capsule/courtyard story, environment and props, continuous opening/ending camera motion, animated capsule/lid/shovel, vegetation development, weather, material ageing, an old shovel's deterioration, the revised pit, solar-driven day/night lighting, restrained stars/moon illumination, year labels and the redesigned digging blade/socket.

The current file is the authoring deliverable. The scripts in this repository explain selected procedural/animation changes; they are not intended to be replayed on the already-modified scene.

## Evidence and its limits

- Latest TC14 saved-file stills demonstrate the current shovel and several film frames.
- TC13 saved-file stills and its short day/night preview demonstrate the latest time/lighting system.
- TC9/TC10 clips demonstrate earlier continuous-camera and shovel motion; later appearance changes are absent from those clips.
- A complete five-minute MP4 exists locally from 8 November. Its date and sampled footage predate the current scene, so it has not been uploaded as the current final demo.
- No new render or Blender save was performed during repository publication. The authoring file and its local rolling backup remain intact; backups are excluded from Git.

## Remaining work

1. Review the entire latest time-lapse at normal playback speed. In particular, inspect the mostly-night windows/door shot and the brief sunrise/sunset intervals for readability.
2. Check the full current opening/ending, object movement, weather/lighting transitions and year progression together, resolving any issues that this review finds.
3. Perform final-resolution checks where needed, then render the current full sequence, encode the final MP4 and verify every frame and playback.
4. Prepare the final demonstration with annotated technique examples and an accurate account of what works and any remaining limitations.

Blender is allowed. No C++ rewrite is listed as a requirement of this accepted implementation choice, and no standalone OpenGL application is claimed.
