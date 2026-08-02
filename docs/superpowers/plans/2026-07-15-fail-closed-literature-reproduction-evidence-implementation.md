# Fail-Closed Literature Reproduction Evidence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** Replace the self-certifying 155-entry audit with a source-backed audit that proves every registered observable matches its cited literature by independent local recomputation or executable local source parsing.

**Architecture:** Keep the existing registry as the catalog, but move proof into authoritative source snapshots, independent canonical observable specifications, per-benchmark evidence records, runtime parsers, isolated recomputation adapters, and one fail-closed audit manifest. The audit obtains the literature operand from hashed source bytes and the registry operand independently, executes recomputation adapters under network and file-access controls when required, and derives every report from the manifest.

**Tech Stack:** Python 3, pytest, JSON, SHA-256, curl, pdftotext, unshare, strace, NumPy/SciPy, existing ED/GLT/TenPy helpers, Matplotlib.

**Working Directory:** Run every relative path and command below from /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier. Git add and commit commands run from /data/work/zhli/soft/Design_Mott_Materials and therefore prefix paths with translation-invariant-spin-model-simplifier.

---

## File Map

- Create scripts/validation/literature_evidence_schema.py for validated source, contract, record, trace, and outcome types.
- Create scripts/validation/literature_evidence_sources.py for offline provenance, hash, payload, PDF/text, and locator verification.
- Create scripts/validation/literature_evidence_parsers.py for runtime numeric and typed-claim extraction.
- Create scripts/validation/literature_evidence_comparators.py for structured comparisons and uncertainty checks.
- Create scripts/validation/literature_evidence_adapters.py for pure analytic, ED, GLT, DMRG, and numerical adapters.
- Create scripts/validation/literature_evidence_isolation.py for fresh-process isolation, dependency closure, file-access policy, and counterfactual checks.
- Create scripts/validation/fetch_literature_evidence_sources.py as the explicit online acquisition CLI.
- Create scripts/validation/verify_literature_reproduction_manifest.py as the independent all-artifact completion verifier.
- Replace verdict logic in scripts/validation/literature_reproduction_audit.py.
- Modify scripts/validation/literature_spin_model_benchmarks.py only where pure calculations or registry selectors are needed.
- Create reference/literature-evidence/canonical-observables.json.
- Create reference/literature-evidence/source-index.json.
- Create reference/literature-evidence/source-provisioning.json with one acquisition/provisioning route per source.
- Create reference/literature-evidence/sources/<source-id>/provenance.json and payload artifacts.
- Create reference/literature-evidence/records/<benchmark-name>.json.
- Create focused tests in tests/test_literature_evidence_*.py.
- Create tests/test_literature_reproduction_manifest_verifier.py for independent completion-verifier RED/GREEN and tamper cases.
- Rewrite runtime assertions in tests/test_literature_reproduction_audit.py.
- Update reports/generate_literature_reproduction_audit_pdf.py and its tests.

## Task 1: Freeze The False-Positive Baseline

**Files:** Modify and test tests/test_literature_reproduction_audit.py.

- [ ] Write failing tests proving that prose-only evidence, evidence containing "checked only", and a hard-coded published-result helper cannot yield strict yes without a runtime record and extraction/execution trace.
- [ ] Run: python -m pytest tests/test_literature_reproduction_audit.py -k "prose_only or checked_only or hard_coded_parse" -q
- [ ] Confirm RED because the current whitelist promotes these cases.
- [ ] Save a diagnostic assertion exposing whitelist-only promotions, zero-task rows, and weak-marker rows without hard-coding a desired final count.
- [ ] Commit only the RED tests with forced add because tests are ignored by the repository root.

## Task 2: Implement Fail-Closed Schemas

**Files:** Create scripts/validation/literature_evidence_schema.py and tests/test_literature_evidence_schema.py.

- [ ] Write tests rejecting missing fields, duplicate names, orphan records, evidence-supplied targets/verdicts, free-text-only normalization, unsupported modes, and invalid canonical observable IDs.
- [ ] Run the new test and verify import-failure RED.
- [ ] Implement immutable CanonicalObservable, SourceProvenance, EvidenceRecord, ExtractionTrace, AdapterTrace, ComparisonTrace, and AuditOutcome types.
- [ ] Implement canonical JSON serialization.
- [ ] Implement pre-run registry-to-record and post-run registry-to-outcome-to-report set-equality gates.
- [ ] Run: python -m pytest tests/test_literature_evidence_schema.py -q
- [ ] Commit GREEN.

## Task 3: Implement Structured Comparators

**Files:** Create scripts/validation/literature_evidence_comparators.py and extend tests/test_literature_evidence_schema.py.

- [ ] Write RED tests for exact scalar/boolean/string, absolute and relative tolerance, intervals, sets, sequences, typed claims, unit mismatch, NaN/Inf, and uncertainty propagation.
- [ ] Implement comparators that accept explicit operands and return both operands, error, tolerance, and mismatch reason.
- [ ] Fail when local uncertainty is incompatible with the literature tolerance.
- [ ] Run the full schema/comparator test and commit GREEN.

## Task 4: Create The Complete Contract, Record, And Locator Inventory

**Files:** Create reference/literature-evidence/canonical-observables.json, source-index.json, source-provisioning.json, and exactly 155 provisional records; extend schema tests.

