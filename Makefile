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

.PHONY: all raw db help

all: raw

help:
	@echo "make raw   download missing raw inputs"
	@echo "make db    start PostGIS (docker compose)"

# --- setup ---
raw: $(RAW_FILES)

# no prerequisites: raw files are fetched only when missing, never rebuilt
$(RAW_FILES):
	$(PY) scripts/setup/download_raw.py

db:
	docker compose up -d
