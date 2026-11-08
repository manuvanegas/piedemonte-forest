# Decisions

One file per topic. Entries are append-only: decision → why → what it affects, three lines at most. A replaced entry gets `[SUPERSEDED → X]` and keeps its text. New IDs follow the "Next ID" line in each file. Sources cited in any file go in `references.md`, so each topic file ends with its latest entry.

| File | Prefix | Covers |
|---|---|---|
| `design.md` | D | question, framing, outcome, treatment, timing |
| `data.md` | A | sources, covariates, CRS, storage |
| `references.md` | — | sources cited in the decision files |
