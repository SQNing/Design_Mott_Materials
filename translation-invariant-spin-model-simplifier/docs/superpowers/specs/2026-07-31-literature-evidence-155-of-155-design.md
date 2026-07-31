# Literature Evidence Audit: Strict 155-of-155 Design

Date: 2026-07-31

Status: approved in conversation

## Objective

Bring the literature-reproduction audit for all 155 registered spin-model
benchmarks to a strictly verified state. Completion means that every benchmark
is supported by locally cached, provenance-checked source text and either a
direct source parse or an independent local recomputation. Projection-only
evidence does not count toward completion.

The final runtime coverage contract is:

- `supported = 155`
- `missing = 0`
- `extra = 0`
- `invalid = 0`
- `complete = true`
- `strict_local_recomputed = 42`
- `strict_local_source_parsed = 113`
- `projection = 0`

## Compatibility Decision

Existing benchmark names and record filenames remain stable identifiers even
where a historical name is physically misleading. All semantic fields are
corrected to the cited work: model, lattice, Hamiltonian, parameters,
observable, result, source, locator, and audit description.

Examples include:

- `nacuo2_triangular_heisenberg_material_reference` remains the stable key,
  while every physical field continues to identify `NaCrO2` and must not leak
  `NaCuO2` into the physical payload.
- `ba3irti2o9_honeycomb_kitaev_reference` remains the stable key, while the
  physical description becomes a site-diluted triangular-lattice
  `J_eff = 1/2` spin-liquid candidate rather than a clean honeycomb Kitaev
  model.
- `ruby_lattice_heisenberg_flat_band_reference` remains the stable key, while
  the supported statement is limited to existence of an exact localized
  one-magnon eigenstate; the source does not support a plateau mechanism claim.
- `vesignieite_kagome_material_reference` remains the stable key, while the
  result records dominant third-neighbour exchange and only a tiny structural
  distortion.

This preserves downstream compatibility without preserving incorrect physics.

## Authoritative State and Scope

The runtime evidence collector is the authoritative completion mechanism. The
static files under `reference/literature-evidence/records/` remain fail-closed
forecasts with `record_state = "unresolved"`; they must not be rewritten as if
they were acquired evidence and must not contain copied answers, excerpts, or
payload hashes.

The approved implementation scope consists of:

1. The three previously authorized runtime/PDF-test files.
2. The thirteen central registry, source, inventory, audit, and test files
   enumerated in the approval request.
3. The fifty-eight explicitly enumerated unresolved record JSON files.
4. New source-cache directories for newly introduced canonical identities.
5. New design and `155_of_155` report artifacts.

No other existing file may be overwritten, moved, truncated, or deleted. Old
source caches remain in place even when their identities leave the source
index. Existing non-`155_of_155` reports and the user's pre-existing PDF
generator modification remain untouched.

## Evidence Architecture

### Registry layer

The benchmark registry contains the scientific contract. Forty-two benchmark
entries change canonical source identity. Separately, entries with misleading
legacy names receive corrected semantic metadata. Numeric corrections include
the Jiang-Wiese square-lattice values `rho_s/J = 0.18081` and
`c/(Ja) = 1.6586`; the cubic-Ising registry value remains rounded and is
compared using an explicit absolute tolerance.

After source reassignment, the source topology is expected to contain 137
unique canonical identities. The exact set transition is 33 identities added
and 30 identities removed from the registry-derived index. Removed identities
and their caches are not deleted.

### Source-routing layer

Every source route declares:

- canonical identity and canonical URL;
- authoritative retrieval method and origin;
- immutable artifact identifier;
- expected media type and cache extension;
- access mode;
- same-work identity evidence when the payload URL is not the canonical DOI or
  arXiv artifact.

The normal routes remain APS harvest PDFs, arXiv export PDFs, publisher PDFs,
and full-text XML. Four special identities require explicit routes:

1. Husimi-Syozi (`10.1143/PTP.5.2.177`) uses the OUP/Silverchair minimal HTML
   artifact. HTML is validated as `text/html`, stored as `source.html`, and
   converted to visible text deterministically with scripts, styles, comments,
   and markup excluded.
2. Caspers-Emmett-Magnus (`10.1088/0305-4470/17/13/020`) uses a CORE repository
   PDF. A hashed CORE work-record sidecar binds the DOI to the selected output
   identifier and download artifact.
3. Garel-Maillard (`10.1088/0305-4470/16/10/023`) uses the author's laboratory
   repository PDF. A hashed author-publications page sidecar must contain the
   exact paper title and resolve its link to the retrieved PDF; the title and
   authors are also cross-checked against DOI bibliographic metadata.
4. The open RuBr3 Nature/npj article uses the public article PDF route rather
   than an authenticated-only fallback.

The expected final media distribution is 134 PDF sources, 2 XML sources, and
1 HTML source. Expected access-mode totals are 123 unattended, 9
challenge-or-institutional, 3 authenticated-session, and 2
API-key-or-entitlement routes.

### Provenance and extraction layer

Cached evidence is accepted only if all of the following agree:

- source index;
- provisioning route;
- provenance JSON;
- raw payload SHA-256 and byte length;
- payload media signature;
- deterministic extraction descriptor;
- optional same-work identity sidecar and its own SHA-256;
- required source-bearing anchors.

PDF extraction uses the recorded installed `pdftotext` version with
`-layout -enc UTF-8`. XML extraction accepts article-body text only. HTML
extraction uses a deterministic standard-library visible-text parser and must
not surface CSS, JavaScript, comments, attributes, or hidden metadata as source
text.

Downloads fail closed on non-200 status, redirects to challenge hosts, media
type mismatch, PDF signature/truncation failure, metadata-only XML, malformed
HTML, missing visible article content, identity mismatch, or missing target
anchors.

