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
  sources/<source-id>/provenance.json
  sources/<source-id>/payload.<media-extension>
  records/<benchmark-name>.json
```

### Source snapshot

Each unique cited source preserves raw authoritative bytes plus a provenance
record containing:

- canonical source identifier and DOI/arXiv URL;
- retrieval URL, retrieval date, media type, retrieval method, HTTP response
  metadata, and an immutable DOI/arXiv/repository artifact identifier;
- source title, authors, venue, and publication date;
- the raw official abstract response, openly available publisher/repository full
  text, or author manuscript artifact needed for the observable;
- SHA-256 and byte length of the raw retrieved payload consumed by parsers;
- license/access notes and a citation-metadata verification result.

SHA-256 establishes integrity, not authenticity. The acquisition command must
retrieve the payload from an authoritative publisher, DOI target, arXiv, or
institutional/author repository and preserve enough response metadata to audit
that origin. Manually authored source payloads are rejected. A bounded excerpt
is acceptable only when its exact bytes and coordinates are verified against a
hashed authoritative parent artifact.

The repository must not claim that Crossref title/author metadata establishes a
scientific observable. A snapshot is sufficient only when its authoritative
payload contains the actual target statement. If the cited source is
inaccessible, the entry stays `source_unavailable` until an authoritative
snapshot is supplied.

### Benchmark evidence record

Each of the 155 benchmarks has one record with these required fields:

```json
{
  "schema_version": 1,
  "benchmark_name": "...",
  "evidence_mode": "recompute_or_parse",
  "source_id": "...",
  "source_sha256": "...",
  "registry_selector": {"path": ["energy_per_site"]},
  "canonical_observable_id": "...",
  "target_locator": {"kind": "equation", "value": "Eq. (3)"},
  "target_parser": "module:function",
  "normalization": {
    "kind": "typed_claim_map",
    "field_rules": {},
    "negation_rule": "...",
    "qualifier_rules": []
  },
  "adapter": "module:function",
  "adapter_parameters": {},
  "convergence": {},
  "comparison": {"kind": "absolute", "tolerance": 1e-6}
}
```

The record may declare where and how to parse, but it may not supply
`target_excerpt` or `target_observable` as parser output. The exact source span,
raw extracted value, normalized literature target, and byte/page/table
coordinates are derived at runtime from the hashed payload and written only to
the run result.

The canonical observable identity is not declared by the evidence record. It
lives in an independently maintained benchmark specification associated with
the registry entry and contains subject, system/material, Hamiltonian,
parameter regime, size or thermodynamic limit, observable definition, units,
and conditions. The evidence record may only reference its immutable identifier.
The auditor compares the record reference, parsed literature claim, registry
value, and adapter output against that canonical specification field by field.

`evidence_mode` is one of:

- `local_recompute`: parse a literature target, execute an independent local
  calculation, and compare the two;
- `local_source_parse`: parse a direct published target and compare it with the
  independently declared registry observable;
- `projection_only`: preserve a useful smaller-model calculation without
  granting strict status.

Categorical and experimental observables use a machine-readable typed claim
schema containing
subject, observable, experimental or model conditions, scope, polarity,
uncertainty, and an executable normalization map. Every mapped component is
extracted at runtime from exact source spans. Executable rules handle negation,
qualifiers, scope, and uncertainty. Boolean values are accepted only when exact
source spans directly entail the normalized claim. The auditor rejects
absence-of-mention, model-to-material inference, review paraphrases when primary
evidence is claimed, and source conditions that do not match the registry
contract.

## Runtime Architecture

### Source loader

A focused module loads snapshots, recomputes SHA-256, validates provenance, and
returns source text. It rejects missing files, hash mismatches, empty payloads,
source identifiers that disagree with the registry URL, non-authoritative
origins, and excerpts that cannot be located in their hashed parent payload.

### Literature target parser

Each evidence record declares a parser or a constrained locator. The parser
must resolve the locator to exact bytes, pages, table cells, or structured fields
in the snapshot and derive both the excerpt and target from those bytes at
runtime. Tests must demonstrate both that removing the target makes extraction
fail and that replacing it with another syntactically valid target makes the
parser return the replacement rather than a hard-coded value.

### Reproduction adapter

Each recomputation adapter accepts explicit parameters and returns a structured
observable. Adapters may wrap existing benchmark helpers, but they must not read
`LITERATURE_STANDARD_RESULTS` or the evidence record's target value while
calculating the local result. `adapter_parameters` contain only model inputs and
may not contain expected outputs. Model parameters used for recomputation are
independently parsed from the literature source or declared as universal test
inputs distinct from the target observable.

The adapter runs in a restricted fresh process whose readable inputs are limited
to declared model parameters and approved backend resources. Registry, evidence,
source, previous-output, and report artifacts are not mounted or readable in
that process. The run manifest records an auditable dependency closure and
hashes adapter source code and all transitive project helpers. Static inspection
rejects embedded benchmark outputs and benchmark-specific lookup tables in that
closure; runtime information-flow checks reject undeclared file, environment,
network, or import access.

At audit time, the runner generates unpredictable counterfactual model inputs
after the adapter code hash is fixed. Results are checked by an independent
oracle or mathematical invariant that is not in the adapter dependency closure.
This supplements ordinary fixed regression cases and prevents a constant or
finite benchmark lookup table hidden in an adapter or helper from establishing
independence. If a backend cannot provide this independence proof, the entry
does not receive strict recomputation status and must use a direct source-parse
route instead.

Before comparing values, the auditor verifies that adapter output has the same
machine-readable observable identity as the independent canonical benchmark
specification: subject,
system/material, Hamiltonian, parameter regime, size or thermodynamic limit,
observable definition, units, and conditions. A smaller cluster, clean limit,
representative parameter point, or different material cannot pass solely
because its numerical label resembles the literature claim.

### Comparator

The comparator supports exact, absolute-tolerance, relative-tolerance,
interval, set, sequence, and normalized categorical comparisons. It records
both operands and the computed error or mismatch reason.

Numerical records declare a convergence protocol appropriate to their backend:
deterministic seeds where applicable, size/bond-dimension/truncation scans,
stopping thresholds, finite-size or truncation error estimates, backend version
and code hash, and a fail-closed bound showing total numerical uncertainty is
compatible with the comparison tolerance. A numerically close but unconverged
run is not strict evidence.

### Auditor

For every registered entry, the auditor performs the following in order:

1. perform a pre-run set-equality check between canonical registry names and
   evidence-record names;
2. require exactly one evidence record;
3. verify source identity and snapshot hash;
4. extract the literature target from source content;
5. resolve the independent canonical observable specification and verify the
   parsed claim field by field;
6. independently select the registry operand using `registry_selector` and
   compare it with the runtime-parsed source operand;
7. for `local_recompute`, execute the independent adapter in a restricted fresh
   process;
8. verify independence, convergence, and observable-identity equality;
9. compare the local result with the independently parsed literature target;
10. emit a structured pass/fail result, extraction trace, execution trace, and
   all provenance fields.

Any exception, unavailable backend, missing source, missing adapter, stale
hash, unsupported comparator, target mismatch, or projection-only route yields
`strict_literature_match=no` with a concrete reason. There is no strict-kind
promotion whitelist. Cached verdicts and precomputed pass labels are ignored.

After running entries and generating reports, the auditor performs a separate
post-run set-equality check among canonical registry names, outcome names, and
every report's row names. Either the pre-run or post-run bijection check failing
invalidates the entire audit. Duplicates, missing records, and orphaned records
are never reduced to a warning.

## Migration Strategy

Migration is deliberately honest and incremental:

1. Introduce the source/record schemas, loader, comparator, and fail-closed
   auditor while retaining the current report columns where practical.
2. Convert the current 155 prose assertions into provisional records. Until a
   record has a real snapshot and executable adapter/parser, it reports `no`.
3. Populate and verify the 137 unique source snapshots.
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
- runtime-resolved source coordinates, exact excerpt, and parsed literature
  value;
- machine-readable observable identity and registry selector;
- evidence mode and executed adapter;
- local result, comparator, tolerance, and numerical error;
- extraction, adapter, convergence, and fresh-process execution traces;
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
- source target is replaced with another valid value but the parser does not
  return the replacement;
- categorical source mutations change polarity, subject, scope, conditions,
  qualifiers, or uncertainty but the parser/normalizer does not reflect or
  reject the change;
- declared excerpt differs from bytes selected from the hashed parent artifact;
- manually authored or non-authoritative source payload;
- adapter reads the registry or literature target as its result;
- restricted adapter process can read registry, evidence, source, output, or
  report artifacts, use undeclared network/environment inputs, or load an
  undeclared dependency;
- expected output is smuggled through adapter parameters or a transitive helper;
- adapter fails counterfactual parameter/property tests;
- local projection presented for a paper-level/material observable;
- subject, Hamiltonian, parameter regime, limit, units, or conditions differ
  from the registered observable identity;
- backend exception or non-convergence;
- numerical result outside tolerance;
- duplicate, orphaned, and stale evidence records.

Required positive tests cover each comparator and at least one real analytic,
ED/GLT, DMRG/numerical, paper-numeric parse, and direct experimental-observable
parse before batch migration begins.

For every migrated entry, the test suite must execute the same record consumed
by the production audit. Tests may not independently hard-code a second pass
classification. Acceptance runs in fresh processes, lists the parser and adapter
invoked for every benchmark, and fails if any record lacks a runtime extraction
trace, comparison trace, or mode-appropriate execution trace.

## Acceptance Criteria

The goal is complete only when a fresh run proves all of the following:

- the canonical registry, evidence records, runtime outcomes, CSV rows,
  Markdown rows, and PDF detail rows contain exactly the same set of 155
  distinct benchmark identifiers;
- every record consumes a verified local source snapshot containing the target
  observable;
- every `local_recompute` adapter executes without reading its expected answer;
- every `local_recompute` result matches the independently parsed literature
  target under an explicit comparator;
- every `local_source_parse` result records two independently obtained operands,
  the runtime-parsed source value and the canonical-registry-selected value,
  and compares them without either operand being populated from the other or
  from the evidence record;
- every strict recomputation includes a complete dependency closure,
  information-flow isolation result, static embedded-output scan, unpredictable
  counterfactual trace, and independent-oracle/invariant result;
- the run manifest contains 155 distinct `strict_literature_match=yes`
  outcomes and zero failures, skips, duplicates, or orphans;
- no entry is `projection_only`, `source_unavailable`, `backend_unavailable`, or
  otherwise unresolved;
- the generated CSV, Markdown, and PDF agree on the per-entry and aggregate
  results;
- the full project test suite passes after the audit run;
- a machine-readable run manifest records commands, environment information,
  source hashes, registry/record hashes, adapter and transitive dependency
  hashes, backend versions, extraction and execution traces, timestamps, all
  155 outcomes, and hashes of generated report artifacts.

Passing pytest alone is not completion. A `155/155` summary alone is not
completion. The per-entry runtime evidence and source provenance are the
authoritative proof.

## Controlled Acquisition-Route Amendment (2026-08-02)

This section supersedes the generic acquisition details above for the three
exact DOI identities named below. It also records the implemented inventory
cardinality of 137 unique canonical sources for 155 benchmarks. The amendment
does not weaken any generic source, redirect, stylesheet, DOI, provenance, or
offline-verification rule.

### Amendment-wide invariants

- Route exceptions are closed by exact canonical DOI and never selected by
  hostname, publisher, media type, or a partial DOI prefix.
- The online fetcher validates candidate bytes and all identity sidecars before
  atomically creating a previously absent cache directory. A failed candidate
  never replaces or mutates an existing cache.
- Every identity sidecar is retained as the exact raw response bytes consumed
  by validation, with its own SHA-256, byte length, media type, relative path,
  and query-free, userinfo-free provenance URL.
- Request and redirect query values may be constructed and used in memory only.
  They never enter command output, logs, outcomes, provenance, or serialized
  route inventories.
- Offline verification revalidates the raw primary payload and every raw
  sidecar from their stored hashes; it does not trust fields copied into main
  provenance when the corresponding raw sidecar disagrees.
- Bibliographic author matching preserves exact author order and cardinality.
  A source-specific normalizer may equate presentation forms only by the tuple
  `(casefolded family name, ordered casefolded initials)`. Missing, extra,
  duplicated, reordered, ambiguous, or colliding authors fail closed.
- The 30 unattended cache directories already acquired during this task and all
  cache paths that predated the task remain byte-for-byte and metadata-for-
  metadata unchanged.

### Garel-Maillard: HAL identity sidecar plus author PDF

Canonical source identity and primary payload remain unchanged:

```text
doi:10.1088/0305-4470/16/10/023
source_id: doi_dba239926d673e54f80a
route kind: author_repository_pdf
payload: https://www.lptmc.jussieu.fr/files/maillard/PUB2/Frustrated_jav16i10p2257.pdf
media: application/pdf
access: unattended
artifact: author-repository:Frustrated_jav16i10p2257.pdf
```

The former `author_publications_same_work` HTML sidecar is not admissible for
this source. The live page imports unpinned stylesheets and does not expose one
visible record containing the canonical DOI, complete ordered authorship, exact
title, and exact PDF link. Generic CSS validation must not be relaxed to make
that page pass.

The replacement evidence kind is
`hal_same_work_bibliographic_payload`. The configured official API base is
`https://api.archives-ouvertes.fr/search/`; the fixed record identifier is
`hal-02340631v1`; and the stable public document URL is
`https://hal.science/hal-02340631v1`. The fetcher constructs the exact HAL query
and fixed field projection only in memory and stores the returned bytes as
`work-identity.json`.

