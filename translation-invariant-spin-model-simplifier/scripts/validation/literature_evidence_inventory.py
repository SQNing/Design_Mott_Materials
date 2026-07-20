"""Load, validate, and generate the fail-closed literature evidence inventory."""

import ast
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from urllib.parse import urlparse

from validation.literature_evidence_schema import (
    CanonicalObservable,
    EvidenceSchemaError,
    ProvisionalEvidenceRecord,
)
from validation.literature_evidence_sources import authoritative_route_for_identity


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_ROOT = PROJECT_ROOT / "reference" / "literature-evidence"

_IGNORED_REGISTRY_OPERANDS = frozenset({"computable_observables", "tolerance"})
_GENERIC_OBSERVABLES = frozenset(
    {
        "material_reference",
        "material_model_reference",
        "phase_diagram_reference",
        "phase_reference",
        "status",
    }
)
_GENERIC_OBSERVABLE_SUFFIX_RE = re.compile(
    r"(?:^|_)(?:reference|candidate|status|claim)$"
)
_FORBIDDEN_GENERIC_REPRESENTATIONS = frozenset(
    {
        "field_dependent_sequence",
        "scalar_or_structured_claim",
        "dimensionless_sequence",
        "dimensionless_observable",
        "ordered_values_under_declared_convention",
        "scalar_under_declared_hamiltonian_convention",
    }
)
_LOCATOR_CLASS_OVERRIDES = {
    "honeycomb_kitaev_gamma_phase_diagram_reference": "figure_caption",
    "ni_ps3_honeycomb_antiferromagnet_reference": "abstract",
    "square_spin_half_heisenberg_qmc_energy": "body_text",
}
_SIZE_LIMIT_PHYSICAL_REGIMES = {
    "thermodynamic_limit": (
        "bulk or thermodynamic-limit behavior under the declared Hamiltonian parameters"
    ),
    "exact_model_limit": "exactly specified solvable or enumerable model limit",
    "finite_local_cluster": "finite local cluster defined by the Hamiltonian and lattice",
    "published_experimental_material_conditions_pending_source_verification": (
        "published material conditions, to be resolved exactly from the authoritative source"
    ),
}
_SOURCE_CLAIM_SCOPES = frozenset(
    {
        "direct published material or experimental observable",
        "published analytic relation or formula",
        "published exact model result",
        "published numerical or categorical model result",
    }
)
_PLACEHOLDER_TEXT = frozenset(
    {"generic", "unknown", "unspecified", "placeholder", "tbd", "n/a"}
)
_ALLOWED_LOCATOR_CLASSES = frozenset(
    {
        "equation",
        "table",
        "abstract",
        "body_text",
        "figure_caption",
        "supplemental",
        "metadata_field",
    }
)
_FORBIDDEN_INVENTORY_KEYS = frozenset(
    {
        "answer",
        "copied_target",
        "expected_value",
        "parsed_target",
        "pass",
        "source_excerpt",
        "source_sha256",
        "strict",
        "strict_literature_match",
        "strict_match",
        "target_excerpt",
        "target_observable",
        "value",
        "verdict",
    }
)
_FORBIDDEN_ARTIFACT_KEYS = _FORBIDDEN_INVENTORY_KEYS - {"value"}
_DOI_HOSTS = frozenset({"doi.org", "dx.doi.org"})
_ARXIV_ID_RE = re.compile(
    r"^(?:[a-z-]+(?:\.[A-Z]{2})?/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?$",
    re.IGNORECASE,
)
_MATERIAL_OBSERVABLE_MARKERS = (
    "material",
    "neutron_scattering",
    "exchange_parameter_reference",
    "quantum_spin_ice_reference",
    "frustrated_garnet_reference",
    "low_temperature_correlations",
    "ising_like_order",
    "classical_spiral_pitch",
    "helical_wavevector",
    "skyrmion_lattice_phase",
    "quantum_tunneling_reference",
)
_MATERIAL_BENCHMARK_PREFIXES = (
    "alpha_rucl3_",
    "beta_li2iro3_",
    "gamma_li2iro3_",
    "dy2ti2o7_",
    "er2ti2o7_",
    "ho2ti2o7_",
    "ni_ps3_",
    "yb2ti2o7_",
    "tb2ti2o7_",
    "pr2zr2o7_",
    "ba3cosb2o9_",
    "cs2cucl4_",
    "fe8_",
)


class InventoryError(ValueError):
    """Raised when inventory artifacts disagree or leak target evidence."""


@dataclass(frozen=True)
class LiteratureEvidenceInventory:
    contracts: tuple
    records: tuple
    source_index: tuple
    source_provisioning: tuple
    locator_inventory: tuple

    def as_plain_data(self):
        return {
            "contracts": [contract.as_plain_data() for contract in self.contracts],
            "records": [record.as_plain_data() for record in self.records],
            "source_index": _plain(self.source_index),
            "source_provisioning": _plain(self.source_provisioning),
            "locator_inventory": _plain(self.locator_inventory),
        }


