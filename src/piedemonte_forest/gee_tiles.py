"""
Direct tiled download from Earth Engine (computePixels), on the native MapBiomas grid snapped around
the study area. No Drive, no Cloud Storage.
"""
import io
import time

import ee
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from shapely.geometry import box

RETRIES = 3


class Grid:
    """Native grid of `asset`, cut to the bounds of `aoi` (a shapely geometry in the asset CRS)."""

    def __init__(self, asset, aoi, tile):
        proj = ee.Image(asset).projection().getInfo()
        self.crs = proj["crs"]
        native = Affine(*proj["transform"])
        c0, r0 = map(int, np.floor(~native * (aoi.bounds[0], aoi.bounds[3])))
        c1, r1 = map(int, np.ceil(~native * (aoi.bounds[2], aoi.bounds[1])))
        self.transform = native * Affine.translation(c0, r0)
        self.width, self.height = c1 - c0, r1 - r0
        self.tile = tile
        self.aoi = aoi
        self.tiles = [(r, c) for r in range(0, self.height, tile) for c in range(0, self.width, tile)
                      if box(*rasterio.windows.bounds(((r, min(r + tile, self.height)), (c, min(c + tile, self.width))),
                                                      self.transform)).intersects(aoi)]

    def inside(self):
        return ~geometry_mask([self.aoi], (self.height, self.width), self.transform)

    def fetch(self, img, r, c, path):
        """Download one tile to `path`; returns its cost in EECU-s (0 if cached)."""
        if path.exists():
            return 0.0
        t = self.transform * Affine.translation(c, r)
        grid = {"dimensions": {"width": min(self.tile, self.width - c), "height": min(self.tile, self.height - r)},
                "affineTransform": {"scaleX": t.a, "shearX": t.b, "translateX": t.c,
                                    "shearY": t.d, "scaleY": t.e, "translateY": t.f},
                "crsCode": self.crs}
        for attempt in range(RETRIES):
            try:
                buf = io.StringIO()
                with ee.profilePrinting(destination=buf):
                    data = ee.data.computePixels({"expression": img, "fileFormat": "GEO_TIFF", "grid": grid})
                path.with_suffix(".part").write_bytes(data)
                path.with_suffix(".part").rename(path)
                return eecu_s(buf.getvalue())
            except Exception as e:
                if attempt == RETRIES - 1:
                    raise
                print(f"  tile {r},{c}: {e}; retrying")
                time.sleep(10 * (attempt + 1))

    def mosaic(self, tmp, dtype, fill):
        a = np.full((self.height, self.width), fill, dtype)
        for r, c in self.tiles:
            with rasterio.open(tmp / f"{r}_{c}.tif") as src:
                t = src.read(1)
            a[r:r + t.shape[0], c:c + t.shape[1]] = t
        return a


def eecu_s(profile):
    rows = [line.split() for line in profile.splitlines()[1:]]
    return sum(float(r[0]) for r in rows if r and r[0] != "-")