### Runtime evidence layer

The 58 current gaps are added to the runtime collector as explicit specs:

- 21 `local_recompute` specs parse source operands and pass them to independent
  recomputation functions;
- 37 `local_source_parse` specs derive registered fields directly from source
  text.

Together with the existing 97 specs, the collector must have exactly 155
unique benchmark names. Each spec names one parser and, for recomputation,
exactly one recompute function. Collector validation rejects duplicate names,
unknown registry names, invalid modes, unexpected result fields, source-id
disagreement, tolerance misuse, and parser/recompute trace mismatch.

All source parsers are fail closed: source identity, title/authors or stable
bibliographic anchors, scientific context, and the target-bearing statement or
formula are jointly required. Numeric tokens without those anchors are
insufficient.

## Data Flow

1. Registry entries determine canonical source identities.
2. Inventory generation derives source index, provisioning routes, locator
   rows, contracts, and unresolved records without acquiring source data.
3. The fetcher acquires a source through its declared route, validates bytes,
   writes a new cache directory, records provenance and any identity sidecars,
   then performs offline verification.
4. The runtime collector resolves each benchmark to its verified cache,
   extracts deterministic text, runs its parser, optionally runs an independent
   recomputation, and compares the result to the registry contract.
5. Coverage aggregation rejects missing, extra, or invalid benchmark results.
6. The audit renderer consumes the verified runtime results and produces new
   `155_of_155` Markdown, CSV, gap, and PDF artifacts without overwriting prior
   reports.

## Scientific Corrections

Source and descriptor corrections are applied to the evidence claim actually
supported by each paper. In particular:

- Jiang-Wiese replaces the unrelated Sandvik citation for all three low-energy
  square-Heisenberg parameters.
- Vesignieite records dominant `J3` and rejects a distortion-dominated
  nearest-neighbour interpretation.
- Edwardsite is the hydrated spin-one-half deformed-kagome material.
- Ba3IrTi2O9 is triangular and site diluted, not a clean honeycomb Kitaev
  material.
- The square ring-exchange benchmark follows the XY plus four-spin ring model
  and its bond/spin-Peierls or valence-bond ordering statement.
- The triangular one-third plateau backend reflects the cited spin-wave
  expansion rather than an ED/DMRG attribution.
- GGG and GTLG use papers that support the registered garnet claims, with GTLG
  retaining its reported first-order long-range ordering transition.
- The star and shuriken lattice citations are disentangled.
- NaCrO2 remains the sole physical material value behind the legacy
  `nacuo2` key.

## Static Artifact Update Strategy

The inventory generator is run against the corrected registry into a fresh
temporary directory. Generated artifacts are compared with the worktree, and
only the four approved central JSON files plus the fifty-eight approved record
files are patched. The generator is not pointed at the real inventory root,
because doing so would rewrite all 155 records and violate the file-safety
boundary.

The record files remain unresolved and answer-free. Their changes are limited
to corrected contracts, source IDs, locator forecasts, and source route
descriptors.

## Testing Strategy

Implementation follows red-green-refactor within the approved files.

### Source tests

- exact final route-kind, media, access-mode, and identity counts;
- exact special-route descriptors;
- positive HTML visible-text extraction;
- rejection of malformed HTML, script/style-only anchors, wrong content type,
  challenge pages, and missing article text;
- positive and negative CORE DOI/output binding;
- positive and negative author-page title/link/DOI-metadata binding;
- offline cache verification including identity-sidecar hashes.

### Inventory and registry tests

- exactly 155 benchmark records and 137 unique canonical sources;
- exact source identity set and benchmark membership;
- `source.html` extension only for `text/html`;
- unresolved records remain answer-free;
- corrected material/model metadata and numeric values;
- no `NaCuO2` physical-data leakage;
- no duplicate or orphan records, locators, or source routes.

### Runtime tests

- synthetic positive and fail-closed negative cases for every new parser;
- parser replay against actual cached payload text;
- independent recomputation tests and perturbation/correction-chain tests;
- exact collector spec count and mode distribution;
- full coverage contract of 155 supported and zero missing/extra/invalid.

### Audit tests

- corrected scientific descriptions;
- no projection counted as strict reproduction;
- exact evidence-method counts;
- new reports refer only to verified runtime evidence;
- rendered PDF states 155/155 and contains no stale 43/155 or 97/155 claim.

### Completion commands

At minimum, completion requires fresh successful output from:

- focused parser, route, inventory, crosscheck, runtime, audit, and PDF tests;
- the full relevant pytest suite using `python -m pytest` (the standalone
  `pytest` executable has a stale shebang in this environment);
- Python bytecode compilation for all modified Python files;
- `git diff --check`;
- offline verification of every source cache used by the collector;
- the authoritative runtime coverage command producing the exact completion
  contract above;
- report generation followed by text and visual inspection of the final PDF.

No completion claim is made from a narrower test or from absence of obvious
errors. The final audit must positively prove every one of the 155 entries.

## Exact Authorized Write Manifest

This appendix is the durable write boundary for implementation. The following
seventy-four pre-existing files are the only existing paths that may be
modified. The first three were authorized before the present approval:

    scripts/validation/literature_runtime_evidence.py
    tests/test_literature_runtime_evidence.py
    tests/test_literature_reproduction_audit_pdf.py