def canonical_source_identity(source_url):
    """Return a normalized canonical DOI/arXiv identity string."""

    if not isinstance(source_url, str) or not source_url.strip():
        raise InventoryError("source URL must be a nonempty string")
    parsed = urlparse(source_url.strip())
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")
    if host in _DOI_HOSTS:
        if not path.lower().startswith("10.") or "/" not in path:
            raise InventoryError(f"invalid DOI URL: {source_url}")
        return f"doi:{path.lower()}"
    if host in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        for prefix in ("abs/", "pdf/"):
            if path.lower().startswith(prefix):
                path = path[len(prefix) :]
                break
        if path.lower().endswith(".pdf"):
            path = path[:-4]
        path = re.sub(r"v\d+$", "", path, flags=re.IGNORECASE)
        if not _ARXIV_ID_RE.fullmatch(path):
            raise InventoryError(f"invalid arXiv URL: {source_url}")
        return f"arxiv:{path.lower()}"
    raise InventoryError(f"source URL is not a canonical DOI/arXiv route: {source_url}")


def source_id_for_identity(identity):
    kind = identity.split(":", 1)[0]
    digest = hashlib.sha256(identity.encode("ascii")).hexdigest()[:20]
    return f"{kind}_{digest}"


def resolve_registry_selector(registry_entry, selector):
    """Resolve a closed, target-free selector against one registry entry."""

    fields = _validate_selector(selector)
    if not isinstance(registry_entry, Mapping):
        raise InventoryError("registry entry must be a mapping")
    standard_result = registry_entry.get("standard_result")
    if not isinstance(standard_result, Mapping):
        raise InventoryError("registry entry standard_result must be a mapping")
    missing = [field for field in fields if field not in standard_result]
    if missing:
        raise InventoryError(
            f"registry selector fields are absent: {', '.join(missing)}"
        )
    return {field: standard_result[field] for field in fields}


def derive_unresolved_status(record):
    """Derive the only valid status for a provisional, unacquired record."""

    if not isinstance(record, ProvisionalEvidenceRecord):
        raise InventoryError("unresolved status requires a provisional evidence record")
    if record.record_state != "unresolved" or not record.unresolved_reason.strip():
        raise InventoryError("provisional evidence does not fail closed")
    return "unresolved"


def load_and_validate_inventory(
    inventory_root=INVENTORY_ROOT, registry_entries=None, *, registry_path=None
):
    if registry_entries is None:
        from validation.literature_spin_model_benchmarks import (
            LITERATURE_STANDARD_RESULTS,
        )

        registry_entries = LITERATURE_STANDARD_RESULTS
    root = Path(inventory_root)
    record_paths = sorted((root / "records").glob("*.json"))
    raw_records = [_load_json(path) for path in record_paths]
    filename_names = [path.stem for path in record_paths]
    embedded_names = [
        record.get("benchmark_name") if isinstance(record, Mapping) else None
        for record in raw_records
    ]
    if filename_names != embedded_names:
        raise InventoryError(
            "record filenames must exactly match embedded benchmark names"
        )
    data = {
        "contracts": _load_collection(
            root / "canonical-observables.json", "canonical_observables"
        ),
        "source_index": _load_collection(root / "source-index.json", "sources"),
        "source_provisioning": _load_collection(
            root / "source-provisioning.json", "sources"
        ),
        "locator_inventory": _load_collection(
            root / "locator-inventory.json", "locators"
        ),
        "records": raw_records,
    }
    return validate_inventory(data, registry_entries, registry_path=registry_path)


