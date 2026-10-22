# Decisions: data

Next ID: A4.

- **A1** **Roads: GRIP4 Region 2 rather than raw OSM.** For Colombia, GRIP4 blends OSM highways with IGAC photogrammetric mapping for lower road classes (Meijer et al. 2018). Informal roads remain undercounted, a limitation for any road dataset in this region.
- **A2** **CRS: EPSG:9377 (MAGNA-SIRGAS 2018 / Origen-Nacional) for all distances and areas.** Sources in EPSG:4326 are reprojected, or their pixel areas computed, before any metric calculation.
- **A3** **Raw inputs are read straight from their zip archives** (`zip://…!file.shp`). No extracted copies, and the archive's checksum identifies the version used.