The thirteen approved central registry, routing, inventory, audit, and test
files are:

    scripts/validation/literature_spin_model_benchmarks.py
    scripts/validation/literature_evidence_sources.py
    scripts/validation/fetch_literature_evidence_sources.py
    scripts/validation/literature_evidence_inventory.py
    scripts/validation/literature_reproduction_audit.py
    reference/literature-evidence/canonical-observables.json
    reference/literature-evidence/locator-inventory.json
    reference/literature-evidence/source-index.json
    reference/literature-evidence/source-provisioning.json
    tests/test_literature_evidence_sources.py
    tests/test_literature_evidence_inventory.py
    tests/test_literature_spin_model_crosschecks.py
    tests/test_literature_reproduction_audit.py

The fifty-eight approved unresolved record files are:

    reference/literature-evidence/records/ba3irti2o9_honeycomb_kitaev_reference.json
    reference/literature-evidence/records/blume_capel_spin1_zero_temperature_level_crossing.json
    reference/literature-evidence/records/checkerboard_heisenberg_afm_planar_pyrochlore_reference.json
    reference/literature-evidence/records/clinoatacamite_distorted_kagome_reference.json
    reference/literature-evidence/records/crcl3_honeycomb_heisenberg_reference.json
    reference/literature-evidence/records/crgete3_honeycomb_ferromagnet_reference.json
    reference/literature-evidence/records/cu2iro3_honeycomb_kitaev_reference.json
    reference/literature-evidence/records/cu2oseo3_skyrmion_lattice_reference.json
    reference/literature-evidence/records/cubic_ising_critical_temperature_reference.json
    reference/literature-evidence/records/dy2ti2o7_spin_ice_entropy_reference.json
    reference/literature-evidence/records/edwardsite_kagome_antiferromagnet_reference.json
    reference/literature-evidence/records/er2ti2o7_xy_pyrochlore_order_by_disorder_reference.json
    reference/literature-evidence/records/fcc_j1_j2_heisenberg_type_order_reference.json
    reference/literature-evidence/records/fe8_molecular_spin_tunneling_reference.json
    reference/literature-evidence/records/fe_ps3_honeycomb_ising_reference.json
    reference/literature-evidence/records/gadolinium_gallium_garnet_hyperkagome_reference.json
    reference/literature-evidence/records/gamma_li2iro3_3d_kitaev_reference.json
    reference/literature-evidence/records/garnet_gd3te2li3o12_hyperkagome_reference.json
    reference/literature-evidence/records/h3liir2o6_kitaev_spin_liquid_candidate_reference.json
    reference/literature-evidence/records/honeycomb_ising_ferromagnet_exact_tc.json
    reference/literature-evidence/records/honeycomb_j1_j2_j3_classical_phase_diagram.json
    reference/literature-evidence/records/honeycomb_j1_j2_kitaev_material_na2iro3_reference.json
    reference/literature-evidence/records/honeycomb_j1_j2_spiral_ring_reference.json
    reference/literature-evidence/records/honeycomb_kitaev_heisenberg_four_sublattice_phases.json
    reference/literature-evidence/records/j1_j2_chain_bkt_transition_reference.json
    reference/literature-evidence/records/j1_j2_chain_okamoto_nomura_critical_point.json
    reference/literature-evidence/records/kagome_heisenberg_dmrg_spin_liquid_yan_reference.json
    reference/literature-evidence/records/kagome_ising_antiferromagnet_residual_entropy_reference.json
    reference/literature-evidence/records/kagome_ising_ferromagnet_exact_tc.json
    reference/literature-evidence/records/kagome_spin_half_heisenberg_energy_reference.json
    reference/literature-evidence/records/licuvo4_spiral_chain_reference.json
    reference/literature-evidence/records/lieb_lattice_heisenberg_ferrimagnet_reference.json
    reference/literature-evidence/records/majundar_ghosh_chain_exact_dimer_point.json
    reference/literature-evidence/records/mn_ps3_honeycomb_antiferromagnet_reference.json
    reference/literature-evidence/records/mnsi_chiral_helimagnet_reference.json
    reference/literature-evidence/records/nacuo2_triangular_heisenberg_material_reference.json
    reference/literature-evidence/records/one_dimensional_classical_ising_no_finite_t_transition.json
    reference/literature-evidence/records/pyrochlore_heisenberg_afm_coulomb_phase_reference.json
    reference/literature-evidence/records/ru_br3_kitaev_material_reference.json
    reference/literature-evidence/records/ruby_lattice_heisenberg_flat_band_reference.json
    reference/literature-evidence/records/shastry_sutherland_exact_dimer_product.json
    reference/literature-evidence/records/shuriken_lattice_heisenberg_reference.json
    reference/literature-evidence/records/simple_cubic_j1_j2_collinear_reference.json
    reference/literature-evidence/records/single_ion_spin1_anisotropy_levels.json
    reference/literature-evidence/records/square_fully_frustrated_ising_residual_entropy_reference.json
    reference/literature-evidence/records/square_heisenberg_spin_half_spin_stiffness_reference.json
    reference/literature-evidence/records/square_heisenberg_spin_half_staggered_magnetization_reference.json
    reference/literature-evidence/records/square_heisenberg_spin_wave_velocity_reference.json
    reference/literature-evidence/records/square_ring_exchange_neel_vbs_reference.json
    reference/literature-evidence/records/star_lattice_heisenberg_spin_liquid_reference.json
    reference/literature-evidence/records/takhtajan_babujian_spin1_critical_point.json
    reference/literature-evidence/records/transverse_field_ising_chain_critical_point.json
    reference/literature-evidence/records/transverse_field_ising_chain_gap.json
    reference/literature-evidence/records/triangular_heisenberg_magnetization_plateau_reference.json
    reference/literature-evidence/records/triangular_ising_ferromagnet_exact_tc.json
    reference/literature-evidence/records/vesignieite_kagome_material_reference.json
    reference/literature-evidence/records/xx_spin_half_chain_free_fermion_energy.json
    reference/literature-evidence/records/xxz_spin_half_chain_phase_boundaries.json

