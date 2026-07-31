# Literature Evidence Strict 155-of-155 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development
> (if subagents are available) or superpowers:executing-plans to implement this
> plan. Steps use checkbox - [ ] syntax for tracking.

**Goal:** Convert the authoritative cache-backed literature audit from 97/155
to a scientifically corrected, fail-closed, strictly verified 155/155 result.

**Architecture:** Keep the registry as the scientific contract, derive static
inventory surfaces from it, acquire each canonical source through an explicit
provenance-checked route, and let the runtime collector be the sole authority
for strict completion. The registry, source routing, inventory, caches,
runtime evidence, audit, and reports are deliberately implemented in that
order because each layer supplies the identity contract for the next one.

**Tech Stack:** Python 3.9, pytest, standard-library urllib/HTML/XML/JSON
parsers, pdftotext 0.26.5, Git, Matplotlib, and local immutable source caches.

---

## Normative Inputs and Current State

Read the complete design before executing any task:

    docs/superpowers/specs/2026-07-31-literature-evidence-155-of-155-design.md

The design appendices are normative for all exact sets. In particular, do not
invent or approximate any of the following:

- the 74 authorized pre-existing write paths;
- the 42 benchmark-to-source reassignments;
- the 33 added and 30 removed canonical identities;
- the 37 local-source-parse contracts;
- the 21 local-recompute contracts;
- the 47 exclusive-create cache directories;
- the four new 155_of_155 report paths.

This is one sequential plan, not separate subsystem plans. Registry identity,
inventory generation, source routing, cache identity, runtime comparison, and
audit rendering form one dependency chain and cannot be made independently
correct.

Authoritative pre-implementation evidence recorded on 2026-07-31:

    registry entries: 155
    unique source identities: 134
    local source-cache directories: 113
    collector specs: 97
    collector modes: local_recompute=21, local_source_parse=76
    coverage: supported=97, missing=58, extra=0, invalid=0, complete=false
    parser/recompute symbols required by the 58-row contract: all present
    parser/recompute and PDF tests: 1520 passed in 950.24s

The current worktree contains authorized parser/recompute WIP in:

    scripts/validation/literature_runtime_evidence.py
    tests/test_literature_runtime_evidence.py
    tests/test_literature_reproduction_audit_pdf.py

It also contains a user-owned modification in:

    reports/generate_literature_reproduction_audit_pdf.py

Do not edit, revert, stage, or commit that generator. It may be imported to
render the new PDF because its existing write_reproduction_pdf function
already accepts an explicit destination path.

The following stale reports are user-owned and must remain untouched:

    reports/literature_reproduction_audit.csv
    reports/literature_reproduction_audit.md
    reports/literature_reproduction_audit_43_of_155.pdf
    reports/remaining_strict_reproduction_gaps.md

Their current SHA-256 values, plus the user-owned generator hash, are:

    d4ce49dda82c5c1fe18b5d37740d164306d5610afd21638c93c9269cca53ca95  reports/literature_reproduction_audit.csv
    b3ebbdde2ceb2940bb0053506bcb020179da67e56a90a380df9ca1d90cbbfc5d  reports/literature_reproduction_audit.md
    b4f8ff4d0229e785afc8f1590d7c2001f44a40794ddfabfb48efed8be2347e31  reports/literature_reproduction_audit_43_of_155.pdf
    622e1dc9afd08b2526424c4cbdf0d0d67dab617b4c7b6315e162b019b9c0a8a0  reports/remaining_strict_reproduction_gaps.md
    29c5455bc45074216003265a87175fe9d14b772c9d0e18b1ef2448c90162c9d1  reports/generate_literature_reproduction_audit_pdf.py

Use python -m pytest, not the standalone pytest executable, because the latter
has a stale interpreter shebang in this environment.

## File Responsibility Map

Runtime parsing, independent recomputation, collector specs, structural
validation, and authoritative coverage:

    scripts/validation/literature_runtime_evidence.py
    tests/test_literature_runtime_evidence.py

Scientific registry and physics-level crosschecks:

    scripts/validation/literature_spin_model_benchmarks.py
    tests/test_literature_spin_model_crosschecks.py

Canonical routes, payload validation, deterministic extraction, provenance,
same-work sidecars, and acquisition:

    scripts/validation/literature_evidence_sources.py
    scripts/validation/fetch_literature_evidence_sources.py
    tests/test_literature_evidence_sources.py

Inventory derivation, validation, and exact generated surfaces:

    scripts/validation/literature_evidence_inventory.py
    tests/test_literature_evidence_inventory.py
    reference/literature-evidence/canonical-observables.json
    reference/literature-evidence/source-index.json
    reference/literature-evidence/source-provisioning.json
    reference/literature-evidence/locator-inventory.json

Audit semantics, serializers, and PDF expectations:

    scripts/validation/literature_reproduction_audit.py
    tests/test_literature_reproduction_audit.py
    tests/test_literature_reproduction_audit_pdf.py

The only record files that may change are:

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

## Task 1: Verify and Checkpoint the Existing Parser/Recompute Foundation

**Files:**

- Modify: scripts/validation/literature_runtime_evidence.py
- Test: tests/test_literature_runtime_evidence.py

- [ ] **Step 1: Confirm every execution-manifest symbol exists**

Parse the runtime module and the two execution tables in the design. Assert
that all 58 parser symbols and all 21 recompute symbols resolve to top-level
functions. Also assert that none of the 58 target benchmark keys is already in
the 97-entry collector tuple.

Expected:

    target contracts = 58
    target parsers missing = 0
    target recomputes missing = 0
    target specs already connected = 0
    current collector specs = 97