The HAL validator requires a strict duplicate-key-free JSON document with
exactly one result and all of the following values:

- `docid = "2340631"`, `halId_s = "hal-02340631"`, `version_i = 1`, and
  `uri_s = "https://hal.science/hal-02340631v1"`;
- DOI `10.1088/0305-4470/16/10/023`;
- title `Study of a two-dimensional fully frustrated model`;
- exactly two ordered authors, T. Garel followed by J.-M. Maillard;
- journal identity, volume 16, issue 10, pages 2257-2265, and publication year
  1983;
- ISTEX document identifier
  `315C04C1B2CFE6FA0DE1A3BAA04E06FA586E5893` in the exact external link.

The raw HAL record must agree field by field with the Crossref-derived
bibliographic metadata used for the main provenance. The extracted author PDF
must independently contain the exact title, ordered authors, journal, volume,
pages, and year. The PDF is allowed to omit the DOI only for this exact route
and only when both the HAL identity validation and the PDF bibliographic
fingerprint succeed. Scientific target anchors cannot substitute for this
identity proof.

### Caspers-Emmett-Magnus: current CORE download route

Canonical source identity, source ID, primary media, access mode, artifact ID,
and CORE identity sidecar remain unchanged. The sole primary-route correction
is:

```text
old: https://files01.core.ac.uk/download/pdf/572184419.pdf
new: https://core.ac.uk/download/572184419.pdf
```