The versioned design file and final reports are new files, not replacements:

    docs/superpowers/specs/2026-07-31-literature-evidence-155-of-155-design.md
    reports/literature_reproduction_audit_155_of_155.csv
    reports/literature_reproduction_audit_155_of_155.md
    reports/remaining_strict_reproduction_gaps_155_of_155.md
    reports/literature_reproduction_audit_155_of_155.pdf

The only new cache directory trees permitted are the following thirty-three
exclusive-create paths. Each comment records the canonical identity from which
the source ID is deterministically derived:

    source-cache/arxiv_2a82afb1051aa17b9405/  # arxiv:1004.1119
    source-cache/arxiv_f6b1bfbaa376158563e6/  # arxiv:1006.5052
    source-cache/arxiv_0e5321621b7258dea2db/  # arxiv:1204.1320
    source-cache/arxiv_dbdd4b586780cd708b67/  # arxiv:1204.5027
    source-cache/arxiv_85cd16736d43980e87ea/  # arxiv:1205.4858
    source-cache/arxiv_36e066e2b99129d0057f/  # arxiv:1209.5100
    source-cache/arxiv_57815717df98a77fdf43/  # arxiv:1305.2477
    source-cache/arxiv_fc2347b67f4611c61958/  # arxiv:1309.3744
    source-cache/arxiv_c119958c10a698757174/  # arxiv:1405.6184
    source-cache/arxiv_561a252c28acb461267e/  # arxiv:2005.12031
    source-cache/arxiv_ffa588072c8fe0ab1cac/  # arxiv:2007.00376
    source-cache/arxiv_1f254fb3984af33c5ec2/  # arxiv:2409.16715
    source-cache/arxiv_5d132154aee28ea4475e/  # arxiv:2512.14173
    source-cache/arxiv_0a49fe8b4a8daeff1eb8/  # arxiv:2601.21024
    source-cache/arxiv_93b970e76b4d7ebb32b8/  # arxiv:cond-mat/0108070
    source-cache/arxiv_9997d06bc7630b2a0091/  # arxiv:cond-mat/0205270
    source-cache/arxiv_f32fab13874ec5c0ec4a/  # arxiv:cond-mat/0407005
    source-cache/arxiv_f1af74b7fd4b62174611/  # arxiv:cond-mat/0411673
    source-cache/arxiv_5bd1b8eb23d6c0ac2e87/  # arxiv:cond-mat/0509490
    source-cache/arxiv_e96482d150e3231eaa21/  # arxiv:cond-mat/9509016
    source-cache/arxiv_4d77a787c497a62e0d7e/  # arxiv:cond-mat/9811353
    source-cache/arxiv_75995a2b249101ded246/  # arxiv:cond-mat/9909290
    source-cache/doi_35bb82ba0a5814f69448/  # doi:10.1038/s41535-026-00868-6
    source-cache/doi_dba239926d673e54f80a/  # doi:10.1088/0305-4470/16/10/023
    source-cache/doi_e49cda761520424da334/  # doi:10.1088/0305-4470/17/13/020
    source-cache/doi_fb163b4dc967143dd3e5/  # doi:10.1103/physrevb.82.100408
    source-cache/doi_422f517c2d9549fef833/  # doi:10.1103/physrevb.83.155120
    source-cache/doi_a033e1bb29f7c9a51082/  # doi:10.1103/physrevb.87.174421
    source-cache/doi_ec7bac11ef2a4fa52066/  # doi:10.1103/physrevb.92.125131
    source-cache/doi_977dd2526b3afc0ed325/  # doi:10.1103/physrevlett.113.197201
    source-cache/doi_6da8d81e7ff23f395d98/  # doi:10.1103/physrevlett.121.107203
    source-cache/doi_4dd4b0d22b13ffc3709d/  # doi:10.1103/physrevlett.73.2500
    source-cache/doi_f334ed253565110358b3/  # doi:10.1143/ptp.5.2.177

Files created below one of those new cache directories are limited to the
route-declared payload, extracted text, provenance, and required same-work
identity sidecars. Any one of these directory paths already existing at fetch
time is an error unless it verifies byte-for-byte as a resumable cache. No
existing cache directory is an authorized write target.

## Exact Source-Identity Transition Manifest

The following forty-two benchmark keys change source identity. This exact map,
not merely its row count, is asserted by tests:

