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
- [ ] Generate source-index.json and assert exactly 133 unique canonical DOI/arXiv sources covering all 155 records.
- [ ] Generate source-provisioning.json with authoritative retrieval route, expected media type, redistributability, local cache location, and current availability for all 133 sources.
- [ ] Build a 155-row locator inventory before fetching: each row states the expected source section/equation/table/abstract/figure-caption class and target representation without supplying the target answer.
- [ ] Confirm every provisional record fails closed as unresolved.
- [ ] Commit the complete provisional inventory before adding any strict passes.

## Task 5: Acquire And Verify 133 Authoritative Sources

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
- [ ] Run an early feasibility gate proving all 133 source payloads are locally present and every one of 155 locator inventories resolves to target-bearing source content.
- [ ] Verify: python scripts/validation/fetch_literature_evidence_sources.py --verify-offline --all
- [ ] Final source gate: 133/133 authoritative payloads verified; 155/155 target locators resolve; zero metadata-only, blocked, failed, unavailable, or unhashed artifacts.
- [ ] Commit redistributable payloads plus the complete provisioning manifest. Never represent an unprovisioned restricted source as portable or passing.

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
- [ ] Make the verifier require exact identifier-set equality, 155 unique entries everywhere, 133 unique verified source IDs/payloads, and no duplicates or orphans.
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

    python scripts/validation/verify_literature_reproduction_manifest.py --manifest reports/literature_reproduction_manifest.json --check-all --require-count 155 --require-source-count 133

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
