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

## Rollback and Safety

All implementation changes are additive or confined to explicitly approved
paths. No cleanup command is used. Existing caches that become unreferenced are
left intact. New cache directories are created with exclusive semantics so an
unexpected existing directory fails rather than being overwritten. Temporary
generation happens outside the inventory tree. New final reports use the
`155_of_155` suffix.

If any generated diff touches an unapproved existing path, application stops
and the path is reported instead of being changed.