- [ ] Write RED tests requiring exact set equality among 155 registry names, 155 canonical contracts, and 155 provisional record filenames.
- [ ] Require every contract to define subject, system/material, Hamiltonian, parameter regime, size/limit, observable, representation, units, and conditions.
- [ ] Reject generic contracts such as material_reference that do not identify the actual claim.
- [ ] Implement registry selectors that independently resolve each canonical registry operand; mutate records and prove selector output is unchanged.
- [ ] Require every provisional record to define source ID, registry selector, canonical observable ID, evidence mode, target locator strategy, parser strategy, comparator, and unresolved reason, but no parsed target or verdict.
- [ ] Generate source-index.json and assert exactly 137 unique canonical DOI/arXiv sources covering all 155 records.
- [ ] Generate source-provisioning.json with authoritative retrieval route, expected media type, redistributability, local cache location, and current availability for all 137 sources.
- [ ] Build a 155-row locator inventory before fetching: each row states the expected source section/equation/table/abstract/figure-caption class and target representation without supplying the target answer.
- [ ] Confirm every provisional record fails closed as unresolved.
- [ ] Commit the complete provisional inventory before adding any strict passes.

## Task 5: Acquire And Verify 137 Authoritative Sources

**Files:** Create source modules, source tests, source payloads, and complete source provisioning status.

- [ ] Write fixture-based RED tests requiring source title, authors, venue, publication date, canonical DOI/arXiv identity, authoritative origin, retrieval URL/date/method, HTTP or repository response metadata, immutable artifact identifier, media type, raw payload hash/length, license/access notes, citation-metadata verification result, and exact parent coordinates.
- [ ] Treat every missing, empty, internally inconsistent, or malformed provenance field as fail closed in schema validation, offline verification, manifest projection, report projection, and final completion verification.
- [ ] Add explicit RED cases for empty payloads, source-ID versus registry-URL disagreement, manually authored payloads, and metadata that does not contain the target observable.
- [ ] Implement an offline loader that never performs network access, verifies hashes/provenance, and records deterministic PDF extraction tool/version.
- [ ] Implement an explicit online fetch CLI using DOI content negotiation, publisher/repository links, APS harvest, arXiv, and authoritative author/institutional repositories.
- [ ] Fetch: env -u SSL_CERT_FILE -u REQUESTS_CA_BUNDLE python scripts/validation/fetch_literature_evidence_sources.py --all --resume
- [ ] Report acquisition as candidate, metadata-only, blocked, or failed; never count acquisition as a benchmark pass.
- [ ] Resolve every metadata-only or blocked source using the exact cited primary source. Do not silently substitute a review.
- [ ] For restricted payloads, execute the source-specific provisioning route into the declared local cache and verify immutable ID, raw hash, media type, and target-bearing locator. A fresh local audit fails source_unavailable when that cache is absent.
- [ ] Run an early feasibility gate proving all 137 source payloads are locally present and every one of 155 locator inventories resolves to target-bearing source content.
- [ ] Verify: python scripts/validation/fetch_literature_evidence_sources.py --verify-offline --all
- [ ] Final source gate: 137/137 authoritative payloads verified; 155/155 target locators resolve; zero metadata-only, blocked, failed, unavailable, or unhashed artifacts.
- [ ] Commit redistributable payloads plus the complete provisioning manifest. Never represent an unprovisioned restricted source as portable or passing.

## Task 5A: Correct Three Design-Blocked Unattended Routes

This controlled amendment implements the exact contracts in the 2026-08-02
design appendix. It must complete before the source-acquisition gate can count
the three affected sources. Use `superpowers:subagent-driven-development` with
one fresh implementer at a time. Every implementer follows
`superpowers:test-driven-development`, commits only its authorized paths, and is
followed first by spec-compliance review and then code-quality review.

The repository root for every path below is
`/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit`;
commands that name `tests/`, `scripts/`, `reference/`, or `source-cache/` run
from its `translation-invariant-spin-model-simplifier/` child unless stated
otherwise. All subagents are explicitly configured as `gpt-5.6-sol` with
`reasoning_effort=xhigh`; Fast mode is forbidden.

The amended design received explicit independent approval at commit `b097558`.
Before Task 5A.1, commit only this plan, dispatch a fresh read-only plan
reviewer under the same non-Fast model configuration, and resolve every
blocking executability or contract-coverage issue before editing tests or
production code.

### Task 5A.0: Preserve The Pre-Implementation State

**External read-only comparison artifacts:**

- `/tmp/literature-evidence-task6-audit.Z4uIC2bC/source-cache-route-amendment-baseline.jsonl`
- `/tmp/literature-evidence-task6-audit.Z4uIC2bC/route-amendment-protected-user-files-baseline.json`

- [x] Before the first mutation-first amendment test edit/run, production edit,
  static regeneration, or acquisition, confirm all three target cache
  directories are absent and capture all 471 existing lstat entries below all
  143 direct cache directories. Pin the manifest SHA-256 to
  `e9430235340c6cb2fc5d4f451631a0371d4d41a5d7892a183c6f704dabb933df`.
  For regular files record type, mode bits, byte length, and content SHA-256;
  for directories record type and mode bits; for symlinks record type, mode
  bits, and exact non-followed target. Preserve exact baseline path membership
  and descendant membership.