- [ ] **Step 2: Run the complete current parser/recompute suite**

Run:

    python -m pytest -q tests/test_literature_runtime_evidence.py tests/test_literature_reproduction_audit_pdf.py

Expected: 1520 tests pass. If the exact count changes only because a new test
was added during execution, require all tests to pass and explain the count.

- [ ] **Step 3: Inspect the exact staged boundary**

Run:

    git diff --check -- scripts/validation/literature_runtime_evidence.py tests/test_literature_runtime_evidence.py
    git add -- scripts/validation/literature_runtime_evidence.py tests/test_literature_runtime_evidence.py
    git diff --cached --name-only

Expected staged paths: exactly the two files above. The generator and stale
reports must remain unstaged.

- [ ] **Step 4: Commit the verified parser/recompute foundation**

Run:

    git commit -m "feat: add remaining strict literature evidence parsers"

## Task 2: Correct Registry Sources and Scientific Semantics

**Files:**

- Modify: scripts/validation/literature_spin_model_benchmarks.py
- Modify: reference/literature-evidence/canonical-observables.json
- Test: tests/test_literature_spin_model_crosschecks.py
- Test: tests/test_literature_evidence_inventory.py

- [ ] **Step 1: Write the exact source-transition test**

In tests/test_literature_spin_model_crosschecks.py, define
EXPECTED_REASSIGNED_SOURCE_IDENTITIES from the exact 42-row table in the
design. The test must canonicalize each registry source_url and compare the
entire mapping, not only the count:

    actual = {
        name: canonical_source_identity(entries[name]["source_url"])
        for name in EXPECTED_REASSIGNED_SOURCE_IDENTITIES
    }
    assert actual == EXPECTED_REASSIGNED_SOURCE_IDENTITIES
    assert len(actual) == 42

Add separate assertions that Ba3IrTi2O9 retains
doi:10.1103/physrevb.86.140405 and is absent from this source-change mapping.

- [ ] **Step 2: Write scientific-correction tests**

Test complete registry payloads for at least these corrections:

- Ba3IrTi2O9 is a site-diluted triangular J_eff=1/2 spin-liquid candidate,
  not a honeycomb Kitaev model.
- The legacy nacuo2 key contains NaCrO2 physical data and contains no NaCuO2
  material value.
- Vesignieite has dominant J3, tiny distortion, and
  distorted_kagome_relevant=false.
- Ruby lattice claims only an exact localized one-magnon eigenstate.
- Jiang-Wiese values are rho_s/J=0.18081 and c/(Ja)=1.6586 and all three
  square-Heisenberg entries cite doi:10.1103/physrevb.83.155120.
- The square ring-exchange entry describes the XY plus four-spin ring model
  and bond/spin-Peierls or VBS ordering.
- The triangular one-third plateau entry describes the cited spin-wave
  calculation.
- GGG, GTLG, star, and shuriken entries use the sources and claims specified
  in the design.

Test model, lattice, Hamiltonian, parameters, observable, standard_result,
source, source_url, and citation_locator wherever a correction affects that
field. Do not test only prose substrings.

- [ ] **Step 3: Run the new tests and verify red**

Run:

    python -m pytest -q tests/test_literature_spin_model_crosschecks.py tests/test_literature_evidence_inventory.py -k "source or correction or ba3 or vesignieite or nacro2 or jiang"

Expected: failures show the old source identities and old scientific payloads.

- [ ] **Step 4: Apply the 42 exact source reassignments**

Modify each registry entry using the exact canonical identity table in the
design. Use canonical URLs:

    arxiv:<id> -> https://arxiv.org/abs/<id>
    doi:<doi>  -> https://doi.org/<doi>

Update source labels and citation locators so they identify the selected work
and the actual claim-bearing location. Do not preserve an old author/year
label after changing the canonical work.

- [ ] **Step 5: Apply all semantic and numeric corrections**

Make the full registry contract agree with the parser operands already
implemented in literature_runtime_evidence.py. Preserve legacy benchmark keys
and filenames, but correct every physical field. Keep the cubic-Ising
registered value rounded; its 5e-6 tolerance belongs in the runtime collector,
not in an altered target value.

- [ ] **Step 6: Correct independent canonical observable contracts**

Edit only the 58 authorized entries in canonical-observables.json. Keep the
file target-free and answer-free: update semantic identities,
representations, and field definitions, but do not copy source excerpts,
runtime answers, hashes, or verdicts.

- [ ] **Step 7: Run focused registry and contract tests**

Run:

    python -m pytest -q tests/test_literature_spin_model_crosschecks.py tests/test_literature_evidence_inventory.py

Expected: all tests pass; registry count remains 155.

- [ ] **Step 8: Commit registry and canonical-contract corrections**

Stage exactly:

    scripts/validation/literature_spin_model_benchmarks.py
    reference/literature-evidence/canonical-observables.json
    tests/test_literature_spin_model_crosschecks.py
    tests/test_literature_evidence_inventory.py

Run git diff --cached --check and confirm no other staged path, then commit:

    git commit -m "fix: align literature registry with primary sources"

## Task 3: Implement Exact Source Routes, HTML Extraction, and Same-Work Proofs

**Files:**

- Modify: scripts/validation/literature_evidence_sources.py
- Modify: scripts/validation/fetch_literature_evidence_sources.py
- Test: tests/test_literature_evidence_sources.py

- [ ] **Step 1: Write final route-distribution and special-route tests**

Build routes from the corrected registry and assert:

    unique sources = 137
    media = application/pdf:134, application/xml:2, text/html:1
    access = unattended:123
             challenge_or_institutional:9
             authenticated_session:3
             api_key_or_entitlement:2

