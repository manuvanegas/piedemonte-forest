# Run order of the pipeline. Each target is an output file; make rebuilds only what's missing or older than its inputs.
# Works with GNU Make 3.81 (macOS default).

PY ?= python
RAW := data.nosync/raw
PROCESSED := data.nosync/processed

RAW_FILES := \
	$(RAW)/hdx_cod_ab/col-administrative-divisions-shapefiles.zip \
	$(RAW)/runap/runap_latest.zip \
	$(RAW)/grip4/GRIP4_Region2_vector_shp.zip \
	$(RAW)/prem2020/RepliDataset.zip

IGAC_FILES := \
	$(RAW)/igac_drenaje/drenaje_sencillo.parquet \
	$(RAW)/igac_drenaje/drenaje_doble.parquet

RESGUARDOS := $(RAW)/ant_resguardos/resguardos.parquet

# quick-look maps only
HYRIV := $(RAW)/hydrorivers/HydroRIVERS_v10_sa_shp.zip

.PHONY: all raw study loss covariates input-quicklook db help

all: raw study

help:
	@echo "make raw   download missing raw inputs"
	@echo "make study study area and treatment table"
	@echo "make loss  annual loss rasters (Earth Engine) and loss patches"
	@echo "make covariates patch distances (needs make db)"
	@echo "make input-quicklook quick-look maps of the inputs (adds HydroRIVERS, ~95 MB)"
	@echo "make db    start PostGIS (docker compose)"

# --- setup ---
raw: $(RAW_FILES) $(IGAC_FILES) $(RESGUARDOS)

# no prerequisites: raw files are fetched only when missing, never rebuilt
$(RAW_FILES):
	$(PY) scripts/setup/download_raw.py

$(HYRIV):
	$(PY) scripts/setup/download_raw.py --optional

# queried from a map service; the admin zip gives the study-area tiles
$(IGAC_FILES): $(RAW)/hdx_cod_ab/col-administrative-divisions-shapefiles.zip
	$(PY) scripts/setup/download_igac_drainage.py

# queried from ANT's feature service; fetched only when missing
$(RESGUARDOS):
	$(PY) scripts/setup/download_resguardos.py

# --- study area and treatment ---
STUDY_FILES := $(PROCESSED)/study_municipios.parquet $(PROCESSED)/study_area.parquet

study: $(STUDY_FILES) $(PROCESSED)/treatment.parquet

$(STUDY_FILES): scripts/setup/define_study_area.py $(RAW)/hdx_cod_ab/col-administrative-divisions-shapefiles.zip
	$(PY) scripts/setup/define_study_area.py

$(PROCESSED)/treatment.parquet: scripts/setup/join_treatment.py scripts/setup/prem_municipio_aliases.csv \
		$(PROCESSED)/study_municipios.parquet $(RAW)/prem2020/RepliDataset.zip
	$(PY) scripts/setup/join_treatment.py

# written by the same run as treatment.parquet
$(PROCESSED)/treatment_all.parquet: $(PROCESSED)/treatment.parquet ;

# --- loss ---
YEARS := $(shell seq 2008 2023)
LOSS_TIFS := $(YEARS:%=$(PROCESSED)/loss/loss_%.tif)
PATCHES := $(YEARS:%=$(PROCESSED)/loss_patches/patches_%.parquet)
# earlier clearings for 2008-2010 only (D14)
LOOKBACK_YEARS := 2005 2006 2007
LOOKBACK_TIFS := $(LOOKBACK_YEARS:%=$(PROCESSED)/loss/loss_%.tif)
LOOKBACK_PATCHES := $(LOOKBACK_YEARS:%=$(PROCESSED)/loss_patches/patches_%.parquet)

loss: $(PATCHES) $(LOOKBACK_PATCHES)

# Earth Engine, ~5 min and ~1.8 EECU-h a year. No prerequisites: fetched only when missing, never
# rebuilt because a script changed (delete the file to refetch)
$(LOSS_TIFS) $(LOOKBACK_TIFS):
	$(PY) scripts/loss/download_loss.py $(patsubst $(PROCESSED)/loss/loss_%.tif,%,$@)

$(PROCESSED)/loss_patches/patches_%.parquet: $(PROCESSED)/loss/loss_%.tif scripts/loss/vectorize_loss.py \
		src/piedemonte_forest/patch_tools.py $(STUDY_FILES) $(PROCESSED)/treatment.parquet
	$(PY) scripts/loss/vectorize_loss.py $*