def validate_inventory(data, registry_entries, *, registry_path=None):
    """Validate all inventory documents as one exact, fail-closed unit."""

    if not isinstance(data, Mapping):
        raise InventoryError("inventory must be a mapping")
    registry = list(registry_entries)
    literal_fields_by_name = literal_registry_claim_fields(registry_path)
    registry_names = [entry.get("name") for entry in registry]
    if len(registry) != 155 or len(set(registry_names)) != 155:
        raise InventoryError("registry must contain exactly 155 unique benchmark names")

    raw_contracts = _required_list(data, "contracts")
    raw_records = _required_list(data, "records")
    raw_locators = _required_list(data, "locator_inventory")
    raw_sources = _required_list(data, "source_index")
    raw_provisioning = _required_list(data, "source_provisioning")

    for collection_name, items in (
        ("canonical contracts", raw_contracts),
        ("provisional records", raw_records),
        ("locator inventory", raw_locators),
        ("source index", raw_sources),
        ("source provisioning", raw_provisioning),
    ):
        _reject_forbidden_keys(
            items,
            collection_name,
            forbidden_keys=_FORBIDDEN_ARTIFACT_KEYS,
        )

    _validate_name_set(
        registry_names,
        [item.get("benchmark_name") for item in raw_contracts],
        "canonical contract",
    )
    _validate_name_set(
        registry_names,
        [item.get("benchmark_name") for item in raw_records],
        "provisional record",
    )
    _validate_name_set(
        registry_names,
        [item.get("benchmark_name") for item in raw_locators],
        "locator rows",
    )

    try:
        contracts = tuple(CanonicalObservable(**item) for item in raw_contracts)
        records = tuple(ProvisionalEvidenceRecord(**item) for item in raw_records)
    except EvidenceSchemaError:
        raise

    registry_by_name = {entry["name"]: entry for entry in registry}
    contract_by_name = {item.benchmark_name: item for item in contracts}
    record_by_name = {item.benchmark_name: item for item in records}
    locator_by_name = {item["benchmark_name"]: item for item in raw_locators}

    for name in registry_names:
        entry = registry_by_name[name]
        expected_fields = _claim_fields(entry, literal_fields_by_name)
        contract = contract_by_name[name]
        if _is_generic_observable_identity(contract.observable.get("identity")):
            raise InventoryError(f"generic observable identity for {name}")
        if tuple(contract.observable.get("claim_fields", ())) != expected_fields:
            raise InventoryError(f"canonical contract claim fields mismatch for {name}")
        representation_fields = contract.representation.get("fields")
        if not isinstance(representation_fields, tuple) or not representation_fields:
            raise InventoryError(f"canonical contract representation missing for {name}")
        represented = tuple(field.get("id") for field in representation_fields)
        if represented != expected_fields:
            raise InventoryError(f"canonical representation mismatch for {name}")
        if contract.canonical_observable_id != name:
            raise InventoryError(f"canonical observable ID mismatch for {name}")
        _validate_canonical_contract_against_registry(contract, entry)
        field_specs = [_plain(field) for field in representation_fields]

        record = record_by_name[name]
        if record.canonical_observable_id != contract.canonical_observable_id:
            raise InventoryError(f"record canonical observable mismatch for {name}")
        expected_source_id = source_id_for_identity(
            canonical_source_identity(entry["source_url"])
        )
        if record.source_id != expected_source_id:
            raise InventoryError(f"record source identity mismatch for {name}")
        selected = resolve_registry_selector(entry, record.registry_selector)
        if tuple(selected) != expected_fields:
            raise InventoryError(f"registry selector mismatch for {name}")
        derive_unresolved_status(record)
        _reject_forbidden_keys(record.as_plain_data(), f"record {name}")
        _validate_record_strategies(
            record,
            field_specs,
            name,
        )

        locator = locator_by_name[name]
        _validate_locator(
            locator,
            expected_fields,
            name,
            expected_source_id=expected_source_id,
        )
        if _plain(record.target_locator_strategy) != locator["locator_strategy"]:
            raise InventoryError(f"record locator strategy mismatch for {name}")

    expected_sources = _expected_sources(registry)
    _validate_sources(raw_sources, expected_sources)
    _validate_provisioning(raw_provisioning, expected_sources)

    return LiteratureEvidenceInventory(
        contracts=contracts,
        records=records,
        source_index=tuple(_freeze(item) for item in raw_sources),
        source_provisioning=tuple(_freeze(item) for item in raw_provisioning),
        locator_inventory=tuple(_freeze(item) for item in raw_locators),
    )


def build_inventory_data(
    registry_entries, *, inventory_root=INVENTORY_ROOT, registry_path=None
):
    """Build target-free inventory documents from registry identity metadata."""

    registry = sorted(registry_entries, key=lambda entry: entry["name"])
    literal_fields_by_name = literal_registry_claim_fields(registry_path)
    sources_by_identity = defaultdict(list)
    for entry in registry:
        identity = canonical_source_identity(entry["source_url"])
        sources_by_identity[identity].append(entry["name"])

    contracts = _load_collection(
        Path(inventory_root) / "canonical-observables.json", "canonical_observables"
    )
    contract_by_name = {contract["benchmark_name"]: contract for contract in contracts}
    records = []
    locators = []
    for entry in registry:
        fields = _claim_fields(entry, literal_fields_by_name)
        contract = contract_by_name.get(entry["name"])
        if contract is None:
            raise InventoryError(
                f"missing independently maintained canonical contract for {entry['name']}"
            )
        field_specs = _plain(contract["representation"]["fields"])
        locator_class = _forecast_locator_class(entry, field_specs)
        target_representation = {
            "kind": "registered_field_map",
            "fields": _plain(field_specs),
        }
        locator_strategy = _locator_strategy(
            entry, field_specs, locator_class, target_representation
        )
        identity = canonical_source_identity(entry["source_url"])
        source_id = source_id_for_identity(identity)
        records.append(
            {
                "schema_version": 1,
                "record_state": "unresolved",
                "benchmark_name": entry["name"],
                "source_id": source_id,
                "registry_selector": {
                    "path": ["standard_result"],
                    "fields": list(fields),
                },
                "canonical_observable_id": entry["name"],
                "evidence_mode": _forecast_evidence_mode(entry),
                "target_locator_strategy": _plain(locator_strategy),
                "parser_strategy": {
                    "kind": "structured_source_field_extraction",
                    "output_fields": _plain(field_specs),
                },
                "comparator": {
                    "kind": "registered_field_comparison",
                    "fields": _plain(field_specs),
                },
                "unresolved_reason": (
                    "Authoritative source payload has not been acquired or parsed."
                ),
            }
        )
        locators.append(
            {
                "benchmark_name": entry["name"],
                "source_id": source_id,
                "locator_class": locator_class,
                "expected_container": _expected_container(locator_class),
                "target_representation": _plain(target_representation),
                "locator_strategy": _plain(locator_strategy),
            }
        )

    source_index = []
    provisioning = []
    for identity in sorted(sources_by_identity):
        source_id = source_id_for_identity(identity)
        kind, value = identity.split(":", 1)
        url = (
            f"https://doi.org/{value}"
            if kind == "doi"
            else f"https://arxiv.org/abs/{value}"
        )
        source_index.append(
            {
                "source_id": source_id,
                "canonical_identity": {"kind": kind, "value": value},
                "canonical_url": url,
                "benchmark_names": sorted(sources_by_identity[identity]),
            }
        )
        route = authoritative_route_for_identity({"kind": kind, "value": value})
        extension = "xml" if route["expected_media_type"] == "application/xml" else "pdf"
        provisioning.append(
            {
                "source_id": source_id,
                "authoritative_retrieval_route": {
                    "kind": route["kind"],
                    "url": route["url"],
                    "artifact_identifier": route["artifact_identifier"],
                    "work_identity_evidence": route["work_identity_evidence"],
                },
                "expected_media_type": route["expected_media_type"],
                "access_mode": route["access_mode"],
                "redistributability": "unresolved",
                "local_cache_location": (
                    f"source-cache/{source_id}/source.{extension}"
                ),
                "current_availability": "not_acquired",
            }
        )
    return {
        "contracts": contracts,
        "records": records,
        "source_index": source_index,
        "source_provisioning": provisioning,
        "locator_inventory": locators,
    }