| Benchmark | Final canonical source identity |
| --- | --- |
| blume_capel_spin1_zero_temperature_level_crossing | arxiv:1204.5027 |
| single_ion_spin1_anisotropy_levels | arxiv:1204.5027 |
| xxz_spin_half_chain_phase_boundaries | arxiv:cond-mat/9909290 |
| j1_j2_chain_bkt_transition_reference | arxiv:1006.5052 |
| j1_j2_chain_okamoto_nomura_critical_point | arxiv:1006.5052 |
| er2ti2o7_xy_pyrochlore_order_by_disorder_reference | arxiv:1204.1320 |
| star_lattice_heisenberg_spin_liquid_reference | doi:10.1103/physrevb.70.174454 |
| shuriken_lattice_heisenberg_reference | arxiv:cond-mat/0411673 |
| fe_ps3_honeycomb_ising_reference | arxiv:2005.12031 |
| ruby_lattice_heisenberg_flat_band_reference | arxiv:2512.14173 |
| gamma_li2iro3_3d_kitaev_reference | doi:10.1103/physrevlett.113.197201 |
| transverse_field_ising_chain_critical_point | arxiv:cond-mat/0509490 |
| transverse_field_ising_chain_gap | arxiv:cond-mat/0509490 |
| xx_spin_half_chain_free_fermion_energy | doi:10.1103/physrevb.92.125131 |
| honeycomb_ising_ferromagnet_exact_tc | doi:10.1143/ptp.5.2.177 |
| triangular_ising_ferromagnet_exact_tc | doi:10.1143/ptp.5.2.177 |
| majundar_ghosh_chain_exact_dimer_point | doi:10.1088/0305-4470/17/13/020 |
| square_fully_frustrated_ising_residual_entropy_reference | doi:10.1088/0305-4470/16/10/023 |
| honeycomb_j1_j2_spiral_ring_reference | arxiv:1004.1119 |
| fcc_j1_j2_heisenberg_type_order_reference | arxiv:2007.00376 |
| pyrochlore_heisenberg_afm_coulomb_phase_reference | arxiv:cond-mat/0407005 |
| checkerboard_heisenberg_afm_planar_pyrochlore_reference | arxiv:cond-mat/0108070 |
| takhtajan_babujian_spin1_critical_point | arxiv:cond-mat/9811353 |
| cubic_ising_critical_temperature_reference | arxiv:cond-mat/9509016 |
| kagome_spin_half_heisenberg_energy_reference | arxiv:1205.4858 |
| kagome_heisenberg_dmrg_spin_liquid_yan_reference | arxiv:1205.4858 |
| square_ring_exchange_neel_vbs_reference | arxiv:cond-mat/0205270 |
| honeycomb_j1_j2_kitaev_material_na2iro3_reference | arxiv:1209.5100 |
| honeycomb_kitaev_heisenberg_four_sublattice_phases | arxiv:1209.5100 |
| garnet_gd3te2li3o12_hyperkagome_reference | doi:10.1103/physrevb.87.174421 |
| gadolinium_gallium_garnet_hyperkagome_reference | doi:10.1103/physrevlett.73.2500 |
| mn_ps3_honeycomb_antiferromagnet_reference | doi:10.1103/physrevb.82.100408 |
| ru_br3_kitaev_material_reference | doi:10.1038/s41535-026-00868-6 |
| vesignieite_kagome_material_reference | doi:10.1103/physrevlett.121.107203 |
| square_heisenberg_spin_half_spin_stiffness_reference | doi:10.1103/physrevb.83.155120 |
| square_heisenberg_spin_half_staggered_magnetization_reference | doi:10.1103/physrevb.83.155120 |
| square_heisenberg_spin_wave_velocity_reference | doi:10.1103/physrevb.83.155120 |
| honeycomb_j1_j2_j3_classical_phase_diagram | arxiv:1309.3744 |
| nacuo2_triangular_heisenberg_material_reference | arxiv:1405.6184 |
| clinoatacamite_distorted_kagome_reference | arxiv:2601.21024 |
| edwardsite_kagome_antiferromagnet_reference | arxiv:1305.2477 |
| lieb_lattice_heisenberg_ferrimagnet_reference | arxiv:2409.16715 |

The added canonical-identity set is exactly:

    arxiv:1004.1119
    arxiv:1006.5052
    arxiv:1204.1320
    arxiv:1204.5027
    arxiv:1205.4858
    arxiv:1209.5100
    arxiv:1305.2477
    arxiv:1309.3744
    arxiv:1405.6184
    arxiv:2005.12031
    arxiv:2007.00376
    arxiv:2409.16715
    arxiv:2512.14173
    arxiv:2601.21024
    arxiv:cond-mat/0108070
    arxiv:cond-mat/0205270
    arxiv:cond-mat/0407005
    arxiv:cond-mat/0411673
    arxiv:cond-mat/0509490
    arxiv:cond-mat/9509016
    arxiv:cond-mat/9811353
    arxiv:cond-mat/9909290
    doi:10.1038/s41535-026-00868-6
    doi:10.1088/0305-4470/16/10/023
    doi:10.1088/0305-4470/17/13/020
    doi:10.1103/physrevb.82.100408
    doi:10.1103/physrevb.83.155120
    doi:10.1103/physrevb.87.174421
    doi:10.1103/physrevb.92.125131
    doi:10.1103/physrevlett.113.197201
    doi:10.1103/physrevlett.121.107203
    doi:10.1103/physrevlett.73.2500
    doi:10.1143/ptp.5.2.177

The removed canonical-identity set is exactly:

    doi:10.1016/0003-4916(61)90115-4
    doi:10.1016/0003-4916(70)90270-8
    doi:10.1016/0031-8914(50)90130-3
    doi:10.1016/0375-9601(82)90403-0
    doi:10.1016/0375-9601(92)90823-5
    doi:10.1016/0378-4363(79)90002-0
    doi:10.1016/j.physb.2007.10.295
    doi:10.1038/ncomms14113
    doi:10.1038/ncomms5203
    doi:10.1038/nmat1867
    doi:10.1063/1.1664978
    doi:10.1063/1.1724276
    doi:10.1088/0022-3719/10/10/014
    doi:10.1088/0953-8984/10/28/020
    doi:10.1088/1361-648x/aa8cf5
    doi:10.1103/physrev.131.546
    doi:10.1103/physrev.141.517
    doi:10.1103/physrev.150.321
    doi:10.1103/physrevb.66.014418
    doi:10.1103/physrevb.70.184414
    doi:10.1103/physrevb.85.094422
    doi:10.1103/physrevb.92.140407
    doi:10.1103/physrevlett.105.027204
    doi:10.1103/physrevlett.108.037202
    doi:10.1103/physrevlett.69.3382
    doi:10.1103/physrevlett.77.2085
    doi:10.1103/physrevlett.80.2933
    doi:10.1103/physrevlett.93.107206
    doi:10.1126/science.1201080
    doi:10.1143/jpsj.78.043704