- [x] Compare all 381 non-root entries under the 113 direct source directories
  in the earlier 382-entry Task 6 manifest and require its SHA-256
  `7703d8ba51f1cece5dcce3cc5ba04a89c709cc2e157ce55f6d889d3e3514f5d8`.
- [x] Capture exact repository-relative path, lstat regular-file type,
  permission bits, byte length, and SHA-256 for the six protected user files;
  pin the six-entry manifest SHA-256 to
  `71d8baa3394529645c0527af5ca328158700239271bbdb5e1c386ae9ad10bf09`.
  The exact protected paths are:

      translation-invariant-spin-model-simplifier/reports/generate_literature_reproduction_audit_pdf.py
      translation-invariant-spin-model-simplifier/tests/test_literature_reproduction_audit_pdf.py
      translation-invariant-spin-model-simplifier/reports/literature_reproduction_audit.csv
      translation-invariant-spin-model-simplifier/reports/literature_reproduction_audit.md
      translation-invariant-spin-model-simplifier/reports/literature_reproduction_audit_43_of_155.pdf
      translation-invariant-spin-model-simplifier/reports/remaining_strict_reproduction_gaps.md
- [ ] Before and after every amendment test run, commit, regeneration,
  acquisition, and review, compare the same authoritative manifests. Existing
  baseline entries may not change or gain/lose descendants; after acquisition,
  only the three previously absent target subtrees may be additional cache
  paths. Never stage or commit any of the six protected files.

### Task 5A.1: Lock The Amended Route Contracts In RED Tests

**Files:**

- Modify `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_sources.py`
- Modify `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_inventory.py`
- Modify `translation-invariant-spin-model-simplifier/tests/test_literature_spin_model_crosschecks.py`

- [ ] Re-run the Task 5A.0 baseline comparators, then add exact route-shape
  tests for the Garel HAL descriptor, current CORE download URL, correct OUP
  slash DOI/source ID/artifact, and Crossref OUP sidecar.
- [ ] Pin the Garel request to the query-free HAL API base and this exact ordered
  in-memory parameter sequence, with no default projection, alternate query,
  sort, pagination, or serialization of query values:

      q=halId_s:hal-02340631 AND version_i:1
      fl=docid,linkExtId_s,linkExtUrl_s,title_s,journalTitle_s,authFullName_s,halId_s,uri_s,version_i,submitType_s,docType_s,issue_s,page_s,volume_s,doiId_s,producedDateY_i,publicationDate_s
      rows=1
      start=0
      wt=json

- [ ] Add Garel positive and independent-mutation tests for duplicate-key-free
  JSON; `numFound=1`, `start=0`, `numFoundExact=true`, and one document;
  `docid="2340631"`, `halId_s="hal-02340631"`, `version_i=1`, and exact stable
  URI; `submitType_s="notice"` and `docType_s="ART"`; exact DOI; title
  `Study of a two-dimensional fully frustrated model`; ordered `T. Garel`,
  `J-M. Maillard` authors; HAL venue
  `Journal of Physics A: Mathematical and General (1975 - 2006)`; volume 16,
  issue 10, pages 2257-2265, year 1983/date 1983-07-11; ISTEX ID and exact
  `https://api.istex.fr/document/315C04C1B2CFE6FA0DE1A3BAA04E06FA586E5893/fulltext/pdf?sid=hal`
  URL; Crossref agreement; PDF title/authors/header fingerprint; sidecar
  hash/length/media/path; and memory-only query construction.
- [ ] Add CORE positive and independent-mutation tests proving that the exact
  API output is fetched and validated before the first PDF request is even
  constructed. Pin output ID 572184419, DOI
  `10.1088/0305-4470/17/13/020`, title
  `The Majumdar-Ghosh chain:Twofold ground state and elementary excitations`,
  `fulltextStatus="enabled"`, download URL
  `https://core.ac.uk/download/572184419.pdf`, and ordered raw authors
  `Caspers, W.J.`, `Emmett, K.M.`, `Magnus, W.` mapping exactly to tuples
  `(caspers, wj)`, `(emmett, km)`, `(magnus, w)`.
- [ ] Pin the CORE redirect sequence to exactly
  `core.ac.uk/download/572184419.pdf`,
  `fileserver-az.core.ac.uk/download/572184419.pdf`, then
  `pdf.core.ac.uk/corefilesystem/pdf/363/572184419.pdf`; test final-only signed
  query redaction, two-redirect maximum, and rejection-before-request for any
  other origin/path, userinfo, fragment, or earlier-hop query.
- [ ] Replace the invalid OUP dotted-DOI expectations with slash-form DOI tests
  using exact source ID `doi_457c49167653440059e9`, artifact
  `oup-silverchair-article-minimal:1942776`, and Crossref URL
  `https://api.crossref.org/works/10.1143%2Fptp%2F5.2.177`. Add independent
  mutations for response shape; slash DOI; title
  `The Statistics of Honeycomb and Triangular Lattice. I`; ordered author
  tuples `(Husimi, K.)`, `(Syozi, I.)`; publisher
  `Oxford University Press (OUP)`/member 286; journal-article type; volume 5,
  issue 2, pages 177-186; primary-resource URL
  `https://academic.oup.com/ptp/article-lookup/doi/10.1143/ptp/5.2.177`; and raw
  sidecar hash/length/media/path.
