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

# quick-look maps only
HYRIV := $(RAW)/hydrorivers/HydroRIVERS_v10_sa_shp.zip

.PHONY: all raw study input-quicklook db help

all: raw study

help:
	@echo "make raw   download missing raw inputs"
	@echo "make study study area and treatment table"
	@echo "make input-quicklook quick-look maps of the inputs (adds HydroRIVERS, ~95 MB)"
	@echo "make db    start PostGIS (docker compose)"

# --- setup ---
raw: $(RAW_FILES) $(IGAC_FILES)

# no prerequisites: raw files are fetched only when missing, never rebuilt
$(RAW_FILES):
	$(PY) scripts/setup/download_raw.py

$(HYRIV):
	$(PY) scripts/setup/download_raw.py --optional

# queried from a map service; the admin zip gives the study-area tiles
$(IGAC_FILES): $(RAW)/hdx_cod_ab/col-administrative-divisions-shapefiles.zip
	$(PY) scripts/setup/download_igac_drainage.py

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

# --- quick-look maps of the inputs ---
input-quicklook: figures/inputs/sources.png figures/inputs/rivers_el_doncello.png figures/inputs/treatment.png

figures/inputs/sources.png: scripts/setup/map_inputs.py $(STUDY_FILES) $(PROCESSED)/treatment_all.parquet \
		$(IGAC_FILES) $(RAW_FILES) $(HYRIV)
	$(PY) scripts/setup/map_inputs.py

# written by the same run as sources.png
figures/inputs/rivers_el_doncello.png figures/inputs/treatment.png: figures/inputs/sources.png ;

db:
	docker compose up -d
