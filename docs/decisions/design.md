# Decisions: design

Next ID: D7.

- **D1** **Study area: Caquetá, Guaviare, Meta, Putumayo (62 municipios, HDX COD-AB 2020).** The core of the Amazon deforestation frontier, spanning Andean foothills, Amazon lowland forest and Llanos savanna.
- **D2** **Treatment: `FARC1` from the Prem et al. (2020) replication data** (at least one violent event attributed to the group, 2011–2014). It measures violent presence, not territorial control: a municipio held without contest can score 0. `FARC2` and `FARC_N` serve as robustness variants.
- **D3** **Timing: 2014 is the last pre-ceasefire year, 2015 the first post-ceasefire year**, following Prem et al.'s ceasefire indicator. Any baseline layer uses 2014 or earlier.
- **D4** **Forest loss from MapBiomas Colombia Collection 3, pinned.** Land-use classes (forest → pasture) rather than canopy change, one method across 1985–2024, and a history long enough to separate primary from secondary forest. Collections reprocess the full series, so the collection number is fixed.
- **D5** **Hansen GFC v1.13 is used only as a comparison, 2013 onward.** It records tree cover loss from any cause, and its detection sensitivity changes across 2011, 2013 and 2015 (Global Forest Watch technical notes), which would confound a before/after-2015 comparison.
- **D6** **Results are reported as associations.** Treatment is assigned to 62 municipios with no causal design. Pre-ceasefire loss enters as a control to show change, not effect.