- [ ] Pin the OUP DOM to exactly one `.minimal-article-container` containing one
  `.article-header` before one `.article-content`; exactly one
  `.ww-citation-primary` below header but outside content; and exactly one
  `.ref-list` below content but outside header. Require exactly one identity DOI
  anchor whose href and visible text are the single canonical carrier. Invert
  the old positive test so that a second canonical DOI element or plain-text
  carrier outside the exact reference list is rejected, just like a conflicting
  carrier.
- [ ] Add production-layout CSS-v2 tests for the three required compound
  selectors; positive tests for existing non-hiding selector behavior and
  statement-form `@charset`/`@layer`; and negative tests for hiding selectors
  with multiple/sibling combinators, attributes, pseudos, universal/namespace
  forms, escapes, malformed syntax, block/external/other at-rules, external
  CSS, or limit violations. Scope descriptor v2 to this exact corrected OUP
  route and preserve v1 everywhere else.
- [ ] Update exact inventory expectations to 137 sources and replace only the
  invalid OUP source identity/path. Lock aggregate media/route/access counts.
- [ ] Run the new selectors before production edits and record expected failures
  caused by the missing HAL kind, stale CORE URL, invalid OUP identity, absent
  Crossref OUP validator, and unsupported CSS-v2 grammar—not fixture or syntax
  errors.
- [ ] Commit only the three test files with message
  `test: define corrected literature acquisition routes`.

### Task 5A.2: Implement HAL Same-Work Evidence

**Files:**

- Modify `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_sources.py`
- Modify `translation-invariant-spin-model-simplifier/scripts/validation/fetch_literature_evidence_sources.py`
- Test `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_sources.py`

- [ ] Add the exact `hal_same_work_bibliographic_payload` route descriptor for
  DOI `10.1088/0305-4470/16/10/023` without changing its primary PDF route.
- [ ] Construct exactly the Task 5A.1 ordered query against
  `https://api.archives-ouvertes.fr/search/` in memory for stable record
  `hal-02340631v1`; serialize only that query-free/userinfo-free API base and
  `https://hal.science/hal-02340631v1`.
- [ ] Fetch the HAL response once, validate the exact raw bytes with strict JSON
  duplicate rejection, and store those same bytes as `work-identity.json` with
  hashed sidecar provenance.
- [ ] Require `numFound=1`, `start=0`, `numFoundExact=true`, one document, and
  every exact HAL field/value pinned by the design: identifiers, URI,
  notice/ART types, DOI, one-element title, ordered authors, long journal title,
  volume/issue/pages/year/date, and exact ISTEX ID/URL.
- [ ] Implement exact HAL/Crossref/PDF transitive agreement on DOI, title,
  ordered `(garel, t)`/`(maillard, jm)` tuples, volume, issue, pages, and date.
  Require Crossref venue `Journal of Physics A: Mathematical and General` and
  PDF header
  `J. Phys. A : Math. Gen. 16 (1983) 2257-2265. Printed in Great Britain`,
  exact title, and ordered `T Garel` then `J M Maillard` anchors. Permit PDF DOI
  absence only for this exact route when both other identity checks pass. Do
  not invoke or weaken the author-page HTML validator.
- [ ] Run the focused HAL tests and all existing author-sidecar/CSS/redirect
  non-regression tests; obtain GREEN.
- [ ] Run `python -m py_compile` on both source modules and the test module.
- [ ] Commit only the two production modules with message
  `fix: bind Garel source through HAL metadata` (the RED-test commit remains its
  own parent).
- [ ] Re-run both Task 5A.0 comparators after tests and after the commit.

### Task 5A.3: Implement The Current CORE Route

**Files:**

- Modify `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_sources.py`
- Modify `translation-invariant-spin-model-simplifier/scripts/validation/fetch_literature_evidence_sources.py`
- Test `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_sources.py`

- [ ] Replace only the exact Caspers-Emmett-Magnus primary URL with
  `https://core.ac.uk/download/572184419.pdf`.
- [ ] Add a route-specific redirect state machine for the exact three
  origin/path pairs pinned in Task 5A.1, exactly two redirects, and a
  final-hop-only signed query. Reject an unsafe target before constructing or
  issuing its request.
- [ ] Strip all redirect queries from diagnostics, outcomes, main provenance,
  sidecar provenance, and exceptions.
- [ ] Implement the ordered family/initial author canonicalizer for CORE,
  Crossref, and PDF representations with exact order/cardinality and
  ambiguity/collision rejection.
- [ ] Fetch and validate the raw CORE output before constructing or issuing the
  first PDF request; require every exact Task 5A.1 ID/DOI/title/status/URL/author
  value and retain the same raw bytes as the hashed sidecar.
- [ ] Run focused CORE tests plus the complete redirect/credential/redaction
  regression group; obtain GREEN.
- [ ] Commit only the two production modules with message
  `fix: follow the current CORE full-text route`.
- [ ] Re-run both Task 5A.0 comparators after tests and after the commit.

### Task 5A.4: Correct The OUP Canonical Source And Inventory Generator

**Files:**

