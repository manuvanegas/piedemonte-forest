# Decisions: data

Next ID: A6.

- **A1** [SUPERSEDED → A5] **Roads: GRIP4 Region 2 rather than raw OSM.** For Colombia, GRIP4 blends OSM highways with IGAC photogrammetric mapping for lower road classes (Meijer et al. 2018). Informal roads remain undercounted, a limitation for any road dataset in this region.
- **A2** **CRS: EPSG:9377 (MAGNA-SIRGAS 2018 / Origen-Nacional) for all distances and areas.** Sources in EPSG:4326 are reprojected, or their pixel areas computed, before any metric calculation.
- **A3** **Raw inputs are read straight from their zip archives** (`zip://…!file.shp`). No extracted copies, and the archive's checksum identifies the version used.
- **A4** **Rivers: IGAC 1:100.000 drainage (single- and double-line), queried from IDEAM's republication of the IGAC layers.** Digitised from imagery, covers rivers of all widths and carries names; IGAC's own server was unavailable (2026-10-23). The copy has no capture dates and no perennial/intermittent attribute. HydroRIVERS v1.0, modelled from SRTM elevation, is kept as a comparison.
- **A5** **Roads: GRIP4 as the pre-ceasefire road network.** Within the study area GRIP4 is 99.9% IGAC mapping dated 2012 (its source and year attributes), with no ferry or river-route class. Distance to road therefore means distance to the network as it stood before the ceasefire (D3). Roads opened later are not observed; clearing that follows them is captured by distance to earlier clearing, updated every year. Informal roads are undercounted.
