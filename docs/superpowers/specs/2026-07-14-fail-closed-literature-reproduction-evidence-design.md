# Fail-Closed Literature Reproduction Evidence Design

## Goal

Replace the current whitelist-and-prose literature audit with an executable,
fail-closed audit that can prove, for every one of the 155 registered benchmark
entries, both of the following:

1. the target observable was obtained from a traceable literature source; and
2. a local calculation or a local source parser reproduced the registered
   observable and passed an explicit comparison.

The final `155/155` result is valid only when all 155 evidence records satisfy
the contract below during a fresh audit run.

## Problem In The Current Audit

The current audit cannot prove the goal:

- `LOCAL_RECOMPUTED_EVIDENCE` stores prose assertions rather than execution
  results.
- `STRICT_LOCAL_KINDS` promotes an entry solely because its manually assigned
  kind appears in a whitelist.
- weak local limits can be promoted before weak-evidence markers are checked.
- published-result parsers can be hard-coded functions that do not consume a
  saved source snapshot.
- the registry value is often used as both expected value and comparison
  oracle, so tests can establish internal consistency without establishing a
  match to the cited paper.

The replacement must make missing, stale, malformed, or circular evidence fail
closed.

## Definitions

### Literature target

A value or categorical statement extracted from a cited source snapshot. A
source URL or bibliographic record alone is not a literature target. The
evidence must identify the exact source text, table, equation, figure caption,
or machine-readable field from which the target was obtained.

### Local recomputation

An executable local adapter independently calculates the registered observable
from explicit model parameters. Examples include an analytic formula, exact
enumeration, exact diagonalization, transfer-matrix calculation, GLT/Fourier
calculation, DMRG, or another declared numerical backend.

The adapter must return values, units/conventions, and numerical diagnostics.
Calling a helper that merely returns the registered value, a stored status
label, or a candidate model property is not a recomputation.

### Local source parse

An executable parser reads a saved source snapshot, extracts a direct published
observable, normalizes it to the registry convention, and compares it with the
registered result. A prose string embedded in Python source is not a source
parse.

Source parsing is the expected route for direct experimental observations and
for paper-level numerical or categorical claims whose original calculation is
not reasonably rerun locally. It is not described as rerunning an experiment.

### Projection only

A calculation of a smaller model, material context, candidate order, exchange
sign, local constraint, or representative parameter point that does not
calculate or parse the registered observable. Projection evidence remains
useful but cannot receive a strict literature-match verdict.

## Evidence Artifacts

Artifacts live below:

```text
translation-invariant-spin-model-simplifier/reference/literature-evidence/
  sources/<source-id>.json
  records/<benchmark-name>.json
```

### Source snapshot

Each unique cited source has a JSON snapshot containing:

- canonical source identifier and DOI/arXiv URL;
- retrieval URL, retrieval date, media type, and retrieval method;
- source title, authors, venue, and publication date;
- the official abstract, openly available full text, author manuscript text,
  or a bounded exact excerpt needed for the observable;
- SHA-256 of the exact payload consumed by parsers;
- license/access notes and a citation-metadata verification result.

The repository must not claim that Crossref title/author metadata establishes a
scientific observable. A snapshot is sufficient only when its payload contains
the actual target statement. If the cited source is inaccessible, the entry
stays `source_unavailable` until an authoritative snapshot is supplied.

### Benchmark evidence record

Each of the 155 benchmarks has one record with these required fields:

```json
{
  "schema_version": 1,
  "benchmark_name": "...",
  "evidence_mode": "recompute_or_parse",
  "source_id": "...",
  "source_sha256": "...",
  "target_locator": {"kind": "equation", "value": "Eq. (3)"},
  "target_excerpt": "...",
  "target_observable": {"name": "...", "value": 0.0, "units": "..."},
  "normalization": {"description": "..."},
  "adapter": "module:function",
  "adapter_parameters": {},
  "comparison": {"kind": "absolute", "tolerance": 1e-6}
}
```

`evidence_mode` is one of:

- `local_recompute`: parse a literature target, execute an independent local
  calculation, and compare the two;
- `local_source_parse`: parse a direct published target and compare it with the
  independently declared registry observable;
- `projection_only`: preserve a useful smaller-model calculation without
  granting strict status.