# Earth Engine, ~0.25 EECU-h; fetched only when missing, like the loss rasters
$(PROCESSED)/slope/slope.tif:
	$(PY) scripts/covariates/download_slope.py

# --- patch covariates (PostGIS; start it with make db) ---
covariates: $(PROCESSED)/covariates/protected_areas.parquet $(PROCESSED)/covariates/roads.parquet \
		$(PROCESSED)/covariates/rivers.parquet $(PROCESSED)/covariates/resguardos.parquet \
		$(PROCESSED)/covariates/earlier_clearings.parquet $(PROCESSED)/covariates/slope.parquet

# Empty stamp file: all patches are in PostGIS (~3 min). Make can't see inside the database, so
# delete the stamp if the database volume is reset
DB_PATCHES := $(PROCESSED)/db/patches.loaded

$(DB_PATCHES): $(PATCHES) scripts/loss/load_patches.py
	$(PY) scripts/loss/load_patches.py
	@mkdir -p $(@D) && touch $@

DB_LOOKBACK := $(PROCESSED)/db/lookback_patches.loaded

$(DB_LOOKBACK): $(LOOKBACK_PATCHES) scripts/loss/load_patches.py
	$(PY) scripts/loss/load_patches.py --lookback
	@mkdir -p $(@D) && touch $@

# ~5 min
$(PROCESSED)/covariates/protected_areas.parquet: $(DB_PATCHES) $(RAW)/runap/runap_latest.zip \
		$(PROCESSED)/study_area.parquet scripts/covariates/load_targets.py scripts/covariates/distance_protected_areas.py src/piedemonte_forest/patch_distances.py
	$(PY) scripts/covariates/load_targets.py --runap
	$(PY) scripts/covariates/distance_protected_areas.py

# ~7 min
$(PROCESSED)/covariates/roads.parquet: $(DB_PATCHES) $(RAW)/grip4/GRIP4_Region2_vector_shp.zip \
		$(PROCESSED)/study_area.parquet scripts/covariates/load_targets.py scripts/covariates/distance_roads.py \
		src/piedemonte_forest/patch_distances.py
	$(PY) scripts/covariates/load_targets.py --roads
	$(PY) scripts/covariates/distance_roads.py

$(PROCESSED)/covariates/resguardos.parquet: $(DB_PATCHES) $(RESGUARDOS) \
		$(PROCESSED)/study_area.parquet scripts/covariates/load_targets.py scripts/covariates/distance_resguardos.py \
		src/piedemonte_forest/patch_distances.py
	$(PY) scripts/covariates/load_targets.py --resguardos
	$(PY) scripts/covariates/distance_resguardos.py

# --- quick-look maps of the inputs ---
input-quicklook: figures/inputs/sources.png figures/inputs/rivers_el_doncello.png figures/inputs/treatment.png

figures/inputs/sources.png: scripts/setup/map_inputs.py $(STUDY_FILES) $(PROCESSED)/treatment_all.parquet \
		$(IGAC_FILES) $(RAW_FILES) $(RESGUARDOS) $(HYRIV)
	$(PY) scripts/setup/map_inputs.py

# written by the same run as sources.png
figures/inputs/rivers_el_doncello.png figures/inputs/treatment.png: figures/inputs/sources.png ;

db:
	docker compose up -d

$(PROCESSED)/covariates/rivers.parquet: $(DB_PATCHES) $(RAW)/igac_drenaje/drenaje_doble.parquet \
		$(PROCESSED)/study_area.parquet scripts/covariates/load_targets.py scripts/covariates/distance_rivers.py \
		src/piedemonte_forest/patch_distances.py
	$(PY) scripts/covariates/load_targets.py --rivers
	$(PY) scripts/covariates/distance_rivers.py

# ~6 min
$(PROCESSED)/covariates/earlier_clearings.parquet: $(DB_PATCHES) $(DB_LOOKBACK) \
		scripts/covariates/distance_earlier_clearings.py src/piedemonte_forest/patch_distances.py
	$(PY) scripts/covariates/distance_earlier_clearings.py

# local, ~5 min; no PostGIS
$(PROCESSED)/covariates/slope.parquet: $(PATCHES) $(PROCESSED)/slope/slope.tif scripts/covariates/slope_per_patch.py \
		src/piedemonte_forest/patch_tools.py
	$(PY) scripts/covariates/slope_per_patch.py
