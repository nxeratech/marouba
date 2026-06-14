# After Effects Adapter Audit

Date: 2026-06-14

After Effects exposes a scripting object model for projects, comps, layers, properties, effects, expressions, and keyframes.

Relevant r1 surfaces:

- `CompItem` for composition dimensions, duration, frame rate, and layer collection.
- Layer APIs for solid/text/AV/shape layers.
- Property APIs including `keyTime(...)`, `keyValue(...)`, `setValueAtTime(...)`, interpolation/ease/tangent methods, and expression assignment.
- Effect match names for stable effect stack reconstruction.

Integrity rule: keyframe values must be captured exactly from the Property API. Approximation from pixels, graph shape, or UI gesture timing is refused.

File-level status: implemented with fake-runtime tests in `engine/aftereffects_adapter.py`. Real PASS still requires an After Effects capture script, recorded comp/keyframe/effect session, replay proof against comp state, 20-run soak at >=95%, and 3 real demo vaults.
