"""
Loss patches from a packed loss raster (code = to_class * 100 + sec_age, 0 = no loss; see
download_loss.py). Shared by vectorize_loss.py and check_patch_sizes.py.
"""
import numpy as np
import pandas as pd
from rasterio.features import shapes
from scipy import ndimage
from shapely.geometry import shape

import loss_rule as lr


def decode(code):
    """(loss 0/1, to_class, sec_age) arrays from the packed code."""
    return (code > 0).astype(np.uint8), code // 100, code % 100


def label_components(loss, connectivity=4):
    """Connected components of a 0/1 loss array.

    Returns (labels, n_px):
      labels: int32 array, same shape as loss; 0 = no loss, 1..n = component id.
      n_px:   int array of length n + 1; n_px[i] = pixels in component i, n_px[0] = 0.
    connectivity: 4 (edges only) or 8 (edges and corners).
    """
    structure = ndimage.generate_binary_structure(2, 1 if connectivity == 4 else 2)
    labels, n = ndimage.label(loss, structure=structure)
    n_px = np.bincount(labels.ravel(), minlength=n + 1)
    n_px[0] = 0  # background, not a patch
    return labels, n_px


def patch_attributes(labels, n_px, to_class, sec_age):
    """One row per component (index patch_id = label, 1..n).

    Columns:
      n_px             pixels in the patch
      secondary_share  share of its pixels with sec_age > 0
      sec_age_mean     mean sec_age over its secondary pixels (NaN if none)
      to_class         majority destination class
      share_<c>        share of its pixels going to class c, for every c in lr.ANTHRO
    """
    m = labels > 0
    labs, clss, ages = labels[m], to_class[m], sec_age[m]

    def per_patch(weights):
        return np.bincount(labs, weights=weights, minlength=len(n_px))[1:]

    npx = n_px[1:]
    n_sec = per_patch(ages > 0)
    with np.errstate(invalid="ignore"):
        sec_age_mean = per_patch(ages) / n_sec  # 0/0 = NaN: no secondary pixels
    shares = {f"share_{c}": per_patch(clss == c) / npx for c in lr.ANTHRO}
    majority = np.array(lr.ANTHRO)[np.column_stack(list(shares.values())).argmax(axis=1)]
    return pd.DataFrame({"n_px": npx, "secondary_share": n_sec / npx, "sec_age_mean": sec_age_mean,
                         "to_class": majority, **shares},
                        index=pd.Index(np.arange(1, len(n_px)), name="patch_id"))


def polygonize(labels, transform):
    """(patch_ids, polygons) lists. 4-connected labels only: then each label is one polygon."""
    pairs = shapes(labels, mask=labels > 0, connectivity=4, transform=transform)
    ids, geoms = zip(*((int(v), shape(g)) for g, v in pairs))
    return list(ids), list(geoms)