- Modify `translation-invariant-spin-model-simplifier/scripts/validation/literature_spin_model_benchmarks.py`
- Modify `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_inventory.py`
- Test `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_inventory.py`
- Test `translation-invariant-spin-model-simplifier/tests/test_literature_spin_model_crosschecks.py`

- [ ] Change exactly the two Husimi-Syozi benchmark source URLs from the invalid
  dotted hybrid to `https://doi.org/10.1143/ptp/5.2.177`.
- [ ] Require deterministic source ID `doi_457c49167653440059e9`, cache path
  `source-cache/doi_457c49167653440059e9/source.html`, OUP artifact
  `oup-silverchair-article-minimal:1942776`, and
  `crossref_oup_same_work` sidecar.
- [ ] Preserve 137 unique sources, 155 benchmark mappings, 134 PDF / 2 XML / 1
  HTML media counts, and all unaffected route/access counts.
- [ ] Run both complete inventory and benchmark-crosscheck modules; obtain
  GREEN.
- [ ] Commit only the two production modules with message
  `fix: correct the Husimi-Syozi DOI identity`.
- [ ] Re-run both Task 5A.0 comparators after tests and after the commit.

### Task 5A.5: Implement OUP Crossref Binding, DOI Scoping, And CSS V2

**Files:**

- Modify `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_sources.py`
- Modify `translation-invariant-spin-model-simplifier/scripts/validation/fetch_literature_evidence_sources.py`
- Test `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_sources.py`

- [ ] Move the exact OUP route override to slash-form DOI and add the exact OUP
  artifact and `crossref_oup_same_work` descriptor.
- [ ] Fetch the exact query-free Crossref Works URL once; derive main
  bibliographic metadata and store `work-identity.json` from the same raw bytes.
  Require the slash DOI, title
  `The Statistics of Honeycomb and Triangular Lattice. I`, ordered tuples
  `(Husimi, K.)` then `(Syozi, I.)`, OUP publisher/member 286,
  journal-article type, volume 5, issue 2, pages 177-186, and primary-resource
  URL `https://academic.oup.com/ptp/article-lookup/doi/10.1143/ptp/5.2.177`.
- [ ] Implement the exact one-container/header/content/citation/reference-list
  DOM hierarchy and cardinality from Task 5A.1. Require visible title, exact
  full authors `Kodi Husimi` and `Itiro Syôzi`, bibliographic coordinates,
  Summary, both equations, and exactly one header identity-anchor carrier;
  exclude only DOI values inside the structurally exact reference list.
- [ ] Implement only CSS-v2's one-simple-parent/ancestor plus exactly one child
  or descendant combinator plus one simple target, using the real ancestor
  stack and transitive hiding. Fail closed on every prohibited hiding selector,
  hiding value/function, stylesheet structure, external resource, and limit.
  Preserve existing non-hiding-selector and statement-form at-rule behavior.
  Select descriptor v2 only for this exact corrected OUP route and retain v1
  everywhere else.
- [ ] Run the complete OUP/CSS/HTML/DOI/sidecar/redaction test groups and then
  the entire source test module; obtain GREEN.
- [ ] Commit only the two production modules with message
  `fix: validate the corrected OUP article identity`.
- [ ] Re-run both Task 5A.0 comparators after tests and after the commit.

### Task 5A.6: Regenerate Only The Authorized Static Inventory

**Files:**

- Modify `translation-invariant-spin-model-simplifier/reference/literature-evidence/source-index.json`
- Modify `translation-invariant-spin-model-simplifier/reference/literature-evidence/source-provisioning.json`
- Modify `translation-invariant-spin-model-simplifier/reference/literature-evidence/locator-inventory.json`
- Modify `translation-invariant-spin-model-simplifier/reference/literature-evidence/records/honeycomb_ising_ferromagnet_exact_tc.json`
- Modify `translation-invariant-spin-model-simplifier/reference/literature-evidence/records/triangular_ising_ferromagnet_exact_tc.json`

- [ ] Generate the full inventory into a fresh external temporary root rather
  than in place.
- [ ] Compare all generated paths and semantic JSON values against HEAD.
- [ ] Require exactly the five authorized static paths above to differ; copy
  them with the established deterministic generator workflow and do not touch
  any other existing file.
- [ ] Prove the Garel and CORE static effect is confined to their provisioning
  rows, while the OUP identity changes the source index, provisioning, two
  locator rows, and two named records.
- [ ] Run `git diff --check`, exact topology tests, and a second independent
  temporary-root regeneration; require byte-identical output.
- [ ] Commit only the five static files with message
  `data: regenerate corrected acquisition routes`.
- [ ] Re-run both Task 5A.0 comparators before regeneration, after each
  temporary regeneration, after installing the authorized five-file result,
  after tests, and after the commit.

### Task 5A.7: Acquire And Replay The Three Corrected Sources

**New cache directories:**

- `translation-invariant-spin-model-simplifier/source-cache/doi_dba239926d673e54f80a/`
- `translation-invariant-spin-model-simplifier/source-cache/doi_e49cda761520424da334/`
- `translation-invariant-spin-model-simplifier/source-cache/doi_457c49167653440059e9/`

- [ ] Verify the unchanged authoritative 471-entry Task 5A.0 manifest and its
  exact hash; do not replace it with a later pre-acquisition snapshot.