Assert the exact route-kind distribution:

    aps_harvest_pdf: 78
    arxiv_export_pdf: 26
    arxiv_author_manuscript_pdf: 10
    nature_open_article_pdf: 5
    iop_article_pdf: 3
    nature_article_pdf: 2
    elsevier_article_api_xml: 2
    institutional_repository_pdf: 2
    science_article_pdf: 2
    acs_article_pdf: 1
    aip_article_discovery: 1
    author_repository_pdf: 1
    epl_iop_article_pdf: 1
    jpsj_article_pdf: 1
    oup_minimal_html: 1
    springer_content_pdf: 1

Assert these four exact route records:

    doi:10.1143/ptp.5.2.177
      kind: oup_minimal_html
      url: https://oup.silverchair-cdn.com/article-minimal/1942776
      artifact_identifier: doi:10.1143/ptp.5.2.177
      expected_media_type: text/html
      access_mode: unattended

    doi:10.1088/0305-4470/17/13/020
      kind: institutional_repository_pdf
      url: https://files01.core.ac.uk/download/pdf/572184419.pdf
      artifact_identifier: core:572184419
      work identity kind: core_same_work_output
      work identity URL: https://api.core.ac.uk/v3/outputs/572184419
      expected_media_type: application/pdf
      access_mode: unattended

    doi:10.1088/0305-4470/16/10/023
      kind: author_repository_pdf
      url: https://www.lptmc.jussieu.fr/files/maillard/PUB2/Frustrated_jav16i10p2257.pdf
      artifact_identifier: author-repository:Frustrated_jav16i10p2257.pdf
      work identity kind: author_publications_same_work
      work identity URL: https://www.lptmc.jussieu.fr/users/maillard
      expected_media_type: application/pdf
      access_mode: unattended

    doi:10.1038/s41535-026-00868-6
      kind: nature_open_article_pdf
      url: https://www.nature.com/articles/s41535-026-00868-6.pdf
      artifact_identifier: doi:10.1038/s41535-026-00868-6
      expected_media_type: application/pdf
      access_mode: unattended

- [ ] **Step 2: Run route tests and verify red**

Run:

    python -m pytest -q tests/test_literature_evidence_sources.py -k "route or distribution"

Expected: the old generic prefix routes produce 135 PDF/2 XML and the wrong
access distribution.

- [ ] **Step 3: Implement exact route overrides**

Add exact-identity overrides before prefix routing. Extend
authoritative_origin_for_route_kind so:

    oup_minimal_html -> publisher
    institutional_repository_pdf -> institutional_repository
    author_repository_pdf -> author_repository
    nature_open_article_pdf -> publisher

Keep the generic prefix fallbacks unchanged for identities not in the override
table.

- [ ] **Step 4: Write HTML response and visible-text tests**

Add positive tests for a small OUP-like HTML document containing title,
authors, DOI, summary, and both Curie-point equations. Add fail-closed tests
for:

- wrong content type;
- HTTP status other than 200;
- challenge or access-denied page;
- malformed/no-root HTML;
- script/style/comment-only anchors;
- empty visible article body;
- missing title, DOI, author, or target equation.

The visible-text result must not contain CSS, JavaScript, comments, tag names,
attributes, or hidden metadata.

- [ ] **Step 5: Run HTML tests and verify red**

Run:

    python -m pytest -q tests/test_literature_evidence_sources.py -k html

Expected: text/html is unsupported before implementation.

- [ ] **Step 6: Implement deterministic HTML support**

Use html.parser.HTMLParser, not a third-party or browser-dependent parser.
Create one deterministic helper that:

- ignores script, style, noscript, template, comments, and hidden elements;
- emits visible data nodes in document order;
- HTML-unescapes and whitespace-normalizes text;
- requires a document root and nonempty article-bearing text.

Extend validate_download_response and load_verified_source to accept text/html
only for a route that declares text/html. Record extraction as:

    tool: stdlib_html_visible_text
    version: 1
    deterministic: true
    arguments: []

- [ ] **Step 7: Write CORE same-work tests**

Create a positive CORE JSON fixture that binds:

- output ID 572184419;
- DOI 10.1088/0305-4470/17/13/020;
- the Caspers–Emmett–Magnus title and authors;
- the selected CORE PDF URL.

Negative tests independently perturb DOI, output ID, title, authors, and PDF
location. Every perturbation must fail.

- [ ] **Step 8: Write author-page same-work tests**

Create a positive author-publications HTML fixture with exact title, authors,
DOI metadata, and an href resolving to the exact Garel-Maillard PDF. Negative
tests remove or alter the title, author, link target, DOI metadata, and base
URL. Require all three evidence sources to agree: author page, PDF route, and
Crossref bibliographic metadata.

- [ ] **Step 9: Run sidecar tests and verify red**

Run:

    python -m pytest -q tests/test_literature_evidence_sources.py -k "core or author_publications or same_work"

Expected: unsupported evidence-kind or JSON-only sidecar failures.

- [ ] **Step 10: Implement media-aware sidecars in source loader and fetcher**

Keep JSON sidecars backward compatible. Add an explicit media_type to new
sidecar provenance and choose work-identity.json or work-identity.html from
the declared evidence kind. Hash and byte-count raw sidecar bytes before
parsing. Validate raw HTML locally; never synthesize an identity document
from selected fields.

Use exclusive creation for every payload, provenance, and sidecar file. A
failure before full verification must report the new directory and stop; do
not overwrite or silently repair unrelated existing cache content.

- [ ] **Step 11: Fix payload extension selection**

Use one closed mapping in both fetcher and inventory code:

    application/pdf -> pdf
    application/xml -> xml
    text/html -> html