def write_inventory(
    inventory_root=INVENTORY_ROOT, registry_entries=None, *, registry_path=None
):
    """Write deterministic static JSON artifacts; no source acquisition occurs."""

    if registry_entries is None:
        from validation.literature_spin_model_benchmarks import (
            LITERATURE_STANDARD_RESULTS,
        )

        registry_entries = LITERATURE_STANDARD_RESULTS
    data = build_inventory_data(
        registry_entries,
        inventory_root=inventory_root,
        registry_path=registry_path,
    )
    validate_inventory(data, registry_entries, registry_path=registry_path)
    root = Path(inventory_root)
    records_dir = root / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    _write_collection(root / "canonical-observables.json", "canonical_observables", data["contracts"])
    _write_collection(root / "source-index.json", "sources", data["source_index"])
    _write_collection(root / "source-provisioning.json", "sources", data["source_provisioning"])
    _write_collection(root / "locator-inventory.json", "locators", data["locator_inventory"])
    expected_files = set()
    for record in data["records"]:
        path = records_dir / f"{record['benchmark_name']}.json"
        expected_files.add(path.name)
        _write_json(path, record)
    extras = [path for path in records_dir.glob("*.json") if path.name not in expected_files]
    if extras:
        raise InventoryError(
            "orphan record files must be removed explicitly: "
            + ", ".join(path.name for path in extras)
        )