- [ ] Invoke the exact source-specific acquisition command once per absent
  target, using `--source-id` for exactly
  `doi_dba239926d673e54f80a`, `doi_e49cda761520424da334`, and
  `doi_457c49167653440059e9`. Use no credential-file argument and no alternate
  or undeclared route.
- [ ] Require primary response/media validation, raw sidecar validation,
  bibliographic identity, target-bearing anchors, complete hashed provenance,
  and atomic installation.
- [ ] After each acquisition, compare all 471 baseline entries and the six
  protected files before continuing; allow only the successfully validated
  target subtree as an additional cache path.
- [ ] Run `--verify-offline --source-id` separately for each new directory and
  then the full offline source verifier. Report restricted gaps honestly; do
  not promote the deferred fourteen sources.
- [ ] At the end, require exact attribute/path equality for all 471 baseline
  entries and exactly the three authorized new cache subtrees—no other additions.
- [ ] Confirm all signed/query values and any secret-shaped test sentinels are
  absent from cache files, provenance, command output retained for review, and
  git diff.
- [ ] Cache directories remain ignored and are not committed.

### Task 5A.8: Completion Gate And Reviews

- [ ] Run the three affected test modules from a clean process:

      PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider \
        tests/test_literature_evidence_sources.py \
        tests/test_literature_evidence_inventory.py \
        tests/test_literature_spin_model_crosschecks.py -q

- [ ] Run the wider Task 1-5 regression command used by the preceding static
  inventory completion gate.
- [ ] Reconfirm exact static topology: 137 canonical sources, 155 locators,
  134 PDF / 2 XML / 1 HTML sources, unchanged aggregate route/access counts,
  all three corrected caches passing isolated and full offline replay, and
  exactly fourteen credential-restricted gaps still deferred.
- [ ] Verify `git diff --check`, an empty index after commits, exact commit path
  scopes, protected user-file hashes, and absence of unapproved deletions or
  untracked cleanup.
- [ ] Dispatch a fresh spec-compliance reviewer and obtain explicit approval.
- [ ] Only after spec approval, dispatch a fresh code-quality/security reviewer
  and obtain explicit approval. Both reviewers use `gpt-5.6-sol` at `xhigh`
  reasoning and never Fast mode.
- [ ] Run both Task 5A.0 comparators immediately before and after each reviewer;
  require exact baseline equality plus only the three authorized new cache
  subtrees.
- [ ] Do not claim Task 5 source feasibility or final 155/155 while the fourteen
  credential-restricted sources remain absent.

## Task 6: Implement Runtime Source Parsers

**Files:** Create scripts/validation/literature_evidence_parsers.py and tests/test_literature_evidence_parsers.py.

- [ ] Write mutation-first RED tests for numeric, interval, sequence, set, equation, table, and typed categorical claims.
- [ ] Replace a valid numeric target and require parser output to change.
- [ ] Mutate subject, polarity, scope, conditions, qualifier, and uncertainty and require output change or fail-closed rejection.
- [ ] Add categorical RED cases for absence of mention, model-to-material inference, and review paraphrases presented as primary experimental evidence.
- [ ] Implement parsers returning source hash, exact coordinates/span, raw value, normalized value, typed claim fields, and parser code hash.
- [ ] Prohibit expected values as parser inputs.
- [ ] Validate first against one analytic equation, one table number, one DMRG/QMC range, and one direct experimental claim.
- [ ] Add every parser shape needed by the 155 records.
- [ ] Run: python -m pytest tests/test_literature_evidence_parsers.py -q
- [ ] Commit GREEN.

## Task 7: Implement Isolated Recalculation Adapters

**Files:** Create adapter/isolation modules and tests/test_literature_evidence_adapters.py; reuse pure benchmark helpers.

- [ ] Write a fail-closed capability preflight for user, network, and mount namespaces, read-only bind mounts, tmpfs, chroot, and strace. If any capability is absent, strict recomputation is unavailable rather than silently weakened.
- [ ] Write RED tests proving adapters run under unshare -Urnm inside a new allowlist-only root filesystem assembled in the private mount namespace, with an environment allowlist and strace access log.
- [ ] Attempt registry, evidence, source, report, environment-secret, and network access and require rejection.
- [ ] Reject expected outputs in parameters, forbidden registry/evidence imports, benchmark lookup tables, embedded registered outputs, and undeclared transitive dependencies.
- [ ] Hash adapter code and dependency closure before generating random audit inputs.
- [ ] Build the private root from read-only runtime/library/backend bind mounts plus one declared-input mount and one output mount; do not mount the project registry, evidence, sources, reports, or parent filesystem.
- [ ] Chroot into the private root, use an empty network namespace, and fail undeclared reads from the strace log.
- [ ] Record interpreter, packages, BLAS/LAPACK, TenPy, Julia, and backend versions when applicable.
- [ ] Generate unpredictable parameter points after code hashes are fixed.
- [ ] Check analytic adapters with independent algebra/invariants, ED with dense small-system and trace/symmetry oracles, GLT with direct Fourier-energy invariants, and iterative numerics with convergence bounds.
- [ ] Assert for each adapter that the independent oracle/invariant module is outside the adapter dependency closure.
- [ ] Wrap existing pure helpers. Remove status-label/candidate adapters; route those claims through source parsing unless a real calculation exists.
- [ ] Require typed observable identity, local result, units, uncertainty, convergence trace, and backend diagnostics.
- [ ] Require every local_recompute outcome, not only representative examples, to contain independently sourced parameter provenance, dependency-closure hashes, embedded-output scan, namespace/isolation preflight and runtime results, unpredictable counterfactual trace, and independent oracle/invariant result. Any absent field is strict no.
- [ ] Run: python -m pytest tests/test_literature_evidence_adapters.py -q
- [ ] Commit GREEN.

