# Asset provenance

## Project source and generated geometry

The Blender scene and the selected Python authoring passes contain project-specific geometry, animation, material work and composition. The repository includes `textures/photo_1995.png` as the scene's photograph asset and the generated year-label atlas beside `time_pass.py`.

The year atlas is already packed in the saved Blender file. Regenerating it with `make_atlas.py` requires Pillow and the named font or a suitable replacement; the system font itself is not redistributed here.

## Environment textures and HDRIs

The project's texture manifest records the following Poly Haven assets as CC0:

- [Kloofendal partly cloudy sky](https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky)
- [Overcast soil sky](https://polyhaven.com/a/overcast_soil_puresky)
- [Brown bark 02](https://polyhaven.com/a/bark_brown_02)
- [Dirt](https://polyhaven.com/a/dirt)
- [Plastered wall 04](https://polyhaven.com/a/plastered_wall_04)

See [the recorded asset manifest](assets_polyhaven.json) for the source URLs, file names, resolutions and hashes. These environment assets were packed during the graphics pass; this publication does not download or alter them.

No new repository-wide software/artwork license has been assigned as part of this upload. Third-party assets retain their own applicable terms.
