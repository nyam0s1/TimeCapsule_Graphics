# Graphics techniques and source map

The authoritative result is `TimeCapsule.blend`. The source links below document selected incremental authoring passes whose results are already saved in that file.

| Graphics topic | Scene example | Implementation/evidence |
| --- | --- | --- |
| Vertices, edges and polygon meshes | Profiled shovel blade, tapered socket, uneven soil pit | [Shovel mesh pass](../renders/stills/shovel_check/shovel_shape.py), [pit/time pass](../renders/stills/time_pass_check/time_pass.py) |
| Parametric construction | Blade cross-sections, circular socket rings and pit wall rings | `blade_point`, `build_blade`, `build_socket` and the pit generation in the linked scripts |
| Translation | Capsule moving into/out of the pit; camera travel | [Continuous animation source](../renders/stills/no_human_check/continuous.py) |
| Rotation and pivots | Capsule lid hinge and old shovel's fall/break | [Continuous source](../renders/stills/no_human_check/continuous.py), [old-shovel source](../renders/stills/no_human_check/old_shovel.py) |
| Scaling and animated properties | Tree/grass development and seasonal vegetation changes | Saved keyframes and [time pass](../renders/stills/time_pass_check/time_pass.py) |
| Curves/interpolation | Smooth camera motion and eased prop movement | `pchip` and `ss` in [continuous.py](../renders/stills/no_human_check/continuous.py) |
| Hierarchical transforms | Capsule hinge and broken upper shovel shaft relative to its root | Saved parent-child relationships and [old_shovel.py](../renders/stills/no_human_check/old_shovel.py) |
| Perspective/cameras | Wide environment views, close-ups and continuous opening/ending camera moves | Camera/lens keyframes in the Blender file and the continuous source |
| Materials and texturing | Rust, lichen, wood fading, paper yellowing and photograph ageing | [Ageing/look source](../renders/stills/no_human_check/look_pass.py), [old shovel](../renders/stills/no_human_check/old_shovel.py) |
| Lighting and atmospheric effects | Sun direction, daylight, moon/night floor, twilight and haze | `solar`, `airmass`, `transmit`, `skylight` and keyed/driven properties in [time_pass.py](../renders/stills/time_pass_check/time_pass.py) |
| Compositing | Resolution-aware year counter | Year atlas and compositor construction in [time_pass.py](../renders/stills/time_pass_check/time_pass.py) |

## Calculation examples

Smoothstep uses `s(t) = t*t*(3 - 2*t)` for a clamped progress value in `[0,1]`. It eases an interpolation so that motion starts and ends with zero slope.

The camera's PCHIP implementation computes local slopes and limits them to maintain monotonicity. Translation, rotation and scale then act on the saved scene objects through Blender's transform/keyframe system.

The solar model computes altitude/direction from latitude, declination and hour angle, then applies atmospheric transmission and sky/twilight factors. Season/declination, exposure adaptation and timing are art directed. The visual day/night cycles communicate years through the counter; they are not a literal simulation of every day in the 25-year period.

## Scope of the claims

Blender supplies the renderer, clipping, rasterisation, material evaluation and much of the transform/keyframe infrastructure. The project does not claim to implement a renderer or OpenGL bindings from scratch. The older Rust human solver is outside the current visible, non-human presentation and is not required to open the submitted scene.