## Task 8: Replace The Whitelist Auditor

**Files:** Modify scripts/validation/literature_reproduction_audit.py and rewrite audit tests.

- [ ] Write RED integration tests for one real source parse and one real isolated recomputation.
- [ ] Add negative cases for missing source, empty payload, hash mismatch, source-ID/registry-URL disagreement, source mutation, selector mismatch, projection, backend exception, non-convergence, isolation violation, and comparison failure.
- [ ] Parameterize observable-identity RED cases so subject, system/material, Hamiltonian, parameter regime, finite-size/thermodynamic limit, observable definition, units, and conditions are each mutated independently and each yields strict no.
- [ ] Add end-to-end categorical rejection cases for absence of mention, model-to-material inference, and review paraphrase claimed as primary evidence.
- [ ] Implement pre-run bijection, offline source verification, extraction, independent registry selection, identity check, optional isolated adapter, convergence check, comparison, and trace emission.
- [ ] Remove LOCAL_RECOMPUTED_EVIDENCE, STRICT_LOCAL_KINDS, and prose from the authoritative verdict path.
- [ ] Mutate all legacy classification fields and prove outcomes do not change.
- [ ] Emit a canonical fresh manifest with source, registry, record, parser, adapter/dependency, backend, environment, trace, outcome, and report hashes, plus canonical executed-command records and audit/report start and end timestamps.
- [ ] Add tamper tests proving missing, reordered without canonical normalization, or altered command/timestamp records invalidate the manifest envelope.
- [ ] Run: python -m pytest tests/test_literature_reproduction_audit.py -q
- [ ] Commit GREEN.

## Task 8A: Pass The Required Production Evidence Matrix

**Files:** Use real production contracts, records, sources, parsers, adapters, comparators, and the production audit path.

- [ ] Add a parameterized integration test covering one real analytic recomputation, one real ED or GLT recomputation, one real DMRG or iterative numerical recomputation, one real paper-numeric source parse, and one real direct experimental-observable parse.
- [ ] Require all five examples to consume authoritative production payloads and canonical registry operands, not fixtures containing copied answers.
- [ ] Exercise every comparator kind used anywhere in the 155 provisional records.
- [ ] For the three recomputation classes, require the complete per-record independence bundle and convergence evidence.
- [ ] For both parse classes, require exact runtime source coordinates and source-mutation tests.
- [ ] Run the matrix test in RED before migrating those records and GREEN after implementing them.
- [ ] Do not begin bulk migration until the full production matrix and all comparator cases pass.

## Task 9: Create And Migrate All 155 Records

**Files:** Create exactly 155 JSON files under reference/literature-evidence/records.

- [ ] Generate provisional fail-closed shells with selectors and locators but no target values or verdicts.
- [ ] Confirm every provisional unresolved record reports no.
- [ ] Add one parameterized production test that discovers exactly the canonical 155 record files, executes every record through the same production audit function, and requires extraction and comparison traces plus mode-appropriate execution traces.
- [ ] Before each migration batch, select the batch IDs in the parameterized test and verify RED because those records are unresolved or lack required traces.
- [ ] Migrate exact/analytic entries: source-locate the cited equation/value, parse it, define explicit model inputs, and add an adapter plus counterfactual proof where appropriate.
- [ ] Migrate ED/GLT/LSW/classical entries: require matching observable identity and honest size/limit. Local triangles and representative points stay projection-only unless they are the registered observable.
- [ ] Migrate DMRG/QMC/phase-diagram entries: parse published claims unless the local backend reproduces the same limit; require size/bond-dimension/truncation scans for local numerics.
- [ ] Migrate material/experimental entries: parse primary-source observables with typed conditions and exact spans. Never describe these as freshly rerun experiments.
- [ ] After each batch, rerun the selected parameterized cases and verify GREEN, then rerun all 155 cases to expose remaining strict gaps.
- [ ] After each small group run: python scripts/validation/literature_reproduction_audit.py --manifest reports/literature_reproduction_manifest.json
- [ ] Inspect unresolved count: jq "[.outcomes[] | select(.strict_literature_match != true)] | length" reports/literature_reproduction_manifest.json
- [ ] Continue until unresolved is exactly zero; never change tests to bless an incomplete count.

## Task 10: Regenerate Traceable Markdown, CSV, And PDF

**Files:** Modify audit/report generators and PDF tests; regenerate report artifacts.