The route-specific redirect policy permits only this exact sequence of
origin/path pairs:

1. `core.ac.uk/download/572184419.pdf`;
2. `fileserver-az.core.ac.uk/download/572184419.pdf`;
3. `pdf.core.ac.uk/corefilesystem/pdf/363/572184419.pdf`.

The final CORE filesystem request may contain a server-issued signed query, but
the query is memory-only and is stripped from every serialized or displayed
URL. A redirect to any other origin or path, a userinfo URL, a fragment, an
earlier-hop query, a credential-bearing request, or more than these two
redirects fails before the unsafe request is issued.

Before accepting PDF bytes, the fetcher validates the raw official
`https://api.core.ac.uk/v3/outputs/572184419` JSON sidecar. It requires output
ID 572184419, the exact canonical DOI and title, a full-text download state,
the exact current download URL, and the exact ordered author tuples. CORE's
`Caspers, W.J.` and Crossref/PDF `W J Caspers` are representationally equal
under the amendment-wide tuple rule; no broader fuzzy author matching is
permitted.

### Husimi-Syozi: correct DOI and OUP identity contract

`10.1143/ptp.5.2.177` is an unregistered hybrid identifier and must not remain
as a canonical source. The canonical replacement is:

```text
canonical identity: doi:10.1143/ptp/5.2.177
canonical URL: https://doi.org/10.1143/ptp/5.2.177
source_id: doi_457c49167653440059e9
cache target: source-cache/doi_457c49167653440059e9/source.html
```