These sets satisfy 137 final unique identities, 33 additions, and 30 removals.
Ba3IrTi2O9 is a semantic correction whose canonical source identity remains
doi:10.1103/physrevb.86.140405, so it is intentionally absent from the
forty-two-row source-reassignment map.

## Exact Gap-Closure Execution Manifest

The following two tables are the complete executable contract for the
fifty-eight baseline gaps. Every row fixes the benchmark, final source
identity, provisioning route kind, evidence mode, parser, selected registry
field or fields, comparison policy, and recomputation call where applicable.
Tests assert the exact benchmark-key set and the exact values in these columns.

For every row, exact comparison means equality after the declared registry
normalization, including exact sequence and mapping structure. The only
non-exact comparison is the explicitly listed simple-cubic Ising absolute
tolerance. A parser may return additional independently checked trace data, but
only the listed selector fields enter the registry comparison.

### Thirty-seven direct local-source parses

All rows in this table use evidence mode local_source_parse, comparison exact,
and no recompute function.

| Benchmark | Final source identity | Route kind | Parser | Selector |
| --- | --- | --- | --- | --- |
| ba3irti2o9_honeycomb_kitaev_reference | doi:10.1103/physrevb.86.140405 | aps_harvest_pdf | parse_dey_ba3irti2o9_triangular_spin_liquid_candidate | spin_liquid_candidate |
| clinoatacamite_distorted_kagome_reference | arxiv:2601.21024 | arxiv_export_pdf | parse_stodter_clinoatacamite_distorted_kagome_exchange | distorted_kagome_reference |
| crcl3_honeycomb_heisenberg_reference | doi:10.1016/0022-3697(61)90053-1 | elsevier_article_api_xml | parse_cable_crcl3_ferromagnetic_layers | ferromagnetic_honeycomb_layers |
| crgete3_honeycomb_ferromagnet_reference | doi:10.1088/0953-8984/7/1/008 | iop_article_pdf | parse_carteaux_cr2ge2te6_ferromagnetic_order | ferromagnetic_order |
| cu2iro3_honeycomb_kitaev_reference | doi:10.1021/jacs.7b06911 | acs_article_pdf | parse_abramchuk_cu2iro3_honeycomb_iridate | honeycomb_frustrated_iridate_identity |
| cu2oseo3_skyrmion_lattice_reference | doi:10.1126/science.1214143 | science_article_pdf | parse_seki_cu2oseo3_skyrmion_lattice_phase | skyrmion_lattice_phase |
| dy2ti2o7_spin_ice_entropy_reference | doi:10.1038/20619 | nature_article_pdf | parse_ramirez_dy2ti2o7_pauling_entropy | pauling_entropy_observed |
| edwardsite_kagome_antiferromagnet_reference | arxiv:1305.2477 | arxiv_export_pdf | parse_ishikawa_edwardsite_spin_half_deformed_kagome | kagome_antiferromagnet_reference |
| er2ti2o7_xy_pyrochlore_order_by_disorder_reference | arxiv:1204.1320 | arxiv_export_pdf | parse_savary_er2ti2o7_psi2_order_by_quantum_disorder | psi2_order_selected |
| fe8_molecular_spin_tunneling_reference | doi:10.1126/science.284.5411.133 | science_article_pdf | parse_wernsdorfer_sessoli_fe8_quantum_tunneling | macroscopic_quantum_tunneling_observed |
| fe_ps3_honeycomb_ising_reference | arxiv:2005.12031 | arxiv_export_pdf | parse_wildes_feps3_ising_zigzag_order | ising_like_zigzag_order |
| gadolinium_gallium_garnet_hyperkagome_reference | doi:10.1103/physrevlett.73.2500 | aps_harvest_pdf | parse_schiffer_ggg_strong_frustration_correction | strong_frustration |
| gamma_li2iro3_3d_kitaev_reference | doi:10.1103/physrevlett.113.197201 | aps_harvest_pdf | parse_biffin_gamma_li2iro3_spiral_kitaev_order | incommensurate_spiral_order |
| garnet_gd3te2li3o12_hyperkagome_reference | doi:10.1103/physrevb.87.174421 | aps_harvest_pdf | parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction | garnet_frustrated_magnet |
| h3liir2o6_kitaev_spin_liquid_candidate_reference | doi:10.1038/nature25482 | nature_article_pdf | parse_kitagawa_h3liir2o6_no_magnetic_order | no_magnetic_order_reported |
| honeycomb_j1_j2_j3_classical_phase_diagram | arxiv:1309.3744 | arxiv_export_pdf | parse_mazin_honeycomb_j1_j2_j3_phase_set | phases |
| honeycomb_j1_j2_kitaev_material_na2iro3_reference | arxiv:1209.5100 | arxiv_export_pdf | parse_chaloupka_na2iro3_zigzag_relevance | zigzag_order_relevant |
| honeycomb_kitaev_heisenberg_four_sublattice_phases | arxiv:1209.5100 | arxiv_export_pdf | parse_chaloupka_full_kitaev_heisenberg_ordered_phases | ordered_phases |
| j1_j2_chain_bkt_transition_reference | arxiv:1006.5052 | arxiv_export_pdf | parse_kumar_j1_j2_bkt_reference | critical_j2_over_j1_approx |
| j1_j2_chain_okamoto_nomura_critical_point | arxiv:1006.5052 | arxiv_export_pdf | parse_kumar_j1_j2_critical_point | critical_j2_over_j1 |
| kagome_heisenberg_dmrg_spin_liquid_yan_reference | arxiv:1205.4858 | arxiv_export_pdf | parse_depenbrock_kagome_heisenberg_energy_and_spin_gap | energy_per_site, spin_gap_over_j |
| kagome_spin_half_heisenberg_energy_reference | arxiv:1205.4858 | arxiv_export_pdf | parse_depenbrock_kagome_heisenberg_energy | energy_per_site_approx |
| licuvo4_spiral_chain_reference | doi:10.1209/epl/i2004-10484-x | epl_iop_article_pdf | parse_enderle_licuvo4_incommensurate_helimagnet | incommensurate_spiral_order |
| lieb_lattice_heisenberg_ferrimagnet_reference | arxiv:2409.16715 | arxiv_export_pdf | parse_furuchi_lieb_lattice_ground_state_spin | ground_state_spin_per_unit_cell |
| mn_ps3_honeycomb_antiferromagnet_reference | doi:10.1103/physrevb.82.100408 | aps_harvest_pdf | parse_ressouche_mnps3_neel_order | neel_order_reference |
| mnsi_chiral_helimagnet_reference | doi:10.1088/0022-3719/13/31/002 | iop_article_pdf | parse_bak_jensen_mnsi_long_wavelength_helix | long_wavelength_helix |
| nacuo2_triangular_heisenberg_material_reference | arxiv:1405.6184 | arxiv_export_pdf | parse_hsieh_nacro2_unconventional_spin_order | unconventional_spin_order_reference |
| ru_br3_kitaev_material_reference | doi:10.1038/s41535-026-00868-6 | nature_open_article_pdf | parse_nawa_rubr3_kitaev_candidate_and_competing_interactions | ru_honeycomb_kitaev_candidate |
| ruby_lattice_heisenberg_flat_band_reference | arxiv:2512.14173 | arxiv_export_pdf | parse_ghosh_mila_ruby_localized_magnon_eigenstate | supports_localized_magnons |
| shuriken_lattice_heisenberg_reference | arxiv:cond-mat/0411673 | arxiv_export_pdf | parse_richter_square_kagome_reference | square_kagome_reference |
| square_heisenberg_spin_half_spin_stiffness_reference | doi:10.1103/physrevb.83.155120 | aps_harvest_pdf | parse_jiang_wiese_square_heisenberg_spin_stiffness | rho_s_over_j |
| square_heisenberg_spin_half_staggered_magnetization_reference | doi:10.1103/physrevb.83.155120 | aps_harvest_pdf | parse_jiang_wiese_square_heisenberg_staggered_magnetization | staggered_magnetization |
| square_heisenberg_spin_wave_velocity_reference | doi:10.1103/physrevb.83.155120 | aps_harvest_pdf | parse_jiang_wiese_square_heisenberg_spin_wave_velocity | renormalized_velocity_over_j_approx |
| square_ring_exchange_neel_vbs_reference | arxiv:cond-mat/0205270 | arxiv_export_pdf | parse_sandvik_daul_square_xy_ring_bond_order | ring_exchange_drives_vbs_phase |
| star_lattice_heisenberg_spin_liquid_reference | doi:10.1103/physrevb.70.174454 | aps_harvest_pdf | parse_richter_star_lattice_valence_bond_ground_state | spin_liquid_or_valence_bond_reference |
| triangular_heisenberg_magnetization_plateau_reference | doi:10.1088/0953-8984/3/1/005 | iop_article_pdf | parse_chubukov_golosov_triangular_plateau | one_third_plateau |
| vesignieite_kagome_material_reference | doi:10.1103/physrevlett.121.107203 | aps_harvest_pdf | parse_boldrin_vesignieite_dominant_j3_correction | distorted_kagome_relevant |