Reject every other media type. Do not use an else branch that maps unknown
types to PDF.

- [ ] **Step 12: Write fail-closed credential-injection tests**

Add a source-scoped `--request-credential-file PATH` interface for the
fourteen non-unattended routes. This path is a user-supplied, pre-existing
read-only input: the implementation and agent must never create, edit,
move, copy, or delete it. The external JSON file has this closed schema for a
request-header authorization:

    {
      "schema_version": 1,
      "authorization_by_source_id": {
        "doi_aec03f65476f23115a77": {
          "authorization_mode": "request_headers",
          "request_headers_by_origin": {
            "https://api.elsevier.com": {
              "X-ELS-APIKey": "TEST_ONLY_NOT_A_CREDENTIAL"
            }
          }
        }
      }
    }

The value shown is a nonsecret test sentinel. A real source entry maps one or
more exact HTTPS origins to one or more headers from the closed allowlist
`Cookie`, `Authorization`, `X-ELS-APIKey`, and `X-ELS-Insttoken`; unused
origins and headers are omitted. Define a route-kind-to-origin allowlist in
the fetcher for the fourteen routes: the declared initial origin plus only the
known official publisher/API origins needed by that route kind.

For a route whose declared access mode is `challenge_or_institutional` or
`api_key_or_entitlement`, also accept this exact headerless entry when the
user confirms that the current host already has institution-network/IP
entitlement:

    {
      "authorization_mode": "institution_network",
      "request_headers_by_origin": {}
    }

Do not accept `institution_network` for `authenticated_session`, and do not
interpret the assertion as proof of success: the response must still pass the
same status, media, body, identity, and offline provenance validators. Tests
must prove that the loader:

- accepts a regular, nonsymlink file owned by the current user with no
  group/other permission bits, located outside `PROJECT_ROOT` and the cache
  root;
- rejects unknown top-level/entry fields, unknown source IDs, an unknown or
  access-mode-incompatible `authorization_mode`, empty origin/header maps for
  `request_headers`, nonempty origin maps for `institution_network`, non-HTTPS
  or non-allowlisted origins, unknown or duplicate-case header names,
  nonstring/empty values, symlinks, unsafe permissions, and any credential
  file below the repository or cache;
- rejects a selected non-unattended source before network access when its
  exact source ID has no authorization entry;
- applies credentials only to an exact allowlisted origin for that source's
  payload request, never to Crossref, arXiv, CORE/OpenAlex, author-page, or
  other sidecar requests;
- strips all credential headers before every redirect and reapplies only the
  destination origin's explicitly configured headers; a cross-origin redirect
  with no exact profile receives no secret;
- prevents credentials from overriding `Accept`, `User-Agent`, `Host`, or the
  route URL;
- rejects declared, redirect, or final URLs containing userinfo and never
  emits a URL query or fragment in stdout, stderr, exceptions, provenance, or
  work-identity provenance; and
- emits no credential value in stdout, stderr, exceptions, provenance, or
  work-identity provenance on both successful and failing requests.

Use fixed sentinel secrets in tests and recursively inspect every emitted
mapping/string and captured stream to prove absence. Include a redirect whose
final URL contains a signed-query sentinel distinct from every input
credential sentinel; require the request to use the full URL in memory but
require logs, outcomes, exceptions, and provenance to contain only the
userinfo-free URL with query and fragment removed.

- [ ] **Step 13: Run credential tests and verify red**

Run:

    python -m pytest -q tests/test_literature_evidence_sources.py -k "credential or authenticated or api_key"

Expected: argparse rejects the new option or restricted acquisition reaches
the network without a credential policy.

- [ ] **Step 14: Implement source-scoped credential injection**

Load and validate the credential file once in `main`, keep its contents only
in memory, and pass the exact selected source's origin-to-header mapping only
to `_download`. Use a credential-aware redirect handler that drops sensitive
headers at each hop and adds only those configured for the destination's exact
normalized HTTPS origin. Never pass the profile to bibliographic or same-work
requests. Redact caught network errors to status, route kind, and source ID;
never interpolate request headers or credential-file contents. Before writing
provenance, omit any response-header value containing a credential value so a
server cannot reflect a secret into the cache. Centralize URL sanitization:
reject userinfo, retain scheme/host/port/path, and remove query and fragment
before constructing any outcome detail, exception, retrieval-metadata URL, or
sidecar descriptor. Network requests may follow the full in-memory signed URL,
but no serialized or printed value may contain its query or fragment.

When `--access-mode all` selects a non-unattended route, require both
`--request-credential-file` and a valid exact-source authorization entry
before creating the cache directory or opening the network. A
`request_headers` entry must be nonempty; an eligible `institution_network`
entry is intentionally headerless. Reject an entry for an unselected or
unattended source so a broad secret profile cannot be applied accidentally.
Open the user-owned file read-only and never create, edit, copy, move, chmod,
or delete it. The credential-file path may appear in argparse diagnostics;
its contents and header names/values must not appear in cache provenance or
logs. Keep unattended acquisition working without a credential file.

- [ ] **Step 15: Run complete source tests**

Run:

    python -m pytest -q tests/test_literature_evidence_sources.py
    python -m py_compile scripts/validation/literature_evidence_sources.py scripts/validation/fetch_literature_evidence_sources.py

Expected: all pass.

- [ ] **Step 16: Commit source routing, provenance, and credential support**

Stage exactly the three files in this task, inspect the staged name list and
diff check, then commit:

    git commit -m "feat: add authoritative routes for final literature sources"

## Task 4: Enforce Final Inventory Topology and HTML Cache Contracts