Categorical observables use an explicit normalization map. Boolean values are
accepted only when the source excerpt directly supports the normalized claim;
material properties cannot be inferred merely from the model family.

## Runtime Architecture

### Source loader

A focused module loads snapshots, recomputes SHA-256, validates provenance, and
returns source text. It rejects missing files, hash mismatches, empty payloads,
and source identifiers that disagree with the registry URL.

### Literature target parser

Each evidence record declares a parser or a constrained locator. The parser
must extract the target from snapshot text at runtime. Tests must demonstrate
that changing or removing the source text makes extraction fail.

### Reproduction adapter

Each recomputation adapter accepts explicit parameters and returns a structured
observable. Adapters may wrap existing benchmark helpers, but they must not read
`LITERATURE_STANDARD_RESULTS` or the evidence record's target value while
calculating the local result.

### Comparator

The comparator supports exact, absolute-tolerance, relative-tolerance,
interval, set, sequence, and normalized categorical comparisons. It records
both operands and the computed error or mismatch reason.

### Auditor

For every registered entry, the auditor performs the following in order:

1. require exactly one evidence record;
2. verify source identity and snapshot hash;
3. extract the literature target from source content;
4. verify the target agrees with the registry representation;
5. for `local_recompute`, execute the independent adapter;
6. compare the local result with the literature target;
7. emit a structured pass/fail result and all provenance fields.

Any exception, unavailable backend, missing source, missing adapter, stale
hash, unsupported comparator, target mismatch, or projection-only route yields
`strict_literature_match=no` with a concrete reason. There is no strict-kind
promotion whitelist.

## Migration Strategy

Migration is deliberately honest and incremental:

1. Introduce the source/record schemas, loader, comparator, and fail-closed
   auditor while retaining the current report columns where practical.
2. Convert the current 155 prose assertions into provisional records. Until a
   record has a real snapshot and executable adapter/parser, it reports `no`.
3. Populate and verify the 133 unique source snapshots.
4. Upgrade exact and analytic entries with independent adapters.
5. Upgrade ED, GLT, DMRG, and other numerical entries with deterministic
   adapters and recorded convergence/finite-size diagnostics.
6. Upgrade paper-numeric and experimental entries with source parsers.
7. Leave genuinely smaller-model checks as `projection_only` until the direct
   registered observable is parsed or recomputed.

Entries are upgraded in batches, but completion is not claimed until a fresh
full audit reports all 155 strict passes.

## Reports

The CSV, Markdown, and PDF reports must show, per entry:

- source identifier, retrieval provenance, and snapshot hash;
- target excerpt locator and parsed literature value;
- evidence mode and executed adapter;
- local result, comparator, tolerance, and numerical error;
- strict verdict and failure reason.

Summary counts are derived only from runtime evidence results. Report
generators cannot override or promote verdicts.

## Testing

Implementation follows test-driven development.

Required negative tests cover:

- no evidence record;
- no source snapshot;
- source hash mismatch;
- source text no longer contains the target;
- parser returns a hard-coded value without consuming source content;
- adapter reads the registry or literature target as its result;
- local projection presented for a paper-level/material observable;
- backend exception or non-convergence;
- numerical result outside tolerance;
- duplicate, orphaned, and stale evidence records.

Required positive tests cover each comparator and at least one real analytic,
ED/GLT, DMRG/numerical, paper-numeric parse, and direct experimental-observable
parse before batch migration begins.

For every migrated entry, the test suite must execute the same record consumed
by the production audit. Tests may not independently hard-code a second pass
classification.

## Acceptance Criteria

The goal is complete only when a fresh run proves all of the following:

- exactly 155 registry entries and exactly 155 evidence records exist;
- every record consumes a verified local source snapshot containing the target
  observable;
- every `local_recompute` adapter executes without reading its expected answer;
- every local result or direct source parse matches its literature target under
  an explicit comparator;
- no entry is `projection_only`, `source_unavailable`, `backend_unavailable`, or
  otherwise unresolved;
- the generated CSV, Markdown, and PDF agree on the per-entry and aggregate
  results;
- the full project test suite passes after the audit run;
- a machine-readable run manifest records commands, environment information,
  source hashes, adapter versions, timestamps, and all 155 outcomes.

Passing pytest alone is not completion. A `155/155` summary alone is not
completion. The per-entry runtime evidence and source provenance are the
authoritative proof.