- [ ] Write RED consistency tests requiring manifest, CSV, Markdown, and PDF to contain the same 155 IDs and verdicts.
- [ ] Require each CSV, Markdown, and PDF detail row to show source retrieval provenance and hash, runtime locator and exact extracted excerpt, parsed operand, independent registry operand, machine-readable observable identity, evidence mode, executed parser and adapter, local operand when applicable, comparator/error, extraction trace, fresh-process execution trace, isolation/convergence status, strict verdict, and failure reason.
- [ ] Generate all reports only from the canonical manifest.
- [ ] Bind report artifact hashes into a finalized manifest envelope.
- [ ] Run: python reports/generate_literature_reproduction_audit_pdf.py
- [ ] Extract PDF text and verify 155 of 155 plus provenance and runtime fields.
- [ ] Run: python -m pytest tests/test_literature_reproduction_audit_pdf.py -q
- [ ] Commit GREEN.

## Task 11: Fresh Full Completion Audit

**Files:** Verify every artifact above and preserve unrelated files.

- [ ] Write tests/test_literature_reproduction_manifest_verifier.py before implementing the verifier.
- [ ] Create independently mutated fixture artifacts covering missing IDs, duplicate IDs, orphan IDs, registry/contract/record/outcome/report set mismatch, stale registry/source/record/adapter/report hash, missing or malformed environment information, missing or malformed applicable backend versions, missing command/timestamp, missing extraction or execution trace, malformed CSV/Markdown row, and missing or malformed PDF detail row.
- [ ] Run the verifier test and confirm RED because scripts/validation/verify_literature_reproduction_manifest.py does not exist.
- [ ] Implement scripts/validation/verify_literature_reproduction_manifest.py with independent readers for the registry, contracts, record filenames, source index/provisioning, manifest, CSV, Markdown, and pdftotext PDF detail IDs.
- [ ] Make the verifier require exact identifier-set equality, 155 unique entries everywhere, 137 unique verified source IDs/payloads, and no duplicates or orphans.
- [ ] Make the verifier inspect every outcome and report detail for retrieval provenance/hash, exact extraction coordinates and excerpt, parsed operand, independent registry operand, machine-readable observable identity, evidence mode, executed parser/adapter, extraction trace, fresh-process execution trace, comparator/error, strict yes, and no unresolved state.
- [ ] Make the verifier validate canonical executed-command records and monotonic audit/report start/end timestamps.
- [ ] Make the verifier validate the registry hash, complete environment information, and backend name/version/code hash for every applicable outcome; missing or malformed values invalidate check-all.
- [ ] For every local_source_parse outcome require two independently populated operands and a source-mutation parser test reference.
- [ ] For every local_recompute outcome require parameter provenance, adapter/dependency hashes, embedded-output scan, mount/network/file-access isolation results, unpredictable counterfactual trace, independent oracle outside the dependency closure, convergence evidence, local operand, and uncertainty.
- [ ] Run python -m pytest tests/test_literature_reproduction_manifest_verifier.py -q and confirm GREEN before using the verifier as a completion gate.
- [ ] Remove stale generated state:

    rm -f reports/literature_reproduction_manifest.json
    rm -f reports/literature_reproduction_audit.csv
    rm -f reports/literature_reproduction_audit.md
    rm -f reports/literature_reproduction_audit.pdf
    rm -f reports/remaining_strict_reproduction_gaps.md

- [ ] Run the source feasibility gate:

    python scripts/validation/fetch_literature_evidence_sources.py --verify-offline --all --require-target-locators

- [ ] Run the fresh offline audit and generate text reports:

    LD_LIBRARY_PATH=/data/home/zhli/anaconda3/lib:$LD_LIBRARY_PATH python scripts/validation/literature_reproduction_audit.py --offline --fresh --manifest reports/literature_reproduction_manifest.json --write-reports

- [ ] Generate the PDF from that exact manifest:

    python reports/generate_literature_reproduction_audit_pdf.py --manifest reports/literature_reproduction_manifest.json

- [ ] Finalize report hashes into the manifest envelope:

    python scripts/validation/verify_literature_reproduction_manifest.py --manifest reports/literature_reproduction_manifest.json --finalize-report-hashes

- [ ] Run the independent all-artifact verifier:

    python scripts/validation/verify_literature_reproduction_manifest.py --manifest reports/literature_reproduction_manifest.json --check-all --require-count 155 --require-source-count 137

- [ ] Independently require 155 unique outcomes and zero non-true verdicts:

    jq -e '(.outcomes | length) == 155 and ([.outcomes[].benchmark_name] | unique | length) == 155 and ([.outcomes[] | select(.strict_literature_match != true)] | length) == 0' reports/literature_reproduction_manifest.json

- [ ] Inspect PDF text and require aggregate, provenance, and per-entry detail:

    pdftotext reports/literature_reproduction_audit.pdf reports/literature_reproduction_audit.txt
    rg '155 of 155|strict_literature_match|source_sha256|parsed_source_operand|registry_operand|adapter' reports/literature_reproduction_audit.txt

- [ ] Run the complete project suite:

    LD_LIBRARY_PATH=/data/home/zhli/anaconda3/lib:$LD_LIBRARY_PATH python -m pytest -q

- [ ] Require zero failures and review warnings for relevance.
- [ ] Rerun the independent verifier after pytest to prove no source, record, manifest, or report artifact changed.
- [ ] Review git status and preserve unrelated pre-existing changes, especially scripts/classical/certified_glt/universal_anytime.py.
- [ ] Only after every requirement is proven, mark the persistent goal complete.
- [ ] In the final statement distinguish local recomputation from direct published-observable parsing and do not claim experiments were rerun.
