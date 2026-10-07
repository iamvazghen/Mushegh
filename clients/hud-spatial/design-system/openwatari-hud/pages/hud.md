# HUD page override

This page-level system supersedes the generic dashboard suggestions in `MASTER.md` where they conflict with the established OpenWatari product context.

- Pattern: Workbench on a fixed 12x12 spatial mesh.
- Persistent regions: one centered command/search field and the canvas mesh only. No navbar, sidebar, toolbar, dock, or footer.
- Type: locally bundled IBM Plex Sans and IBM Plex Mono; no network font origin.
- Surfaces: Midnight blue-black, restrained cyan focus, purple only for active processing, red only for errors/required action, green only for a live/nominal source.
- Shape: 18px canvas radius, 14px command radius, 10px controls; fine borders rather than heavy elevation.
- Motion: 350ms spring layout morph, 180ms controls, zero duration under reduced motion. Infinite animation is reserved for a real loading state.
- Data: measured snapshot data, local user files, or explicit missing-source states only. Never fabricate telemetry or progress.
- Responsive: four quarters at desktop; one readable vertical stack below 640px. Touch controls remain at least 38px within the dense instrument surface.