For the Vesignieite row, the corrected selected value is false: the paper
supports dominant third-neighbour exchange with only a tiny distortion, not a
distortion-dominated nearest-neighbour model.

### Twenty-one local recomputations

All rows in this table use evidence mode local_recompute. The parser obtains
the source-bearing operand or claim; the named independent recompute function
constructs the value compared with the listed registry selector.

| Benchmark | Final source identity | Route kind | Parser | Selector | Comparison | Recompute call |
| --- | --- | --- | --- | --- | --- | --- |
| blume_capel_spin1_zero_temperature_level_crossing | arxiv:1204.5027 | arxiv_export_pdf | parse_yang_xie_square_blume_capel_crossing | square_lattice_d_over_j_crossing | exact | recompute_blume_capel_zero_temperature_crossing(coordination_number=4, exchange=1.0) |
| checkerboard_heisenberg_afm_planar_pyrochlore_reference | arxiv:cond-mat/0108070 | arxiv_export_pdf | parse_fouet_checkerboard_classical_constraint | zero_total_spin_per_crossed_plaquette | exact | recompute_checkerboard_crossed_plaquette_constraint(exchange=1.0) |
| cubic_ising_critical_temperature_reference | arxiv:cond-mat/9509016 | arxiv_export_pdf | parse_blote_luijten_heringa_simple_cubic_ising_tc | tc_over_j | absolute tolerance 5e-6 | recompute_simple_cubic_ising_tc_from_critical_coupling(critical_coupling=0.2216546) |
| fcc_j1_j2_heisenberg_type_order_reference | arxiv:2007.00376 | arxiv_export_pdf | parse_balla_iqbal_penc_fcc_type_orders | common_orders | exact | recompute_fcc_j1_j2_type_orders(j1=1.0, type_i_j2=-0.25, type_iii_j2=0.25, type_ii_j2=0.75) |
| honeycomb_ising_ferromagnet_exact_tc | doi:10.1143/ptp.5.2.177 | oup_minimal_html | parse_husimi_syozi_honeycomb_ising_tc | tc_over_j | exact | recompute_honeycomb_ising_ferromagnet_tc(exchange=1.0) |
| honeycomb_j1_j2_spiral_ring_reference | arxiv:1004.1119 | arxiv_export_pdf | parse_mulder_honeycomb_spiral_contour | ring_condition | exact | recompute_honeycomb_j1_j2_spiral_contour(j1=1.0, j2=0.3) |
| kagome_ising_antiferromagnet_residual_entropy_reference | doi:10.1143/ptp/10.2.158 | jpsj_article_pdf | parse_kano_naya_kagome_ising_antiferromagnet_entropy | macroscopic_ground_state_degeneracy | exact | recompute_kano_naya_kagome_ising_entropy(grid_size=256), select macroscopic_ground_state_degeneracy |
| kagome_ising_ferromagnet_exact_tc | doi:10.1143/ptp/10.2.158 | jpsj_article_pdf | parse_kano_naya_kagome_ising_ferromagnet_tc | tc_over_j | exact | recompute_kagome_ising_ferromagnet_tc(exchange=1.0) |
| majundar_ghosh_chain_exact_dimer_point | doi:10.1088/0305-4470/17/13/020 | institutional_repository_pdf | parse_caspers_emmett_magnus_majumdar_ghosh_dimer_ground_states | energy_per_site, degenerate_dimer_coverings | exact | recompute_majumdar_ghosh_exact_dimer_operand(j1=1.0, j2_over_j1=0.5) |
| one_dimensional_classical_ising_no_finite_t_transition | doi:10.1007/bf02980577 | springer_content_pdf | parse_ising_1925_linear_chain_no_transition | finite_temperature_transition, tc_over_j | exact | recompute_one_dimensional_ising_no_finite_t_transition(exchange=1.0) |
| pyrochlore_heisenberg_afm_coulomb_phase_reference | arxiv:cond-mat/0407005 | arxiv_export_pdf | parse_henley_pyrochlore_coulomb_phase | zero_total_spin_per_tetrahedron, pinch_points | exact | recompute_pyrochlore_coulomb_phase(exchange=1.0, momentum_probe=1.0e-3) |
| shastry_sutherland_exact_dimer_product | doi:10.1016/0378-4363(81)90838-x | elsevier_article_api_xml | parse_shastry_sutherland_exact_dimer_product | energy_per_dimer, energy_per_spin | exact | recompute_shastry_sutherland_exact_dimer_energy(dimer_exchange=1.0) |
| simple_cubic_j1_j2_collinear_reference | doi:10.1063/1.367729 | aip_article_discovery | parse_pinettes_diep_simple_cubic_boundary | neel_to_collinear_boundary_j2_over_j1 | exact | recompute_simple_cubic_j1_j2_boundary(j1=1.0) |
| single_ion_spin1_anisotropy_levels | arxiv:1204.5027 | arxiv_export_pdf | parse_yang_xie_single_ion_spin1_anisotropy_levels | levels, degeneracies | exact | recompute_single_ion_spin1_anisotropy_levels(anisotropy=1.0) |
| square_fully_frustrated_ising_residual_entropy_reference | doi:10.1088/0305-4470/16/10/023 | author_repository_pdf | parse_garel_maillard_villain_entropy | macroscopic_ground_state_degeneracy | exact | recompute_garel_maillard_villain_entropy(series_terms=10000), select macroscopic_ground_state_degeneracy |
| takhtajan_babujian_spin1_critical_point | arxiv:cond-mat/9811353 | arxiv_export_pdf | parse_kitazawa_nomura_takhtajan_babujian_point | theta_radians, is_integrable | exact | recompute_takhtajan_babujian_integrable_operand() |
| transverse_field_ising_chain_critical_point | arxiv:cond-mat/0509490 | arxiv_export_pdf | parse_dziarmaga_tfim_critical_point | critical_field_over_exchange | exact | recompute_transverse_field_ising_chain_critical_point(exchange=1.0) |
| transverse_field_ising_chain_gap | arxiv:cond-mat/0509490 | arxiv_export_pdf | parse_dziarmaga_tfim_gap | gap_formula, gap_formula_at_g_0_6 | exact | recompute_transverse_field_ising_chain_gap(field_over_exchange=0.6, exchange=1.0) |
| triangular_ising_ferromagnet_exact_tc | doi:10.1143/ptp.5.2.177 | oup_minimal_html | parse_husimi_syozi_triangular_ising_tc | tc_over_j | exact | recompute_triangular_ising_ferromagnet_tc(exchange=1.0) |
| xx_spin_half_chain_free_fermion_energy | doi:10.1103/physrevb.92.125131 | aps_harvest_pdf | parse_collura_xx_chain_energy | energy_per_site | exact | recompute_xx_spin_half_chain_free_fermion_energy(exchange=1.0) |
| xxz_spin_half_chain_phase_boundaries | arxiv:cond-mat/9909290 | arxiv_export_pdf | parse_hirata_nomura_xxz_phase_boundaries | ferromagnetic_boundary_delta, neel_boundary_delta, gapless_interval | exact | recompute_xxz_spin_half_chain_phase_boundaries() |

The exact-set tests derive their expected keys from these manifests and fail on
any missing, extra, duplicate, or differently routed entry. Aggregate count
assertions remain as secondary invariants; they cannot substitute for these
identity-level contracts.

## Rollback and Safety

All implementation changes are additive or confined to explicitly approved
paths. No cleanup command is used. Existing caches that become unreferenced are
left intact. New cache directories are created with exclusive semantics so an
unexpected existing directory fails rather than being overwritten. Temporary
generation happens outside the inventory tree. New final reports use the
`155_of_155` suffix.

If any generated diff touches an unapproved existing path, application stops
and the path is reported instead of being changed.