**Files:**

- Modify: scripts/validation/literature_evidence_inventory.py
- Test: tests/test_literature_evidence_inventory.py
- Test: tests/test_literature_evidence_sources.py

- [ ] **Step 1: Write exact topology tests**

Assert:

- 155 benchmark contracts and records;
- 137 unique canonical sources;
- exact 33 added and 30 removed identity sets from the design;
- exact 42 benchmark source memberships;
- the four special route records;
- 134 source.pdf, 2 source.xml, and 1 source.html forecasts;
- every record remains record_state=unresolved;
- no record contains answer, excerpt, payload hash, acquired status, or verdict;
- no duplicate or orphan benchmark, source, route, locator, or cache path.

- [ ] **Step 2: Write HTML-extension rejection tests**

Corrupt an HTML route to source.pdf and a PDF route to source.html. Both must
fail inventory validation. Also reject a route whose media type has no closed
extension mapping.

- [ ] **Step 3: Run inventory tests and verify red**

Run:

    python -m pytest -q tests/test_literature_evidence_inventory.py tests/test_literature_evidence_sources.py -k "topology or identity or extension or provisioning"

Expected: final counts and HTML path tests fail.

- [ ] **Step 4: Implement the closed media-extension helper**

Use the same three-value mapping as Task 3. Validate route media before
constructing local_cache_location. Keep all records unresolved and target
free.

- [ ] **Step 5: Run complete inventory/source tests**

Run:

    python -m pytest -q tests/test_literature_evidence_inventory.py tests/test_literature_evidence_sources.py

Expected: all pass against in-memory inventory generation.

- [ ] **Step 6: Commit inventory implementation and tests**

Stage exactly:

    scripts/validation/literature_evidence_inventory.py
    tests/test_literature_evidence_inventory.py
    tests/test_literature_evidence_sources.py

Then diff-check and commit:

    git commit -m "test: lock final literature inventory topology"

## Task 5: Selectively Update the Approved Static Inventory Artifacts

**Files:**

- Modify: reference/literature-evidence/source-index.json
- Modify: reference/literature-evidence/source-provisioning.json
- Modify: reference/literature-evidence/locator-inventory.json
- Read/seed only: reference/literature-evidence/canonical-observables.json
- Modify: the exact 58 record JSON paths listed in File Responsibility Map

- [ ] **Step 1: Create a fresh temporary generation root**

Run mktemp -d and record the exact printed path. Create its records
subdirectory and copy the already-corrected canonical-observables.json into
that new root. Do not point write_inventory at the real inventory root.

- [ ] **Step 2: Generate and validate the temporary inventory**

Run a short Python command that calls:

    write_inventory(
        inventory_root=Path(the_recorded_temp_root),
        registry_entries=LITERATURE_STANDARD_RESULTS,
    )

Then load_and_validate_inventory from that temporary root. Expected counts:
155 records and 137 sources.

- [ ] **Step 3: Compute the generated diff without applying it**

Compare the temporary root with reference/literature-evidence. Produce a
sorted changed-path list. Assert that it is exactly:

- the three generated central JSON files source-index.json,
  source-provisioning.json, and locator-inventory.json; plus
- the 58 exact record files in this plan.

Canonical-observables.json was already corrected and committed in Task 2, so
it must compare equal to the seeded temporary copy at this stage. Across the
whole feature branch the static-artifact change set is still the four approved
central JSON files plus 58 records.

If any other existing path appears, stop and report it. Do not apply a partial
or widened change.

- [ ] **Step 4: Apply only the approved JSON patches**

Use apply_patch or an equivalently reviewable exact-path bulk rewrite. Do not
run the generator against the real inventory root. Do not delete old record
or cache files.

- [ ] **Step 5: Prove static artifacts are deterministic and answer-free**

Run:

    python -m pytest -q tests/test_literature_evidence_inventory.py tests/test_literature_spin_model_crosschecks.py

Regenerate into a second fresh temporary root and verify zero diff between the
second generated output and the selectively updated approved paths.

- [ ] **Step 6: Verify the changed-path boundary before staging**

Run git diff --name-only under reference/literature-evidence and compare the
unstaged set to the 61 paths generated in this task. Existing unrelated
records must have no diff.

- [ ] **Step 7: Stage and commit exact static artifacts**

Stage only the three generated central JSON files and 58 listed records.
Confirm the staged path set before committing:

    git commit -m "data: regenerate corrected literature evidence forecasts"

## Task 6: Acquire and Offline-Verify the 47 New Cache Directories

**Files:**

- Create: exactly the 47 source-cache directories in the design manifest
- Test: tests/test_literature_evidence_sources.py
- Test: tests/test_literature_runtime_evidence.py

- [ ] **Step 1: Recompute the missing-cache directory set**

For each of the 58 execution-manifest benchmark keys:

1. resolve its final source_id from source-index.json;
2. test whether source-cache/source_id exists;
3. sort and deduplicate missing paths.

Compare the result to the exact 47-path cache manifest in the design.

Expected:

    missing cache directories = 47
    benchmarks served by new caches = 56
    existing read-only gap caches = 2

The two existing paths must be:

    source-cache/doi_1ef6a4cf65b6598edb8b
    source-cache/doi_0561dc1ddfb83046e779

- [ ] **Step 2: Fetch only the declared unattended source IDs**

Call fetch_literature_evidence_sources.py with one explicit --source-id for
each missing source whose final route says unattended. Do not use --all for
acquisition. The source-index-derived ID list must equal the approved
47-directory set before the first request.

Expected: exactly 33 unattended directories are selected and acquired. Per
successful route: status=acquired, correct media signature, provenance
written, optional same-work sidecar written, and immediate offline
verification successful.