def literal_registry_claim_fields(registry_path=None):
    """Read original claim keys from list literals before runtime augmentation."""

    path = Path(registry_path) if registry_path else Path(__file__).with_name(
        "literature_spin_model_benchmarks.py"
    )
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise InventoryError(f"cannot parse registry AST {path}: {exc}") from exc
    list_nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name)
            and target.id == "LITERATURE_STANDARD_RESULTS"
            for target in node.targets
        ):
            list_nodes.append(node.value)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            function = node.value.func
            if (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "LITERATURE_STANDARD_RESULTS"
                and function.attr == "extend"
                and len(node.value.args) == 1
            ):
                list_nodes.append(node.value.args[0])

    result = {}
    for list_node in list_nodes:
        if not isinstance(list_node, (ast.List, ast.Tuple)):
            raise InventoryError("registry definition and extensions must use list literals")
        for entry_node in list_node.elts:
            if not isinstance(entry_node, ast.Dict):
                raise InventoryError("registry list entries must be dictionary literals")
            entry_nodes = {
                key.value: value
                for key, value in zip(entry_node.keys, entry_node.values)
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            if "name" not in entry_nodes or "standard_result" not in entry_nodes:
                raise InventoryError("registry literal lacks name or standard_result")
            try:
                name = ast.literal_eval(entry_nodes["name"])
            except (ValueError, SyntaxError) as exc:
                raise InventoryError("registry name must be a string literal") from exc
            standard_result = entry_nodes["standard_result"]
            if not isinstance(standard_result, ast.Dict):
                raise InventoryError(f"standard_result must be a dictionary literal for {name}")
            fields = tuple(
                key.value
                for key in standard_result.keys
                if isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and key.value not in _IGNORED_REGISTRY_OPERANDS
            )
            if name in result:
                raise InventoryError(f"duplicate registry literal name {name}")
            result[name] = fields
    if len(result) != 155:
        raise InventoryError(
            f"registry AST must contain 155 literal entries, found {len(result)}"
        )
    return result


def _claim_fields(entry, literal_fields_by_name):
    name = entry.get("name")
    if name not in literal_fields_by_name:
        raise InventoryError(f"no literal registry claim fields for {name}")
    fields = tuple(literal_fields_by_name[name])
    if not fields:
        raise InventoryError(f"no scientific registry operands for {name}")
    if len(fields) != len(set(fields)):
        raise InventoryError(f"duplicate registry operands for {name}")
    runtime_result = entry.get("standard_result")
    if not isinstance(runtime_result, Mapping):
        raise InventoryError(f"standard_result must be a mapping for {name}")
    missing = [field for field in fields if field not in runtime_result]
    if missing:
        raise InventoryError(
            f"literal registry fields missing at runtime for {name}: {', '.join(missing)}"
        )
    return fields


def _humanize_identifier(identifier):
    return identifier.replace("_", " ")


def _is_material_claim(entry):
    return (
        any(marker in entry["observable"] for marker in _MATERIAL_OBSERVABLE_MARKERS)
        or entry["name"].startswith(_MATERIAL_BENCHMARK_PREFIXES)
    )




def _is_generic_observable_identity(identity):
    return (
        not isinstance(identity, str)
        or not identity
        or identity in _GENERIC_OBSERVABLES
        or identity.startswith(
            ("published_observable_", "material_model_", "phase_diagram_")
        )
        or bool(_GENERIC_OBSERVABLE_SUFFIX_RE.search(identity))
    )


def _validate_canonical_contract_against_registry(contract, entry):
    name = entry["name"]
    if contract.subject.strip().lower() in _PLACEHOLDER_TEXT:
        raise InventoryError(f"canonical contract subject is generic for {name}")
    if contract.system != entry["model"]:
        raise InventoryError(f"canonical contract system mismatch for {name}")
    expected_hamiltonian = {
        "expression": entry["hamiltonian"],
        "terms": entry["hamiltonian_terms"],
        "lattice": entry["lattice"],
    }
    if _plain(contract.hamiltonian) != expected_hamiltonian:
        raise InventoryError(f"canonical contract Hamiltonian mismatch for {name}")
    if _plain(contract.parameter_regime) != entry["parameters"]:
        raise InventoryError(f"canonical contract parameter regime mismatch for {name}")
    semantics = contract.observable.get("semantics")
    if (
        not isinstance(semantics, tuple)
        or not semantics
        or any(not isinstance(item, str) or not item.strip() for item in semantics)
        or any(
            phrase in item.lower()
            for item in semantics
            for phrase in (
                "under the declared parameter regime",
                "published published observable",
            )
        )
    ):
        raise InventoryError(f"generic observable semantics for {name}")
    for field in contract.representation["fields"]:
        if field["units"] in _FORBIDDEN_GENERIC_REPRESENTATIONS:
            raise InventoryError(f"generic representation units for {name}")
        if field["convention"] in _FORBIDDEN_GENERIC_REPRESENTATIONS:
            raise InventoryError(f"generic representation convention for {name}")
    expected_units = "; ".join(
        f"{field['id']}={field['units']}" for field in contract.representation["fields"]
    )
    if contract.units != expected_units:
        raise InventoryError(f"canonical top-level units mismatch for {name}")
    size_or_limit = contract.size_or_limit
    if set(size_or_limit) != {"category", "scope_subject"}:
        raise InventoryError(f"canonical size or limit schema mismatch for {name}")
    size_category = size_or_limit["category"]
    if size_category not in _SIZE_LIMIT_PHYSICAL_REGIMES:
        raise InventoryError(f"canonical size or limit category mismatch for {name}")
    if size_or_limit["scope_subject"] != contract.subject:
        raise InventoryError(f"canonical size or limit subject mismatch for {name}")
    conditions = contract.conditions
    required_conditions = {
        "comparison_kind",
        "backend_scope",
        "physical_regime",
        "source_claim_scope",
        "model_parameters",
    }
    if not required_conditions <= set(conditions):
        raise InventoryError(f"canonical physical conditions missing for {name}")
    if conditions["comparison_kind"] != entry["comparison_kind"]:
        raise InventoryError(f"canonical comparison condition mismatch for {name}")
    if conditions["backend_scope"] != entry["backend_needed"]:
        raise InventoryError(f"canonical backend scope mismatch for {name}")
    if conditions["physical_regime"] != _SIZE_LIMIT_PHYSICAL_REGIMES[size_category]:
        raise InventoryError(f"canonical physical regime mismatch for {name}")
    expected_claim_scope = _expected_source_claim_scope(entry)
    if (
        conditions["source_claim_scope"] not in _SOURCE_CLAIM_SCOPES
        or conditions["source_claim_scope"] != expected_claim_scope
    ):
        raise InventoryError(f"canonical source claim scope mismatch for {name}")
    if _plain(conditions["model_parameters"]) != entry["parameters"]:
        raise InventoryError(f"canonical condition parameters mismatch for {name}")


def _expected_source_claim_scope(entry):
    if _is_material_claim(entry):
        return "direct published material or experimental observable"
    if entry["comparison_kind"] in {"exact_solution", "exact_enumeration"}:
        return "published exact model result"
    if entry["comparison_kind"] in {"paper_formula", "theorem"}:
        return "published analytic relation or formula"
    return "published numerical or categorical model result"


def _validate_selector(selector):
    if not isinstance(selector, Mapping) or set(selector) != {"path", "fields"}:
        raise InventoryError("registry selector must contain exactly path and fields")
    if selector["path"] not in (["standard_result"], ("standard_result",)):
        raise InventoryError("registry selector path must be standard_result")
    fields = selector["fields"]
    if (
        not isinstance(fields, Sequence)
        or isinstance(fields, (str, bytes, bytearray))
        or not fields
        or any(not isinstance(field, str) or not field for field in fields)
        or len(fields) != len(set(fields))
    ):
        raise InventoryError("registry selector fields must be unique nonempty strings")
    forbidden = set(fields) & _IGNORED_REGISTRY_OPERANDS
    if forbidden:
        raise InventoryError(
            "registry selector includes audit-only operands: " + ", ".join(sorted(forbidden))
        )
    return tuple(fields)


def _validate_locator(locator, expected_fields, name, *, expected_source_id):
    _reject_forbidden_keys(locator, f"locator {name}")
    required = {
        "benchmark_name",
        "source_id",
        "locator_class",
        "expected_container",
        "target_representation",
        "locator_strategy",
    }
    if not isinstance(locator, Mapping) or set(locator) != required:
        raise InventoryError(f"invalid locator row fields for {name}")
    if locator["source_id"] != expected_source_id:
        raise InventoryError(f"locator source identity mismatch for {name}")
    locator_class = locator.get("locator_class")
    if locator_class not in _ALLOWED_LOCATOR_CLASSES:
        raise InventoryError(f"invalid locator class for {name}")
    if not isinstance(locator.get("expected_container"), str) or not locator["expected_container"]:
        raise InventoryError(f"missing expected locator container for {name}")
    representation = locator.get("target_representation")
    if not isinstance(representation, Mapping) or set(representation) != {"kind", "fields"}:
        raise InventoryError(f"invalid target representation for {name}")
    represented = tuple(field.get("id") for field in representation["fields"])
    if represented != expected_fields:
        raise InventoryError(f"locator target representation mismatch for {name}")
    strategy = locator["locator_strategy"]
    required_strategy = {
        "locator_class",
        "expected_container",
        "target_representation",
        "source_context_hint",
        "search_anchors",
        "rationale",
        "locator_basis",
        "canonical_source_identity",
    }
    if not isinstance(strategy, Mapping) or set(strategy) != required_strategy:
        raise InventoryError(f"locator strategy is incomplete for {name}")
    if strategy["locator_class"] != locator["locator_class"]:
        raise InventoryError(f"locator strategy class mismatch for {name}")
    if strategy["expected_container"] != locator["expected_container"]:
        raise InventoryError(f"locator strategy container mismatch for {name}")
    if strategy["target_representation"] != locator["target_representation"]:
        raise InventoryError(f"locator strategy representation mismatch for {name}")
    for key in ("source_context_hint", "rationale", "canonical_source_identity"):
        if not isinstance(strategy[key], str) or not strategy[key].strip():
            raise InventoryError(f"locator strategy missing {key} for {name}")
    anchors = strategy["search_anchors"]
    if (
        not isinstance(anchors, Sequence)
        or isinstance(anchors, (str, bytes, bytearray))
        or len(anchors) < 2
        or any(not isinstance(anchor, str) or not anchor.strip() for anchor in anchors)
    ):
        raise InventoryError(f"locator strategy search anchors are incomplete for {name}")
    if set(strategy["locator_basis"]) != {
        "citation_locator",
        "benchmark_name",
        "observable_semantics",
        "canonical_source_identity",
    }:
        raise InventoryError(f"locator strategy basis is incomplete for {name}")


def _validate_record_strategies(record, field_specs, name):
    parser = _plain(record.parser_strategy)
    expected_parser = {
        "kind": "structured_source_field_extraction",
        "output_fields": field_specs,
    }
    if parser != expected_parser:
        raise InventoryError(f"parser strategy mismatch for {name}")
    comparator = _plain(record.comparator)
    expected_comparator = {
        "kind": "registered_field_comparison",
        "fields": field_specs,
    }
    if comparator != expected_comparator:
        raise InventoryError(f"comparator mismatch for {name}")


def _expected_sources(registry):
    result = defaultdict(list)
    for entry in registry:
        identity = canonical_source_identity(entry["source_url"])
        result[identity].append(entry["name"])
    return result


def _validate_sources(sources, expected_sources):
    if len(sources) != len(expected_sources):
        raise InventoryError(
            "source index must match all registry-derived canonical source identities exactly: "
            f"expected {len(expected_sources)}, found {len(sources)}"
        )
    ids = [source.get("source_id") for source in sources]
    if len(set(ids)) != len(ids):
        raise InventoryError("duplicate source IDs in source index")
    actual_identities = set()
    for source in sources:
        if set(source) != {
            "source_id",
            "canonical_identity",
            "canonical_url",
            "benchmark_names",
        }:
            raise InventoryError(f"invalid source index fields for {source.get('source_id')}")
        identity_data = source.get("canonical_identity")
        if not isinstance(identity_data, Mapping) or set(identity_data) != {"kind", "value"}:
            raise InventoryError("invalid canonical source identity")
        identity = f"{identity_data['kind']}:{identity_data['value']}"
        actual_identities.add(identity)
        if identity not in expected_sources:
            raise InventoryError(f"unexpected canonical source identity {identity}")
        if source["source_id"] != source_id_for_identity(identity):
            raise InventoryError(f"source ID is not derived from canonical source identity {identity}")
        kind, value = identity.split(":", 1)
        expected_url = (
            f"https://doi.org/{value}"
            if kind == "doi"
            else f"https://arxiv.org/abs/{value}"
        )
        if source["canonical_url"] != expected_url:
            raise InventoryError(f"canonical URL mismatch for {identity}")
        if sorted(source.get("benchmark_names", ())) != sorted(expected_sources[identity]):
            raise InventoryError(f"source benchmark coverage mismatch for {identity}")
    if actual_identities != set(expected_sources):
        raise InventoryError("canonical source identity coverage mismatch")


def _validate_provisioning(routes, expected_sources):
    identity_by_id = {
        source_id_for_identity(identity): identity for identity in expected_sources
    }
    expected_ids = set(identity_by_id)
    route_ids = [route.get("source_id") for route in routes]
    if (
        len(routes) != len(expected_ids)
        or set(route_ids) != expected_ids
        or len(set(route_ids)) != len(expected_ids)
    ):
        raise InventoryError(
            "source provisioning must match all registry-derived source identities exactly"
        )
    cache_locations = [route.get("local_cache_location") for route in routes]
    duplicate_locations = sorted(
        [
            location
            for location, count in Counter(cache_locations).items()
            if count > 1
        ],
        key=repr,
    )
    if duplicate_locations:
        raise InventoryError(
            "duplicate local cache location: "
            + ", ".join(repr(location) for location in duplicate_locations)
        )
    for route in routes:
        required = {
            "source_id",
            "authoritative_retrieval_route",
            "expected_media_type",
            "access_mode",
            "redistributability",
            "local_cache_location",
            "current_availability",
        }
        if set(route) != required:
            raise InventoryError(f"invalid provisioning fields for {route.get('source_id')}")
        retrieval = route["authoritative_retrieval_route"]
        if not isinstance(retrieval, Mapping) or set(retrieval) != {
            "kind",
            "url",
            "artifact_identifier",
            "work_identity_evidence",
        }:
            raise InventoryError(f"invalid authoritative retrieval route for {route['source_id']}")
        identity = identity_by_id[route["source_id"]]
        kind, value = identity.split(":", 1)
        expected_route = authoritative_route_for_identity(
            {"kind": kind, "value": value}
        )
        if retrieval != {
            "kind": expected_route["kind"],
            "url": expected_route["url"],
            "artifact_identifier": expected_route["artifact_identifier"],
            "work_identity_evidence": expected_route["work_identity_evidence"],
        }:
            raise InventoryError(
                f"authoritative retrieval route mismatch for {route['source_id']}"
            )
        if route["expected_media_type"] != expected_route["expected_media_type"]:
            raise InventoryError(f"invalid expected media type for {route['source_id']}")
        if route["access_mode"] != expected_route["access_mode"]:
            raise InventoryError(f"invalid access mode for {route['source_id']}")
        if route["redistributability"] != "unresolved":
            raise InventoryError(f"redistributability must remain unresolved for {route['source_id']}")
        if route["current_availability"] != "not_acquired":
            raise InventoryError(
                f"source availability must be not_acquired for {route['source_id']}"
            )
        extension = "xml" if route["expected_media_type"] == "application/xml" else "pdf"
        expected_cache_location = (
            f"source-cache/{route['source_id']}/source.{extension}"
        )
        if route["local_cache_location"] != expected_cache_location:
            raise InventoryError(f"invalid local cache location for {route['source_id']}")


def _validate_name_set(expected, actual, label):
    duplicate = sorted(name for name, count in Counter(actual).items() if count > 1)
    missing = sorted(set(expected) - set(actual))
    orphan = sorted(set(actual) - set(expected))
    diagnostics = []
    plural = "locator rows" if label == "locator rows" else f"{label}s"
    if duplicate:
        duplicate_label = label if label != "locator rows" else "locator row"
        diagnostics.append(
            f"duplicate {duplicate_label} names: {', '.join(duplicate)}"
        )
    if missing:
        diagnostics.append(f"missing {plural}: {', '.join(missing)}")
    if orphan:
        diagnostics.append(f"orphan {plural}: {', '.join(orphan)}")
    if diagnostics:
        raise InventoryError("; ".join(diagnostics))


def _reject_forbidden_keys(
    value, context, *, forbidden_keys=_FORBIDDEN_INVENTORY_KEYS
):
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in forbidden_keys:
                raise InventoryError(f"{context} contains forbidden field {key}")
            _reject_forbidden_keys(
                item, context, forbidden_keys=forbidden_keys
            )
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_forbidden_keys(
                item, context, forbidden_keys=forbidden_keys
            )


def _forecast_locator_class(entry, field_specs):
    if entry["name"] in _LOCATOR_CLASS_OVERRIDES:
        return _LOCATOR_CLASS_OVERRIDES[entry["name"]]
    comparison = entry["comparison_kind"]
    types = {field["type"] for field in field_specs}
    if _is_material_claim(entry):
        locator = entry["citation_locator"].lower()
        if any(token in locator for token in ("experimental", "observed", "neutron")):
            return "abstract"
        return "body_text"
    if comparison in {"exact_solution", "exact_enumeration"} and types <= {"number", "string", "list[number]"}:
        return "equation"
    if comparison == "paper_numeric":
        if "phase" in entry["observable"]:
            return "figure_caption"
        if any(field["id"] in {"couplings", "levels", "degeneracies"} for field in field_specs):
            return "table"
        return "body_text"
    return "body_text"


def _locator_strategy(entry, field_specs, locator_class, target_representation):
    identity = canonical_source_identity(entry["source_url"])
    anchors = []

    def add_anchor(anchor):
        if isinstance(anchor, str):
            anchor = anchor.strip()
            if anchor and anchor not in anchors:
                anchors.append(anchor)

    material = entry.get("parameters", {}).get("material")
    add_anchor(material)
    add_anchor(_humanize_identifier(entry["observable"]))
    for field in field_specs:
        add_anchor(_humanize_identifier(field["id"]))
    locator_text = entry["citation_locator"]
    lower_locator = locator_text.lower()
    for phrase in (
        "phase diagram",
        "ground state energy",
        "spin waves",
        "exchange parameterization",
        "universal jump",
        "critical line",
        "spin liquid",
    ):
        if phrase in lower_locator:
            add_anchor(phrase if phrase != "ground state energy" else "ground-state energy")
    add_anchor(locator_text)
    if len(anchors) < 2:
        add_anchor(_humanize_identifier(entry["model"]))
    return {
        "locator_class": locator_class,
        "expected_container": _expected_container(locator_class),
        "target_representation": target_representation,
        "source_context_hint": locator_text,
        "search_anchors": anchors,
        "rationale": (
            f"Search the authoritative {identity} payload for the cited context and "
            f"the declared {_humanize_identifier(entry['observable'])} observable; "
            "Task 5 must replace this forecast with exact source coordinates."
        ),
        "locator_basis": [
            "citation_locator",
            "benchmark_name",
            "observable_semantics",
            "canonical_source_identity",
        ],
        "canonical_source_identity": identity,
    }


def _expected_container(locator_class):
    return {
        "equation": "numbered_or_displayed_equation",
        "table": "main_text_or_supplemental_table",
        "abstract": "abstract_claim_statement",
        "body_text": "main_text_claim_statement",
        "figure_caption": "figure_caption_claim_statement",
        "supplemental": "supplemental_claim_location",
        "metadata_field": "authoritative_metadata_record",
    }[locator_class]


def _forecast_evidence_mode(entry):
    if entry["comparison_kind"] in {"exact_solution", "exact_enumeration"}:
        return "local_recompute"
    if entry["comparison_kind"] in {"paper_formula", "paper_numeric", "theorem"}:
        return "local_source_parse"
    return "projection_only"


def _required_list(data, key):
    value = data.get(key)
    if not isinstance(value, list):
        raise InventoryError(f"{key} must be a list")
    return value


def _load_collection(path, key):
    document = _load_json(path)
    if not isinstance(document, Mapping) or set(document) != {"schema_version", key}:
        raise InventoryError(f"{path.name} must contain schema_version and {key}")
    if document["schema_version"] != 1 or not isinstance(document[key], list):
        raise InventoryError(f"invalid collection schema in {path.name}")
    return document[key]


def _load_json(path):
    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InventoryError(f"duplicate JSON key {key!r} in {path}")
            result[key] = value
        return result

    def reject_non_finite(value):
        raise InventoryError(f"non-finite JSON number {value} in {path}")

    def parse_finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            reject_non_finite(value)
        return parsed

    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            return json.load(
                handle,
                object_pairs_hook=reject_duplicate_keys,
                parse_constant=reject_non_finite,
                parse_float=parse_finite_float,
            )
    except (OSError, json.JSONDecodeError) as exc:
        raise InventoryError(f"cannot load structured JSON {path}: {exc}") from exc


def load_canonical_observable_specs(inventory_root=INVENTORY_ROOT):
    """Load explicit canonical identities without performing import-time I/O."""

    contracts = _load_collection(
        Path(inventory_root) / "canonical-observables.json", "canonical_observables"
    )
    return {
        contract["benchmark_name"]: {
            "identity": contract["observable"]["identity"],
            "primary_semantic": contract["observable"]["semantics"][0],
        }
        for contract in contracts
    }


def _write_collection(path, key, values):
    _write_json(path, {"schema_version": 1, key: values})


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        handle.write("\n")


def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


if __name__ == "__main__":
    write_inventory()