Both Husimi-Syozi benchmark registry URLs, source-index identity, provisioning,
locator rows, and provisional records use the slash-form DOI and new source ID.
The old absent cache path is removed from the expected manifest without any
filesystem deletion.

The primary route remains `oup_minimal_html` at
`https://oup.silverchair-cdn.com/article-minimal/1942776`, with media type
`text/html`, unattended access, publisher origin, and artifact identifier
`oup-silverchair-article-minimal:1942776`.

The mandatory identity evidence kind is `crossref_oup_same_work` at the exact
query-free Crossref Works URL
`https://api.crossref.org/works/10.1143%2Fptp%2F5.2.177`. The fetcher retrieves
that record once, derives bibliographic metadata from those exact bytes, and
stores the same bytes as `work-identity.json`. The validator requires a
successful Crossref work response; the exact slash-form DOI; exact title;
exactly two ordered authors Kodi Husimi and Itiro Syozi by family/initial tuple;
OUP publisher and member 286; type `journal-article`; volume 5; issue 2; pages
177-186; and the exact OUP primary-resource origin/path. Conflicting identity
fields fail closed.

The primary HTML validator identifies one visible minimal-article container and
one complete visible article-header citation record. That record must contain
the exact title, both full author names, slash-form DOI, volume, issue, March
1950, and pages, while the visible article body must contain `Summary` and both
target equations. Exactly one DOI is allowed in the article identity record,
and it must be the canonical DOI. DOI values inside the structurally identified
reference list are cited-work identifiers and do not count as article identity;
any additional DOI carrier outside that reference list causes rejection.
Hidden, script/style/comment-only, malformed, query-bearing, attribute-only, or
conflicting DOI carriers cannot satisfy identity.