- [ ] **Step 3: Acquire the 14 declared non-unattended source IDs**

Require the user to supply a pre-existing credential/authorization JSON file
outside the repository and cache root using the Task 3 schema and mode 0600.
The agent only validates and reads this input; it must not create, edit, copy,
move, chmod, or delete it. The file contains exactly the selected
publisher/API credentials supplied by an existing entitlement or authenticated
browser session, or an explicit `institution_network` assertion for an
eligible route. Run the fetcher with
`--access-mode all --request-credential-file "$LITERATURE_CREDENTIAL_FILE"`,
where the task-specific environment variable resolves to that external 0600
file, and these exact source IDs:

    source-cache/doi_85b0ca56044270e7e63e  -> --source-id doi_85b0ca56044270e7e63e
    source-cache/doi_aec03f65476f23115a77  -> --source-id doi_aec03f65476f23115a77
    source-cache/doi_804ce6147864268c7acb  -> --source-id doi_804ce6147864268c7acb
    source-cache/doi_c580f55afb67414f9a9e  -> --source-id doi_c580f55afb67414f9a9e
    source-cache/doi_7535f50aacaae5fd8e46  -> --source-id doi_7535f50aacaae5fd8e46
    source-cache/doi_95a1148cb5d14b4d9680  -> --source-id doi_95a1148cb5d14b4d9680
    source-cache/doi_417e9be0540e18a5c1bf  -> --source-id doi_417e9be0540e18a5c1bf
    source-cache/doi_b757c34f112f5da7b6c7  -> --source-id doi_b757c34f112f5da7b6c7
    source-cache/doi_e3b1415a2e57b3de696a  -> --source-id doi_e3b1415a2e57b3de696a
    source-cache/doi_3c0cd7d12c74eed185ff  -> --source-id doi_3c0cd7d12c74eed185ff
    source-cache/doi_187f5f1c3bdb3f0bdeef  -> --source-id doi_187f5f1c3bdb3f0bdeef
    source-cache/doi_be978237972b2466880e  -> --source-id doi_be978237972b2466880e
    source-cache/doi_a368c0c9e03dd0b4142f  -> --source-id doi_a368c0c9e03dd0b4142f
    source-cache/doi_8bdac77ccac0554c0b1b  -> --source-id doi_8bdac77ccac0554c0b1b

The final access-mode split for these directories is 9
challenge_or_institutional, 3 authenticated_session, and 2
api_key_or_entitlement. Use existing institutional entitlement, API key, or
authenticated session only through the declared route. Never print a secret,
put it in provenance, copy the credential file below the repository, or
commit it. Before accepting an acquisition, scan the command's captured
stdout/stderr and all newly written JSON for every credential sentinel/value;
the scan must find zero matches. Remove no file as part of this check.

- [ ] **Step 4: Handle route failures without weakening validation**

For transient 429/5xx failures, retry the same exact route later. For a
challenge or entitlement response, do not store the response and do not
change expected media type. Use only the already designed authoritative
alternate route or an explicitly authenticated request to the declared route.

Never create a cache from:

- search-result text;
- a metadata-only page;
- a challenge page;
- a secondary paper;
- copied test fixture text;
- a payload whose DOI/title/authors cannot be bound to the canonical work.

- [ ] **Step 5: Verify all 47 exact directories offline**

Invoke the fetcher with `--verify-offline --access-mode all` and each exact
source ID. Offline verification must not require or load the credential file.
Expected: 47 verified, 0 failed. Check that:

- every PDF starts with a valid PDF signature and pdftotext succeeds;
- both XML payloads contain article body text;
- the OUP source.html passes deterministic visible-text extraction;
- CORE and author-repository sources have valid hashed identity sidecars;
- provenance hashes and byte lengths match every raw file.

- [ ] **Step 6: Replay all 58 parsers against actual cached text**

Run the actual-cache parser replay tests, not synthetic fixtures only:

    python -m pytest -q tests/test_literature_runtime_evidence.py -k "verified or replay or actual"

Expected: all selected tests pass. If a parser fails on real extraction
layout, add a fail-closed regression fixture from the verified layout, watch
it fail, minimally broaden normalization, and rerun the parser's complete
positive and negative tests.

- [ ] **Step 7: Re-run offline verification after any parser adjustment**

Parser changes must never mutate cache bytes or provenance. Re-run source
offline verification and the complete runtime evidence tests.

No Git commit is required for source-cache because it is local and ignored.
Do not force-add cached copyrighted payloads.

## Task 7: Connect the Exact 58 Collector Specs and Close Runtime Coverage

**Files:**

- Modify: scripts/validation/literature_runtime_evidence.py
- Test: tests/test_literature_runtime_evidence.py

- [ ] **Step 1: Change the authoritative coverage tests to the final contract**

Replace the 97-route expectation with:

    supported = 155
    missing = 0
    extra = 0
    invalid = 0
    complete = true
    local_recompute = 42
    local_source_parse = 113

Change the completion test from expecting RuntimeEvidenceError to requiring
assert_complete_runtime_evidence to return the complete coverage mapping.
Require collector evidence keys and extraction-trace keys to equal all 155
registry keys.

- [ ] **Step 2: Add an exact 58-contract regression test**

First extract the current function-local specs tuple into a private top-level
_runtime_evidence_specs function that returns the immutable tuple. The
collector must call that function, and tests may inspect it without opening a
cache. Do not expose a new public API.

Encode the two execution tables from the design as test data. Compare every
target spec returned by _runtime_evidence_specs:

