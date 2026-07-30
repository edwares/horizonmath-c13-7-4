"""Audited candidate-formula checkpoints for selected link classes."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from horizonlink import __version__
from horizonlink.candidate_audit import (
    audit_candidate_formula_corpus,
)
from horizonlink.candidate_screening import (
    CORPUS_SCHEMA_VERSION,
    generate_candidate_screening_corpus,
)
from horizonlink.canonical import (
    sha256_bytes,
    sha256_file,
    write_json,
    write_sha256_sidecar,
)
from horizonlink.input import load_link
from horizonlink.manifest import build_manifest


CHECKPOINT_SCHEMA_VERSION = (
    "horizonmath.candidate-formula-checkpoint.v1"
)
STRUCTURAL_CENSUS_SCHEMA_VERSION = (
    "horizonmath.structural-census.v1"
)
STRUCTURAL_CLASS_SCHEMA_VERSION = (
    "horizonmath.structural-census-class.v1"
)
PROFILE_SCREENING_SCHEMA_VERSION = (
    "horizonmath.solver-free-profile-screening.v1"
)
PROFILE_SCREENING_CLASS_SCHEMA_VERSION = (
    "horizonmath.solver-free-profile-screening-class.v1"
)


class CandidateCheckpointError(ValueError):
    """Raised when a candidate-formula checkpoint fails closed."""


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load_json_object(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        _DuplicateKeyError,
    ) as exc:
        raise CandidateCheckpointError(
            f"cannot load {path.name}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise CandidateCheckpointError(
            f"{path.name} must contain a JSON object"
        )
    return value, sha256_bytes(raw)


def _safe_checkpoint_path(
    checkpoint: Path,
    relative: str,
) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise CandidateCheckpointError(
            f"unsafe checkpoint path: {relative!r}"
        )
    path = checkpoint.joinpath(*pure.parts)
    try:
        path.resolve().relative_to(checkpoint.resolve())
    except ValueError as exc:
        raise CandidateCheckpointError(
            f"checkpoint path escapes root: {relative!r}"
        ) from exc
    return path


def _verify_checkpoint_checksums(
    checkpoint: Path,
) -> dict[str, Any]:
    checksum_path = checkpoint / "SHA256SUMS"
    try:
        lines = checksum_path.read_text(
            encoding="utf-8"
        ).splitlines()
    except (OSError, UnicodeError) as exc:
        raise CandidateCheckpointError(
            f"cannot read checkpoint checksums: {exc}"
        ) from exc

    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        parts = line.split("  ", 1)
        if (
            len(parts) != 2
            or len(parts[0]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in parts[0]
            )
            or not parts[1]
        ):
            raise CandidateCheckpointError(
                f"invalid SHA256SUMS row {line_number}"
            )
        expected, relative = parts
        if relative in seen:
            raise CandidateCheckpointError(
                f"duplicate SHA256SUMS path: {relative}"
            )
        seen.add(relative)
        path = _safe_checkpoint_path(checkpoint, relative)
        if not path.is_file():
            raise CandidateCheckpointError(
                f"missing checkpoint artifact: {relative}"
            )
        if sha256_file(path) != expected:
            raise CandidateCheckpointError(
                f"checkpoint hash mismatch: {relative}"
            )
        rows.append((expected, relative))

    observed_files = sorted(
        path.relative_to(checkpoint).as_posix()
        for path in checkpoint.rglob("*")
        if path.is_file() and path != checksum_path
    )
    recorded_files = sorted(relative for _, relative in rows)
    if observed_files != recorded_files:
        raise CandidateCheckpointError(
            "checkpoint SHA256SUMS does not account for every file"
        )
    return {
        "status": "PASS",
        "directory_name": checkpoint.name,
        "sha256sums_sha256": sha256_file(checksum_path),
        "recorded_file_count": len(rows),
        "all_recorded_hashes_match": True,
        "every_checkpoint_file_accounted_for": True,
    }


def _resolve_artifact(
    checkpoint: Path,
    artifact: dict[str, Any],
    label: str,
) -> Path:
    try:
        relative = artifact["path"]
        expected_hash = artifact["sha256"]
        expected_bytes = artifact["bytes"]
    except (KeyError, TypeError) as exc:
        raise CandidateCheckpointError(
            f"{label} artifact record is incomplete"
        ) from exc
    path = _safe_checkpoint_path(checkpoint, relative)
    if not path.is_file():
        raise CandidateCheckpointError(
            f"{label} artifact is missing: {relative}"
        )
    if path.stat().st_size != expected_bytes:
        raise CandidateCheckpointError(
            f"{label} artifact byte count mismatch"
        )
    if sha256_file(path) != expected_hash:
        raise CandidateCheckpointError(
            f"{label} artifact hash mismatch"
        )
    return path


def _find_class_record(
    rows: Any,
    class_index: int,
    label: str,
) -> dict[str, Any]:
    if not isinstance(rows, list):
        raise CandidateCheckpointError(f"{label} classes must be an array")
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("class_index") == class_index
    ]
    if len(matches) != 1:
        raise CandidateCheckpointError(
            f"{label} must contain class {class_index} exactly once"
        )
    return matches[0]


def _audit_structural_input(
    checkpoint: Path,
    class_index: int,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    Path,
    dict[str, Any],
    dict[str, Any],
]:
    checksum_audit = _verify_checkpoint_checksums(checkpoint)
    census_path = checkpoint / "census.manifest.json"
    census, census_sha256 = _load_json_object(census_path)
    class_entry = _find_class_record(
        census.get("classes"),
        class_index,
        "structural census",
    )
    input_path = _resolve_artifact(
        checkpoint,
        class_entry["input"],
        "structural input",
    )
    class_path = _resolve_artifact(
        checkpoint,
        class_entry["class_record"],
        "structural class",
    )
    class_record, class_record_sha256 = _load_json_object(class_path)
    link = load_link(input_path)
    structural = build_manifest(link, 4)
    compact_orbits = class_record.get(
        "candidate_minimum_point_sets", {}
    )
    rebuilt_orbits = structural.get(
        "candidate_minimum_point_sets", {}
    )
    compact_group = class_record.get("automorphism_group", {})
    rebuilt_group = structural.get("automorphism_group", {})
    checks = {
        "census_schema_supported": (
            census.get("schema_version")
            == STRUCTURAL_CENSUS_SCHEMA_VERSION
        ),
        "census_status_enumerated": (
            census.get("status") == "ENUMERATED"
        ),
        "all_68_classes_accounted_for": (
            census.get("summary", {}).get(
                "all_classes_accounted_for"
            )
            is True
            and census.get("summary", {}).get(
                "enumerated_class_count"
            )
            == 68
        ),
        "class_schema_supported": (
            class_record.get("schema_version")
            == STRUCTURAL_CLASS_SCHEMA_VERSION
        ),
        "class_status_enumerated": (
            class_record.get("status") == "ENUMERATED"
        ),
        "class_index_equal": (
            class_record.get("class_index")
            == structural.get("input", {}).get("class_index")
            == class_index
        ),
        "rebuilt_structural_audit_passed": (
            structural.get("status") == "ENUMERATED"
            and structural.get("structural_audit", {}).get(
                "all_checks_passed"
            )
            is True
        ),
        "canonical_document_hash_equal": (
            class_record.get("input", {}).get(
                "canonical_document_sha256"
            )
            == structural["input"]["canonical_document_sha256"]
        ),
        "canonical_labeled_link_hash_equal": (
            class_record.get("input", {}).get(
                "canonical_labeled_link_sha256"
            )
            == structural["input"][
                "canonical_labeled_link_sha256"
            ]
        ),
        "automorphism_group_order_equal": (
            compact_group.get("order")
            == rebuilt_group.get("order")
        ),
        "automorphism_group_hash_equal": (
            compact_group.get("group_sha256")
            == rebuilt_group.get("group_sha256")
        ),
        "candidate_orbit_count_equal": (
            compact_orbits.get("orbit_count")
            == rebuilt_orbits.get("orbit_count")
        ),
        "candidate_partition_hash_equal": (
            compact_orbits.get("partition_sha256")
            == rebuilt_orbits.get("partition_sha256")
        ),
        "candidate_representatives_equal": (
            compact_orbits.get("representatives")
            == rebuilt_orbits.get("representatives")
        ),
        "candidate_orbit_summaries_equal": (
            compact_orbits.get("orbits")
            == [
                {
                    "id": orbit["id"],
                    "representative": orbit["representative"],
                    "size": len(orbit["members"]),
                    "stabilizer_order": orbit[
                        "stabilizer_order"
                    ],
                    "orbit_stabilizer_check": orbit[
                        "orbit_stabilizer_check"
                    ],
                }
                for orbit in rebuilt_orbits.get("orbits", [])
            ]
        ),
        "checkpoint_declares_no_formula_or_solver_run": (
            class_record.get("scope_guardrails", {}).get(
                "formulas_generated"
            )
            is False
            and class_record.get("scope_guardrails", {}).get(
                "solver_run"
            )
            is False
            and class_record.get("scope_guardrails", {}).get(
                "proof_generated"
            )
            is False
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise CandidateCheckpointError(
            "structural input audit failed: " + ", ".join(failed)
        )
    audit = {
        "checkpoint_checksums": checksum_audit,
        "census_manifest": {
            "path": "census.manifest.json",
            "bytes": census_path.stat().st_size,
            "sha256": census_sha256,
        },
        "class_record": class_entry["class_record"],
        "input_link": class_entry["input"],
        "checks": checks,
        "all_checks_passed": True,
    }
    input_artifact = {
        "checkpoint": checkpoint.name,
        **class_entry["input"],
    }
    class_artifact = {
        "checkpoint": checkpoint.name,
        **class_entry["class_record"],
        "loaded_sha256": class_record_sha256,
    }
    return (
        audit,
        structural,
        input_path,
        input_artifact,
        class_artifact,
    )


def _audit_profile_screening_gate(
    checkpoint: Path,
    class_index: int,
    structural_audit: dict[str, Any],
    structural: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    checksum_audit = _verify_checkpoint_checksums(checkpoint)
    manifest_path = checkpoint / "screening.manifest.json"
    manifest, manifest_sha256 = _load_json_object(manifest_path)
    class_entry = _find_class_record(
        manifest.get("classes"),
        class_index,
        "profile screening",
    )
    class_path = _resolve_artifact(
        checkpoint,
        class_entry["class_manifest"],
        "profile-screening class",
    )
    class_manifest, class_manifest_sha256 = _load_json_object(
        class_path
    )
    expected_orbits = structural["candidate_minimum_point_sets"][
        "orbits"
    ]
    decisions = class_manifest.get(
        "candidate_orbit_screening", {}
    ).get("decisions", [])
    expected_decisions = [
        {
            "orbit_index": orbit_index,
            "representative": orbit["representative"],
            "orbit_size": len(orbit["members"]),
            "stabilizer_order": orbit["stabilizer_order"],
        }
        for orbit_index, orbit in enumerate(expected_orbits)
    ]
    observed_decisions = [
        {
            "orbit_index": decision.get("orbit_index"),
            "representative": decision.get("representative"),
            "orbit_size": decision.get("orbit_size"),
            "stabilizer_order": decision.get("stabilizer_order"),
        }
        for decision in decisions
    ]
    checks = {
        "screening_schema_supported": (
            manifest.get("schema_version")
            == PROFILE_SCREENING_SCHEMA_VERSION
        ),
        "screening_status_enumerated": (
            manifest.get("status") == "ENUMERATED"
        ),
        "class_schema_supported": (
            class_manifest.get("schema_version")
            == PROFILE_SCREENING_CLASS_SCHEMA_VERSION
        ),
        "class_status_enumerated": (
            class_manifest.get("status") == "ENUMERATED"
        ),
        "class_index_equal": (
            class_entry.get("class_index")
            == class_manifest.get("class_index")
            == class_index
        ),
        "structural_census_manifest_hash_equal": (
            manifest.get("input", {})
            .get("structural_census", {})
            .get("census_manifest_sha256")
            == structural_audit["census_manifest"]["sha256"]
        ),
        "canonical_document_hash_equal": (
            class_manifest.get("input", {}).get(
                "canonical_document_sha256"
            )
            == structural["input"]["canonical_document_sha256"]
        ),
        "canonical_labeled_link_hash_equal": (
            class_manifest.get("input", {}).get(
                "canonical_labeled_link_sha256"
            )
            == structural["input"][
                "canonical_labeled_link_sha256"
            ]
        ),
        "candidate_orbit_count_equal": (
            class_manifest.get(
                "candidate_orbit_screening", {}
            ).get("orbit_count")
            == len(expected_orbits)
        ),
        "one_decision_per_orbit": (
            observed_decisions == expected_decisions
        ),
        "all_candidate_orbits_retained": (
            len(decisions) == len(expected_orbits)
            and all(
                decision.get("disposition") == "RETAINED"
                and decision.get("evidence_status")
                == "NO_CONTRADICTION_FOUND"
                and decision.get("rule_id")
                == "NO_SOLVER_FREE_CANDIDATE_CONTRADICTION"
                for decision in decisions
            )
        ),
        "formula_status_not_started": (
            class_manifest.get("status_ledger", {}).get("formulas")
            == "NOT_STARTED"
        ),
        "lp_solver_proof_verifier_not_started": (
            class_manifest.get("status_ledger", {}).get("root_lp")
            == "NOT_STARTED"
            and class_manifest.get("status_ledger", {}).get("solver")
            == "NOT_STARTED"
            and class_manifest.get("status_ledger", {}).get("proof")
            == "NOT_STARTED"
            and class_manifest.get("status_ledger", {}).get(
                "verification"
            )
            == "NOT_STARTED"
        ),
        "scope_declares_no_prior_formula_or_solver_run": (
            class_manifest.get("scope_guardrails", {}).get(
                "formulas_generated"
            )
            is False
            and class_manifest.get("scope_guardrails", {}).get(
                "root_lp_run"
            )
            is False
            and class_manifest.get("scope_guardrails", {}).get(
                "solver_run"
            )
            is False
            and class_manifest.get("scope_guardrails", {}).get(
                "proof_generated"
            )
            is False
            and class_manifest.get("scope_guardrails", {}).get(
                "verifier_run"
            )
            is False
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise CandidateCheckpointError(
            "profile-screening gate failed: " + ", ".join(failed)
        )
    audit = {
        "checkpoint_checksums": checksum_audit,
        "screening_manifest": {
            "path": "screening.manifest.json",
            "bytes": manifest_path.stat().st_size,
            "sha256": manifest_sha256,
        },
        "class_manifest": {
            "checkpoint": checkpoint.name,
            **class_entry["class_manifest"],
            "loaded_sha256": class_manifest_sha256,
        },
        "checks": checks,
        "all_checks_passed": True,
    }
    return audit, class_manifest


def _write_checksums(output_directory: Path) -> Path:
    checksum_path = output_directory / "SHA256SUMS"
    targets = sorted(
        (
            path
            for path in output_directory.rglob("*")
            if path.is_file() and path != checksum_path
        ),
        key=lambda path: path.relative_to(
            output_directory
        ).as_posix(),
    )
    checksum_path.write_text(
        "".join(
            f"{sha256_file(path)}  "
            f"{path.relative_to(output_directory).as_posix()}\n"
            for path in targets
        ),
        encoding="utf-8",
    )
    return checksum_path


def generate_candidate_formula_checkpoint(
    structural_census_directory: Path,
    profile_screening_directory: Path,
    class_index: int,
    output_directory: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Generate and independently audit one formula per candidate orbit."""

    class_index = int(class_index)
    if class_index < 1 or class_index > 68:
        raise CandidateCheckpointError(
            "class index must be between 1 and 68"
        )
    if output_directory.exists() and any(output_directory.iterdir()):
        raise CandidateCheckpointError(
            "candidate-formula checkpoint output directory must be empty"
        )

    (
        structural_audit,
        structural,
        input_path,
        input_artifact,
        structural_class_artifact,
    ) = _audit_structural_input(
        structural_census_directory,
        class_index,
    )
    screening_audit, screening_class_manifest = (
        _audit_profile_screening_gate(
            profile_screening_directory,
            class_index,
            structural_audit,
            structural,
        )
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    corpus_directory = output_directory / "corpus"
    _, corpus = generate_candidate_screening_corpus(
        structural,
        corpus_directory,
    )
    audit = audit_candidate_formula_corpus(
        input_path,
        corpus_directory,
        input_artifact=input_artifact,
    )
    if audit["status"] != "PASS":
        raise CandidateCheckpointError(
            "independent candidate formula audit failed"
        )
    audit_path = output_directory / "independent-audit.json"
    write_json(audit_path, audit)
    write_sha256_sidecar(audit_path)

    candidate_decisions = {
        int(row["orbit_index"]): row
        for row in screening_class_manifest[
            "candidate_orbit_screening"
        ]["decisions"]
    }
    comparisons = {
        int(row["orbit_index"]): row
        for row in audit["comparisons"]
    }
    instances = []
    for record in corpus["instances"]:
        orbit_index = int(record["orbit_index"])
        decision = candidate_decisions[orbit_index]
        comparison = comparisons[orbit_index]
        instances.append(
            {
                "orbit_index": orbit_index,
                "candidate_minimum_points": record[
                    "candidate_minimum_points"
                ],
                "candidate_orbit": record["candidate_orbit"],
                "screening_gate": {
                    "prior_disposition": decision["disposition"],
                    "prior_evidence_status": decision[
                        "evidence_status"
                    ],
                    "prior_rule_id": decision["rule_id"],
                },
                "formula": record["formula"],
                "metadata": record["metadata"],
                "independent_audit": {
                    "passed": comparison["passed"],
                    "rows_equal_in_order": comparison["checks"][
                        "rows_equal_in_order"
                    ],
                    "canonical_formula_hash_equal": comparison[
                        "checks"
                    ]["independent_canonical_hash_equal"],
                    "native_formula_hash_equal": comparison["checks"][
                        "native_formula_hash_equal"
                    ],
                },
                "status_ledger": {
                    "formula": "FORMULAS_GENERATED",
                    "direct_containment": "NOT_STARTED",
                    "root_lp": "NOT_STARTED",
                    "solver": "NOT_STARTED",
                    "proof": "NOT_STARTED",
                    "verification": "NOT_STARTED",
                },
                "formal_pruning_authorized": False,
            }
        )

    expected_indices = list(
        range(
            structural["candidate_minimum_point_sets"][
                "orbit_count"
            ]
        )
    )
    observed_indices = [
        record["orbit_index"] for record in instances
    ]
    all_accounted_for = observed_indices == expected_indices
    all_audited = all(
        row["independent_audit"]["passed"] for row in instances
    )
    if not all_accounted_for or not all_audited:
        raise CandidateCheckpointError(
            "a candidate orbit disappeared or failed its audit"
        )

    phase_manifest = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "producer": {
            "name": "horizonlink",
            "version": __version__,
        },
        "status": "FORMULAS_GENERATED",
        "input": {
            "class_index": class_index,
            "numbering_source": structural["input"][
                "numbering_source"
            ],
            "canonical_document_sha256": structural["input"][
                "canonical_document_sha256"
            ],
            "canonical_labeled_link_sha256": structural["input"][
                "canonical_labeled_link_sha256"
            ],
            "structural_census": structural_audit,
            "structural_class_artifact": (
                structural_class_artifact
            ),
            "profile_screening": screening_audit,
        },
        "model": {
            "id": "candidate-minimum-set-native-opb-v1",
            "role": "necessary-condition candidate-orbit screen",
            "variable_count": corpus["variable_count"],
            "candidate_orbit_partition_sha256": corpus["input"][
                "candidate_orbit_partition_sha256"
            ],
            "historical_semantics": (
                "legacy_source/full_minpoints.py"
            ),
            "formal_pruning_requires": "VERIFIED_UNSAT",
        },
        "artifacts": {
            "candidate_corpus_manifest": {
                "path": "corpus/corpus.manifest.json",
                "bytes": (
                    corpus_directory / "corpus.manifest.json"
                ).stat().st_size,
                "sha256": sha256_file(
                    corpus_directory / "corpus.manifest.json"
                ),
            },
            "independent_audit": {
                "path": "independent-audit.json",
                "bytes": audit_path.stat().st_size,
                "sha256": sha256_file(audit_path),
            },
        },
        "instances": instances,
        "summary": {
            "candidate_orbits": len(expected_indices),
            "formulas_generated": len(instances),
            "independent_formula_audits_passed": sum(
                row["independent_audit"]["passed"]
                for row in instances
            ),
            "all_candidate_orbits_accounted_for": (
                all_accounted_for
            ),
            "all_serialized_rows_audited_equal": all_audited,
            "orbit_indices": observed_indices,
            "unique_native_formula_hashes": len(
                {row["formula"]["sha256"] for row in instances}
            ),
            "unique_canonical_formula_hashes": len(
                {
                    row["formula"]["canonical_formula_sha256"]
                    for row in instances
                }
            ),
            "total_native_formula_bytes": sum(
                row["formula"]["bytes"] for row in instances
            ),
        },
        "status_ledger": {
            "structural_checkpoint_audit": "ENUMERATED",
            "profile_screening_gate": "ENUMERATED",
            "candidate_formulas": "FORMULAS_GENERATED",
            "independent_formula_audit": "FORMULAS_GENERATED",
            "direct_containment": "NOT_STARTED",
            "root_lp": "NOT_STARTED",
            "solver": "NOT_STARTED",
            "proof": "NOT_STARTED",
            "verification": "NOT_STARTED",
        },
        "scope_guardrails": {
            "only_requested_class_processed": True,
            "all_candidate_orbits_accounted_for": True,
            "formulas_generated": True,
            "direct_containment_run": False,
            "root_lp_run": False,
            "solver_run": False,
            "proof_generated": False,
            "verifier_run": False,
            "formal_orbit_pruning_authorized": False,
            "class_elimination_claimed": False,
            "C_13_7_4_equals_30_claimed": False,
        },
    }
    phase_path = output_directory / "phase.manifest.json"
    write_json(phase_path, phase_manifest)
    write_sha256_sidecar(phase_path)
    _write_checksums(output_directory)
    temporary_files = sorted(
        path.relative_to(output_directory).as_posix()
        for path in output_directory.rglob("*.tmp")
    )
    if temporary_files:
        raise CandidateCheckpointError(
            "temporary output artifacts remain: "
            + ", ".join(temporary_files)
        )
    return phase_manifest, corpus, audit