The pinned inline stylesheet requires HTML extraction descriptor version 2.
Version 2 adds only one simple parent/ancestor selector followed by exactly one
child (`>`) or descendant (whitespace) combinator and one simple target
selector. A simple selector remains limited to one supported tag, class, or ID
form. Matching uses the parser's actual ancestor stack and propagates hiding to
descendants. Multiple combinators, sibling combinators, attributes, pseudos,
universal or namespace selectors, escapes, malformed blocks/comments,
unsupported values/functions, at-rules, external stylesheets, or size/rule
limit violations remain fail closed.

### Static topology and restricted sources

The correction preserves 137 canonical sources, 155 locators, 134 PDF sources,
2 XML sources, 1 HTML source, and all route/access aggregate counts. Static
regeneration may change only `source-index.json`, `source-provisioning.json`,
`locator-inventory.json`, and the two Husimi-Syozi record files already named in
the approved implementation boundary. `canonical-observables.json` is
unchanged.

Fourteen credential-restricted cache gaps remain explicitly unavailable until
the user supplies a pre-existing external credential file. The agent never
creates, edits, copies, moves, deletes, or changes permissions on that file. It
must be a regular non-symlink file outside the repository and cache, owned by
the user, mode 0600, and valid under the existing credential schema. Deferring
those sources never permits a 155/155 completion claim.

### Amendment acceptance criteria

- Mutation-first tests demonstrate RED before each production behavior is
  implemented and GREEN afterward.
- All pre-amendment source/inventory/crosscheck tests remain green except tests
  deliberately inverted because they encoded the invalid DOI or stale route.
- Regeneration occurs in a temporary root and an exact semantic/path diff proves
  that no unauthorized static file changed.
- Each of the three new cache candidates passes online response, media,
  identity-sidecar, bibliographic, payload, provenance, hash, and target-anchor
  checks before installation, followed by fresh offline replay from stored
  bytes.
- The six protected user-owned report artifacts retain their entry hashes, the
  git index contains no unrelated path, and every pre-existing cache path
  retains its entry type, mode, byte length, and content hash.
- Independent spec-compliance and code-quality reviews approve the amendment
  before the controlled acquisition-route work is considered complete.