- benchmark_name;
- final source identity;
- provisioning route kind;
- mode;
- parser function name;
- registry_fields;
- adapter function name and parameters;
- output field mapping;
- absolute tolerance.

The test must carry the full fifty-eight-row expected table, not infer source
identity or route kind from aggregate counts. For each row, require the spec's
literal `source_identity` and `route_kind` to equal the expected values, then
independently join through the generated record/source index/provisioning
inventory and require the same identity and route kind there. This locks all
58 benchmark-to-source-to-route mappings even if registry and collector drift
together.

All comparisons are exact except cubic_ising_critical_temperature_reference,
which must have absolute_tolerance=5e-6. Require exactly 58 new unique keys and
155 total collector keys.

- [ ] **Step 3: Run the final-contract tests and verify red**

Run:

    python -m pytest -q tests/test_literature_runtime_evidence.py -k "coverage or complete or exact_58_contract"

Expected before implementation: 97 supported, 58 missing.

- [ ] **Step 4: Add the 37 local_source_parse specs**

For each direct-parse row in the design, add:

    {
        "benchmark_name": exact_legacy_key,
        "source_identity": exact_final_canonical_identity,
        "route_kind": exact_provisioning_route_kind,
        "mode": "local_source_parse",
        "parser": exact_parser_symbol,
        "registry_fields": exact_selector_fields_if_narrowing_is_required,
    }

Omit registry_fields only when the record selector already equals the exact
listed selector. Do not add an adapter to a direct parse.

- [ ] **Step 5: Add the 21 local_recompute specs**

For each recompute row, add:

    {
        "benchmark_name": exact_legacy_key,
        "source_identity": exact_final_canonical_identity,
        "route_kind": exact_provisioning_route_kind,
        "mode": "local_recompute",
        "parser": exact_parser_symbol,
        "adapter": exact_recompute_symbol,
        "adapter_parameters": exact_arguments,
        "output_fields": exact_registry_to_adapter_field_map,
    }

Use output_field only for a scalar adapter. For Kano-Naya and Garel-Maillard,
select only macroscopic_ground_state_degeneracy from the richer adapter
output. Set absolute_tolerance=5e-6 only on the cubic-Ising row.

- [ ] **Step 6: Add collector spec validation before source access**

Fail before touching a cache on:

- duplicate benchmark keys;
- unknown registry keys;
- either `source_identity` or `route_kind` missing from one of the exact 58
  manifest-bound specs;
- a spec source identity inconsistent with the record/source index;
- a spec route kind inconsistent with source-provisioning.json;
- invalid mode;
- missing or unexpected adapter;
- missing parser/adapter name;
- empty or widening registry_fields;
- tolerance on any nonnumeric or unapproved row;
- unexpected output fields.

- [ ] **Step 7: Run focused collector tests**

Run:

    python -m pytest -q tests/test_literature_runtime_evidence.py -k "collector or coverage or complete or exact_58_contract"

Expected: all pass against actual verified caches.

- [ ] **Step 8: Run complete runtime suite**

Run:

    python -m pytest -q tests/test_literature_runtime_evidence.py

Expected: all tests pass. The authoritative collector output must be exactly
155/155, not merely the synthetic structural validator.

- [ ] **Step 9: Commit collector completion**

Stage exactly runtime implementation and runtime tests, diff-check, then:

    git commit -m "feat: complete strict runtime evidence coverage"

## Task 8: Correct Audit Semantics and Final PDF Expectations

**Files:**

- Modify: scripts/validation/literature_reproduction_audit.py
- Test: tests/test_literature_reproduction_audit.py
- Test: tests/test_literature_reproduction_audit_pdf.py

- [ ] **Step 1: Write final audit-count tests**

Require:

    total_standard_results = 155
    strict_local_recomputed = 42
    strict_local_source_parsed = 113
    local_projection_only = 0
    executable_projection = 0
    reference_only = 0
    strict yes rows = 155
    strict no rows = 0
    remaining gap rows = 0

Runtime-disabled audit must remain hermetic and non-strict; do not weaken that
negative control.

- [ ] **Step 2: Write corrected-description tests**

Assert that audit rows use corrected registry physics for Ba3IrTi2O9,
NaCrO2, Vesignieite, Ruby, Jiang-Wiese, square ring exchange, triangular
plateau, GGG/GTLG, star, and shuriken. Explicitly reject stale phrases such as
clean honeycomb Kitaev for Ba3IrTi2O9, NaCuO2 physical data, distortion-led
Vesignieite, and a Ruby plateau-mechanism claim.

- [ ] **Step 3: Run final audit tests and verify red**

Run:

    python -m pytest -q tests/test_literature_reproduction_audit.py tests/test_literature_reproduction_audit_pdf.py

Expected before audit updates: stale count and/or description failures.

- [ ] **Step 4: Update audit descriptions and gap logic**

Keep runtime evidence authoritative. Audit prose may describe verified
results, but must not promote local projection metadata to strict evidence.
When coverage is complete, the remaining-gaps writer must emit an explicit
zero-gap summary rather than stale upgrade advice.

- [ ] **Step 5: Update PDF payload expectations without editing the generator**

Modify only tests/test_literature_reproduction_audit_pdf.py. Require the
existing generator payload to report strict_match_count=155, zero remaining
rows, and both strict mode counts. Do not stage or modify
reports/generate_literature_reproduction_audit_pdf.py.

- [ ] **Step 6: Run audit and PDF tests**

Run:

    python -m pytest -q tests/test_literature_reproduction_audit.py tests/test_literature_reproduction_audit_pdf.py
    python -m py_compile scripts/validation/literature_reproduction_audit.py

Expected: all pass.

- [ ] **Step 7: Commit audit completion**

Stage exactly the audit implementation and two test files, inspect staged
paths, then:

    git commit -m "feat: report strict 155-of-155 literature coverage"

## Task 9: Generate and Inspect New 155_of_155 Reports

**Files:**

- Create: reports/literature_reproduction_audit_155_of_155.md
- Create: reports/literature_reproduction_audit_155_of_155.csv
- Create: reports/remaining_strict_reproduction_gaps_155_of_155.md
- Create: reports/literature_reproduction_audit_155_of_155.pdf

- [ ] **Step 1: Generate Markdown, CSV, and zero-gap report to new paths**

Run:

    python scripts/validation/literature_reproduction_audit.py \
      --markdown reports/literature_reproduction_audit_155_of_155.md \
      --csv reports/literature_reproduction_audit_155_of_155.csv \
      --remaining-gaps reports/remaining_strict_reproduction_gaps_155_of_155.md

Expected printed counts: 42 recomputed, 113 source parsed, and no non-strict
category.

- [ ] **Step 2: Render the PDF to the explicit new path**

Import the existing user-owned generator without editing it:

    python -c "import sys; from pathlib import Path; sys.path.insert(0, 'reports'); import generate_literature_reproduction_audit_pdf as g; p=g.build_reproduction_pdf_payload(); g.write_reproduction_pdf(p, Path('reports/literature_reproduction_audit_155_of_155.pdf'))"

- [ ] **Step 3: Inspect report text mechanically**

Require all of:

    155 of 155
    strict_local_recomputed = 42
    strict_local_source_parsed = 113
    zero remaining strict reproduction gaps

Reject all stale completion strings:

    43 of 155
    97 of 155
    Missing: 58
    Complete: False

Validate CSV has one header plus 155 unique benchmark rows.

- [ ] **Step 4: Inspect PDF text and rendering**

Run pdftotext on the new PDF and apply the same positive and negative string
checks. Render representative pages to new temporary PNG files with
pdftoppm, then inspect them with view_image. Check title, count summary,
category legend, table clipping, line wrapping, Unicode rendering, and the
zero-gap statement.

- [ ] **Step 5: Confirm stale reports are byte-untouched**

Re-run sha256sum and compare to the five exact baseline hashes in Normative
Inputs and Current State. The four unsuffixed or 43_of_155 report files and
the user-owned generator must remain byte-identical.

- [ ] **Step 6: Force-stage only the four new reports**

Reports may be ignored. Use git add -f with the four exact new paths. Confirm
the staged name set and commit:

    git commit -m "docs: publish strict 155-of-155 literature audit"

## Task 10: Full Completion Audit

**Files:** All authorized implementation paths and four new reports.

- [ ] **Step 1: Compile every modified Python file**

Run python -m py_compile on:

    scripts/validation/literature_spin_model_benchmarks.py
    scripts/validation/literature_evidence_sources.py
    scripts/validation/fetch_literature_evidence_sources.py
    scripts/validation/literature_evidence_inventory.py
    scripts/validation/literature_runtime_evidence.py
    scripts/validation/literature_reproduction_audit.py

- [ ] **Step 2: Run the complete relevant pytest suite**

Run:

    python -m pytest -q \
      tests/test_literature_evidence_sources.py \
      tests/test_literature_evidence_inventory.py \
      tests/test_literature_spin_model_crosschecks.py \
      tests/test_literature_runtime_evidence.py \
      tests/test_literature_reproduction_audit.py \
      tests/test_literature_reproduction_audit_pdf.py

Expected: every test passes. Do not cite the earlier 395-test or 1520-test
baselines as final evidence.

- [ ] **Step 3: Offline-verify every final source**

Run:

    python scripts/validation/fetch_literature_evidence_sources.py \
      --all --verify-offline --access-mode all

Expected: total=137, verified=137, failed=0. Removed-identity caches may remain
on disk but are not selected by the final source index.

- [ ] **Step 4: Run the authoritative coverage assertion**

Run a Python command that calls assert_complete_runtime_evidence with
LITERATURE_STANDARD_RESULTS and prints only:

    supported=155
    missing=0
    extra=0
    invalid=0
    complete=True

Then independently count evidence modes from the returned collector bundles:

    local_recompute=42
    local_source_parse=113

- [ ] **Step 5: Validate exact inventory and report sets**

Prove:

- registry names = inventory record names = collector evidence names = report
  CSV names, all with cardinality 155;
- source-index names = provisioning names, cardinality 137;
- no duplicate or orphan source/record/route/cache path;
- four final reports exist and stale reports are untouched;
- every changed existing path belongs to the 74-path authorization manifest;
- every created cache/report path belongs to its exact create manifest.

- [ ] **Step 6: Check Git integrity and file safety**

Run:

    git diff --check
    git status --short
    git diff --name-only
    git diff --cached --name-only

Do not clean, reset, delete, move, or truncate anything. The user-owned
generator diff and stale untracked reports may remain visible and must not be
claimed as our staged work.

- [ ] **Step 7: Perform verification-before-completion review**

Invoke @superpowers:verification-before-completion. Re-run any command whose
output is stale, partial, or narrower than its claim.

- [ ] **Step 8: Request code review**

Invoke @superpowers:requesting-code-review for the completed implementation.
Resolve every correctness or safety blocker with tests and repeat the
completion commands affected by the fix.

- [ ] **Step 9: Mark the persistent goal complete only on fresh evidence**

Completion is allowed only when all exact contracts above are proven by the
current worktree. If any source cannot be acquired and verified, any parser
does not replay, any count differs, or any unauthorized path changed, keep the
goal active and continue remediation.
