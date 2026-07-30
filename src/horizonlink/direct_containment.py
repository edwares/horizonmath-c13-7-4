"""Deterministic direct-containment contradiction scans.

For a lower row

    sum(i in S) x_i >= L

and an upper row

    sum(i in T) x_i <= U,

if ``S`` is contained in ``T`` and ``L > U``, the two rows are already
inconsistent over nonnegative Boolean variables.  After normalizing the upper
row to ``-sum(i in T) x_i >= -U``, adding the rows gives

    -sum(i in T \\ S) x_i >= L - U > 0,

which is a cutting-planes contradiction.  This is the short proof method used
by the published class-52 ``pair12_eq9`` through ``pair12_eq14`` certificates.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from horizonlink import __version__
from horizonlink.canonical import (
    sha256_bytes,
    sha256_file,
    write_json,
    write_sha256_sidecar,
)
from horizonlink.direct_containment_audit import (
    audit_direct_containment_scan,
)


CHECKPOINT_SCHEMA_VERSION = (
    "horizonmath.direct-containment-checkpoint.v1"
)
SCAN_SCHEMA_VERSION = "horizonmath.direct-containment-scan.v1"
INPUT_CHECKPOINT_SCHEMA_VERSION = (
    "horizonmath.candidate-formula-checkpoint.v1"
)
INPUT_CORPUS_SCHEMA_VERSION = (
    "horizonmath.candidate-screening-pb-corpus.v1"
)
HEADER_RE = re.compile(
    r"^\* #variable= (?P<variables>[0-9]+) "
    r"#constraint= (?P<constraints>[0-9]+)$"
)
ROW_RE = re.compile(
    r"^(?P<terms>(?:\+1 x[1-9][0-9]* ?)+)"
    r"(?P<relation>>=|<=) (?P<rhs>-?[0-9]+) ;$"
)
TERM_RE = re.compile(r"\+1 x([1-9][0-9]*)")


class DirectContainmentError(ValueError):
    """Raised when a direct-containment phase fails closed."""


class _DuplicateKeyError(ValueError):
    pass


@dataclass(frozen=True)
class ContainmentRow:
    """One parsed unit-coefficient native OPB row."""

    variables: tuple[int, ...]  # one-based OPB variable identifiers
    relation: str
    rhs: int
    family: str | None = None
    subject: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if self.relation not in {">=", "<="}:
            raise ValueError("containment row relation must be >= or <=")
        if tuple(sorted(set(self.variables))) != self.variables:
            raise ValueError(
                "containment row variables must be unique and increasing"
            )
        if not self.variables or self.variables[0] < 1:
            raise ValueError(
                "containment row variables must use positive OPB identifiers"
            )


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
        raise DirectContainmentError(
            f"cannot load {path.name}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise DirectContainmentError(
            f"{path.name} must contain a JSON object"
        )
    return value, sha256_bytes(raw)


def _safe_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise DirectContainmentError(
            f"unsafe checkpoint path: {relative!r}"
        )
    path = root.joinpath(*pure.parts)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise DirectContainmentError(
            f"checkpoint path escapes root: {relative!r}"
        ) from exc
    return path


def _verify_checkpoint_checksums(checkpoint: Path) -> dict[str, Any]:
    checksum_path = checkpoint / "SHA256SUMS"
    try:
        lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise DirectContainmentError(
            f"cannot read candidate checkpoint checksums: {exc}"
        ) from exc

    recorded: list[str] = []
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
            raise DirectContainmentError(
                f"invalid candidate SHA256SUMS row {line_number}"
            )
        expected, relative = parts
        if relative in seen:
            raise DirectContainmentError(
                f"duplicate candidate SHA256SUMS path: {relative}"
            )
        seen.add(relative)
        path = _safe_path(checkpoint, relative)
        if not path.is_file():
            raise DirectContainmentError(
                f"missing candidate checkpoint artifact: {relative}"
            )
        if sha256_file(path) != expected:
            raise DirectContainmentError(
                f"candidate checkpoint hash mismatch: {relative}"
            )
        recorded.append(relative)

    observed = sorted(
        path.relative_to(checkpoint).as_posix()
        for path in checkpoint.rglob("*")
        if path.is_file() and path != checksum_path
    )
    if sorted(recorded) != observed:
        raise DirectContainmentError(
            "candidate SHA256SUMS does not account for every file"
        )
    return {
        "status": "PASS",
        "directory_name": checkpoint.name,
        "sha256sums_sha256": sha256_file(checksum_path),
        "recorded_file_count": len(recorded),
        "all_recorded_hashes_match": True,
        "every_checkpoint_file_accounted_for": True,
    }


def _resolve_artifact(
    root: Path,
    artifact: dict[str, Any],
    label: str,
) -> Path:
    try:
        relative = artifact["path"]
        expected_bytes = int(artifact["bytes"])
        expected_hash = artifact["sha256"]
    except (KeyError, TypeError, ValueError) as exc:
        raise DirectContainmentError(
            f"{label} artifact record is incomplete"
        ) from exc
    path = _safe_path(root, relative)
    if not path.is_file():
        raise DirectContainmentError(
            f"{label} artifact is missing: {relative}"
        )
    if path.stat().st_size != expected_bytes:
        raise DirectContainmentError(
            f"{label} artifact byte count mismatch"
        )
    if sha256_file(path) != expected_hash:
        raise DirectContainmentError(
            f"{label} artifact hash mismatch"
        )
    return path


def _parse_native_opb(
    path: Path,
    family_counts: dict[str, int],
) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise DirectContainmentError(
            f"cannot read {path.name}: {exc}"
        ) from exc
    if not lines:
        raise DirectContainmentError(f"{path.name} is empty")
    header = HEADER_RE.fullmatch(lines[0])
    if header is None:
        raise DirectContainmentError(
            f"{path.name}: malformed native OPB header"
        )

    rows: list[ContainmentRow] = []
    comments: list[str] = []
    for line_number, raw_line in enumerate(lines[1:], start=2):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("*"):
            comments.append(line)
            continue
        match = ROW_RE.fullmatch(line)
        if match is None:
            raise DirectContainmentError(
                f"{path.name}:{line_number}: unsupported native OPB row"
            )
        variables = tuple(
            int(value) for value in TERM_RE.findall(match.group("terms"))
        )
        rows.append(
            ContainmentRow(
                variables,
                match.group("relation"),
                int(match.group("rhs")),
            )
        )

    family_order = (
        "residual_four_coverage",
        "candidate_point_degree",
        "pair_degree_lower",
        "triple_degree_lower",
        "extension_block_count",
    )
    if set(family_counts) != set(family_order):
        raise DirectContainmentError(
            f"{path.name}: unsupported serialized row families"
        )
    expected_family_count = sum(
        int(family_counts[family]) for family in family_order
    )
    if expected_family_count != len(rows):
        raise DirectContainmentError(
            f"{path.name}: family counts do not cover every row"
        )
    annotated: list[ContainmentRow] = []
    cursor = 0
    for family in family_order:
        count = int(family_counts[family])
        for row in rows[cursor : cursor + count]:
            annotated.append(
                ContainmentRow(
                    row.variables,
                    row.relation,
                    row.rhs,
                    family,
                )
            )
        cursor += count

    return {
        "variable_count": int(header.group("variables")),
        "declared_constraint_count": int(
            header.group("constraints")
        ),
        "comments": comments,
        "rows": tuple(annotated),
    }


def _support_sha256(variables: Iterable[int]) -> str:
    payload = json.dumps(
        list(variables),
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


def _serialize_witness(
    lower_id: int,
    lower: ContainmentRow,
    upper_id: int,
    upper: ContainmentRow,
) -> dict[str, Any]:
    lower_set = frozenset(lower.variables)
    upper_set = frozenset(upper.variables)
    difference = tuple(sorted(upper_set - lower_set))
    gap = lower.rhs - upper.rhs
    return {
        "lower_row": {
            "id_1based": lower_id,
            "relation": lower.relation,
            "rhs": lower.rhs,
            "support_size": len(lower.variables),
            "support_sha256": _support_sha256(lower.variables),
            "family": lower.family,
            "subject": (
                list(lower.subject)
                if lower.subject is not None
                else None
            ),
        },
        "upper_row": {
            "id_1based": upper_id,
            "relation": upper.relation,
            "rhs": upper.rhs,
            "support_size": len(upper.variables),
            "support_sha256": _support_sha256(upper.variables),
            "family": upper.family,
            "subject": (
                list(upper.subject)
                if upper.subject is not None
                else None
            ),
        },
        "support_relation": (
            "LOWER_SUPPORT_SUBSET_OF_UPPER_SUPPORT"
        ),
        "support_difference_variable_ids_1based": list(difference),
        "contradiction_gap": gap,
        "derived_inequality": {
            "negative_unit_variables_1based": list(difference),
            "rhs": gap,
            "interpretation": (
                "-sum(difference variables) >= contradiction_gap"
            ),
        },
        "exact_checks": {
            "lower_relation_is_greater_equal": (
                lower.relation == ">="
            ),
            "upper_relation_is_less_equal": (
                upper.relation == "<="
            ),
            "lower_support_is_subset": lower_set <= upper_set,
            "lower_rhs_strictly_exceeds_upper_rhs": gap > 0,
            "derived_coefficients_are_nonpositive": True,
            "derived_rhs_is_strictly_positive": gap > 0,
        },
    }


def scan_direct_containment_rows(
    rows: Iterable[ContainmentRow],
) -> dict[str, Any]:
    """Exhaustively scan all lower/upper row pairs."""

    normalized = tuple(rows)
    lowers = [
        (row_id, row)
        for row_id, row in enumerate(normalized, start=1)
        if row.relation == ">="
    ]
    uppers = [
        (row_id, row)
        for row_id, row in enumerate(normalized, start=1)
        if row.relation == "<="
    ]
    containments = 0
    gap_histogram: Counter[int] = Counter()
    witnesses: list[dict[str, Any]] = []
    for lower_id, lower in lowers:
        lower_set = frozenset(lower.variables)
        for upper_id, upper in uppers:
            upper_set = frozenset(upper.variables)
            if not lower_set <= upper_set:
                continue
            containments += 1
            gap = lower.rhs - upper.rhs
            gap_histogram[gap] += 1
            if gap > 0:
                witnesses.append(
                    _serialize_witness(
                        lower_id,
                        lower,
                        upper_id,
                        upper,
                    )
                )
    witnesses.sort(
        key=lambda row: (
            row["lower_row"]["id_1based"],
            row["upper_row"]["id_1based"],
        )
    )
    return {
        "lower_rows": len(lowers),
        "upper_rows": len(uppers),
        "row_pairs_tested": len(lowers) * len(uppers),
        "support_containments": containments,
        "containment_gap_histogram": {
            str(gap): count
            for gap, count in sorted(gap_histogram.items())
        },
        "maximum_containment_gap": (
            max(gap_histogram) if gap_histogram else None
        ),
        "contradictions_found": len(witnesses),
        "witnesses": witnesses,
    }


def render_verifier_normalized_opb(
    rows: Iterable[ContainmentRow],
    *,
    variable_count: int,
    source_name: str,
) -> bytes:
    """Render all rows as ``>=`` while preserving row identifiers."""

    normalized = tuple(rows)
    lines = [
        (
            f"* #variable= {variable_count} "
            f"#constraint= {len(normalized)}"
        ),
        f"* source formula {source_name}",
        (
            "* verifier-normalized for direct containment; "
            "constraint ids preserved"
        ),
    ]
    for row in normalized:
        coefficient = 1 if row.relation == ">=" else -1
        rhs = row.rhs if row.relation == ">=" else -row.rhs
        terms = " ".join(
            f"{coefficient:+d} x{variable}"
            for variable in row.variables
        )
        lines.append(f"{terms} >= {rhs} ;")
    return ("\n".join(lines) + "\n").encode("utf-8")


def render_direct_containment_proof(
    formula_constraint_count: int,
    witness: dict[str, Any],
) -> bytes:
    """Render the four-line cutting-planes proof for one witness."""

    upper_id = int(witness["upper_row"]["id_1based"])
    lower_id = int(witness["lower_row"]["id_1based"])
    lines = [
        "pseudo-Boolean proof version 1.0",
        f"f {formula_constraint_count}",
        f"p {upper_id} {lower_id} +",
        f"c {formula_constraint_count + 1}",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


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


def _audit_candidate_checkpoint(
    candidate_checkpoint_directory: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    checksum_audit = _verify_checkpoint_checksums(
        candidate_checkpoint_directory
    )
    phase_path = (
        candidate_checkpoint_directory / "phase.manifest.json"
    )
    phase, phase_hash = _load_json_object(phase_path)
    if (
        phase.get("schema_version")
        != INPUT_CHECKPOINT_SCHEMA_VERSION
        or phase.get("status") != "FORMULAS_GENERATED"
    ):
        raise DirectContainmentError(
            "candidate checkpoint schema or status is invalid"
        )
    if not phase.get("summary", {}).get(
        "all_candidate_orbits_accounted_for"
    ) or not phase.get("summary", {}).get(
        "all_serialized_rows_audited_equal"
    ):
        raise DirectContainmentError(
            "candidate checkpoint is not completely audited"
        )
    scope = phase.get("scope_guardrails", {})
    if (
        scope.get("direct_containment_run") is not False
        or scope.get("root_lp_run") is not False
        or scope.get("solver_run") is not False
        or scope.get("proof_generated") is not False
        or scope.get("verifier_run") is not False
    ):
        raise DirectContainmentError(
            "candidate checkpoint stage boundaries are invalid"
        )

    audit_path = _resolve_artifact(
        candidate_checkpoint_directory,
        phase["artifacts"]["independent_audit"],
        "independent candidate-formula audit",
    )
    candidate_audit, candidate_audit_hash = _load_json_object(
        audit_path
    )
    if (
        candidate_audit.get("status") != "PASS"
        or not candidate_audit.get("summary", {}).get(
            "all_rows_equal_in_order"
        )
    ):
        raise DirectContainmentError(
            "independent candidate-formula audit did not pass"
        )

    corpus_path = _resolve_artifact(
        candidate_checkpoint_directory,
        phase["artifacts"]["candidate_corpus_manifest"],
        "candidate corpus manifest",
    )
    corpus, corpus_hash = _load_json_object(corpus_path)
    if (
        corpus.get("schema_version") != INPUT_CORPUS_SCHEMA_VERSION
        or corpus.get("status") != "FORMULAS_GENERATED"
        or not corpus.get("summary", {}).get(
            "all_orbits_accounted_for"
        )
    ):
        raise DirectContainmentError(
            "candidate corpus schema or status is invalid"
        )

    phase_instances = {
        int(row["orbit_index"]): row
        for row in phase.get("instances", [])
    }
    corpus_instances = {
        int(row["orbit_index"]): row
        for row in corpus.get("instances", [])
    }
    expected_indices = phase["summary"]["orbit_indices"]
    if (
        expected_indices != list(range(len(expected_indices)))
        or sorted(phase_instances) != expected_indices
        or sorted(corpus_instances) != expected_indices
    ):
        raise DirectContainmentError(
            "candidate orbit inventory is incomplete"
        )
    for orbit_index in expected_indices:
        left = phase_instances[orbit_index]
        right = corpus_instances[orbit_index]
        if (
            left["candidate_minimum_points"]
            != right["candidate_minimum_points"]
            or left["formula"] != right["formula"]
            or left["status_ledger"]["direct_containment"]
            != "NOT_STARTED"
            or left["status_ledger"]["root_lp"] != "NOT_STARTED"
            or left["status_ledger"]["solver"] != "NOT_STARTED"
            or left["status_ledger"]["proof"] != "NOT_STARTED"
            or left["status_ledger"]["verification"] != "NOT_STARTED"
            or left["formal_pruning_authorized"] is not False
        ):
            raise DirectContainmentError(
                f"candidate orbit {orbit_index} boundary mismatch"
            )

    input_audit = {
        "checkpoint_checksums": checksum_audit,
        "phase_manifest": {
            "path": "phase.manifest.json",
            "bytes": phase_path.stat().st_size,
            "sha256": phase_hash,
        },
        "independent_formula_audit": {
            "path": phase["artifacts"]["independent_audit"]["path"],
            "bytes": audit_path.stat().st_size,
            "sha256": candidate_audit_hash,
            "status": candidate_audit["status"],
        },
        "candidate_corpus_manifest": {
            "path": phase["artifacts"][
                "candidate_corpus_manifest"
            ]["path"],
            "bytes": corpus_path.stat().st_size,
            "sha256": corpus_hash,
            "status": corpus["status"],
        },
        "checks": {
            "checkpoint_checksums_passed": True,
            "candidate_checkpoint_schema_supported": True,
            "candidate_checkpoint_status_formula_generated": True,
            "all_candidate_orbits_accounted_for": True,
            "all_serialized_rows_previously_audited": True,
            "independent_formula_audit_passed": True,
            "candidate_corpus_schema_supported": True,
            "candidate_corpus_status_formula_generated": True,
            "prior_direct_containment_not_started": True,
            "prior_lp_solver_proof_verifier_not_started": True,
        },
        "all_checks_passed": True,
    }
    return input_audit, phase, corpus


def generate_direct_containment_checkpoint(
    candidate_checkpoint_directory: Path,
    output_directory: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Scan every candidate formula and independently audit the result."""

    if output_directory.exists() and any(output_directory.iterdir()):
        raise DirectContainmentError(
            "direct-containment output directory must be empty"
        )
    input_audit, candidate_phase, corpus = (
        _audit_candidate_checkpoint(candidate_checkpoint_directory)
    )
    class_index = int(candidate_phase["input"]["class_index"])
    corpus_root = candidate_checkpoint_directory / "corpus"
    output_directory.mkdir(parents=True, exist_ok=True)
    instance_directory = output_directory / "instances"
    instance_directory.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for source in corpus["instances"]:
        orbit_index = int(source["orbit_index"])
        name = source["name"]
        formula_path = _safe_path(
            corpus_root,
            source["formula"]["path"],
        )
        if (
            not formula_path.is_file()
            or formula_path.stat().st_size
            != source["formula"]["bytes"]
            or sha256_file(formula_path)
            != source["formula"]["sha256"]
        ):
            raise DirectContainmentError(
                f"source formula mismatch for orbit {orbit_index}"
            )
        parsed = _parse_native_opb(
            formula_path,
            source["formula"]["serialized_family_counts"],
        )
        if (
            parsed["variable_count"]
            != source["formula"]["variables"]
            or parsed["declared_constraint_count"]
            != len(parsed["rows"])
            or len(parsed["rows"])
            != source["formula"]["opb_constraints"]
        ):
            raise DirectContainmentError(
                f"source formula header mismatch for orbit {orbit_index}"
            )

        scan = scan_direct_containment_rows(parsed["rows"])
        contradiction_found = scan["contradictions_found"] > 0
        normalized_artifact = None
        proof_artifact = None
        selected_witness = None
        if contradiction_found:
            selected_witness = scan["witnesses"][0]
            normalized_path = (
                instance_directory
                / f"{name}.direct-containment.opb"
            )
            normalized_path.write_bytes(
                render_verifier_normalized_opb(
                    parsed["rows"],
                    variable_count=parsed["variable_count"],
                    source_name=formula_path.name,
                )
            )
            proof_path = (
                instance_directory
                / f"{name}.direct-containment.pbp"
            )
            proof_path.write_bytes(
                render_direct_containment_proof(
                    len(parsed["rows"]),
                    selected_witness,
                )
            )
            normalized_artifact = {
                "path": normalized_path.relative_to(
                    output_directory
                ).as_posix(),
                "bytes": normalized_path.stat().st_size,
                "sha256": sha256_file(normalized_path),
                "constraint_ids_preserved": True,
                "native_less_equal_rows_sign_reversed": (
                    scan["upper_rows"]
                ),
            }
            proof_artifact = {
                "path": proof_path.relative_to(
                    output_directory
                ).as_posix(),
                "bytes": proof_path.stat().st_size,
                "sha256": sha256_file(proof_path),
                "rules": 4,
                "requires_verification": True,
            }

        record = {
            "name": name,
            "class_index": class_index,
            "orbit_index": orbit_index,
            "candidate_minimum_points": source[
                "candidate_minimum_points"
            ],
            "source_formula": {
                "path": (
                    "corpus/" + source["formula"]["path"]
                ),
                "bytes": formula_path.stat().st_size,
                "sha256": sha256_file(formula_path),
                "canonical_formula_sha256": source["formula"][
                    "canonical_formula_sha256"
                ],
                "normalized_native_row_sha256": source["formula"][
                    "normalized_native_row_sha256"
                ],
                "variables": parsed["variable_count"],
                "constraints": len(parsed["rows"]),
            },
            "scan": scan,
            "selected_witness": selected_witness,
            "artifacts": {
                "verifier_normalized_formula": normalized_artifact,
                "proof": proof_artifact,
            },
            "result": {
                "disposition": (
                    "DIRECT_CONTAINMENT_CONTRADICTION_FOUND"
                    if contradiction_found
                    else "SURVIVED_DIRECT_CONTAINMENT_SCAN"
                ),
                "evidence_status": (
                    "PROOF_GENERATED"
                    if contradiction_found
                    else "NO_CONTRADICTION_FOUND"
                ),
                "mathematical_reason": (
                    "A lower-row support is contained in an upper-row "
                    "support and its lower bound strictly exceeds the "
                    "upper bound."
                    if contradiction_found
                    else "No serialized >= row has support contained in a "
                    "serialized <= row with a strictly larger right-hand "
                    "side."
                ),
            },
            "status_ledger": {
                "formula": "FORMULAS_GENERATED",
                "direct_containment": (
                    "PROOF_GENERATED"
                    if contradiction_found
                    else "ENUMERATED"
                ),
                "root_lp": "NOT_STARTED",
                "solver": "NOT_STARTED",
                "proof": (
                    "PROOF_GENERATED"
                    if contradiction_found
                    else "NOT_STARTED"
                ),
                "verification": "NOT_STARTED",
            },
            "formal_pruning_authorized": False,
        }
        metadata_path = (
            instance_directory
            / f"{name}.direct-containment.json"
        )
        write_json(metadata_path, record)
        record["metadata"] = {
            "path": metadata_path.relative_to(
                output_directory
            ).as_posix(),
            "bytes": metadata_path.stat().st_size,
            "sha256": sha256_file(metadata_path),
        }
        records.append(record)

    expected_indices = candidate_phase["summary"]["orbit_indices"]
    observed_indices = [row["orbit_index"] for row in records]
    if observed_indices != expected_indices:
        raise DirectContainmentError(
            "direct-containment scan lost a candidate orbit"
        )
    proof_indices = [
        row["orbit_index"]
        for row in records
        if row["scan"]["contradictions_found"] > 0
    ]
    survivor_indices = [
        row["orbit_index"]
        for row in records
        if row["scan"]["contradictions_found"] == 0
    ]
    scan_manifest = {
        "schema_version": SCAN_SCHEMA_VERSION,
        "status": (
            "PROOF_GENERATED" if proof_indices else "ENUMERATED"
        ),
        "producer": {
            "package": "horizonlink",
            "version": __version__,
            "command": "scan-direct-containment",
        },
        "input": {
            "class_index": class_index,
            "numbering_source": candidate_phase["input"][
                "numbering_source"
            ],
            "canonical_labeled_link_sha256": candidate_phase[
                "input"
            ]["canonical_labeled_link_sha256"],
            "candidate_orbit_partition_sha256": candidate_phase[
                "model"
            ]["candidate_orbit_partition_sha256"],
            "candidate_checkpoint": input_audit,
        },
        "method": {
            "id": "unit-support-direct-containment-cp-v1",
            "criterion": (
                "For every native lower row sum(S)>=L and upper row "
                "sum(T)<=U, test S subseteq T and L>U."
            ),
            "exhaustive_pair_order": (
                "lower rows by one-based formula id, then upper rows by "
                "one-based formula id"
            ),
            "proof_rule": (
                "Normalize the upper row by sign reversal, add it to the "
                "lower row, and declare the resulting nonpositive-left, "
                "positive-right inequality contradictory."
            ),
            "proof_format": "VeriPB pseudo-Boolean proof version 1.0",
            "runtime_dependencies": [],
        },
        "instances": records,
        "summary": {
            "candidate_orbits_expected": len(expected_indices),
            "candidate_orbits_scanned": len(records),
            "all_candidate_orbits_accounted_for": (
                observed_indices == expected_indices
            ),
            "orbit_indices": observed_indices,
            "direct_contradictions_found": len(proof_indices),
            "proofs_generated": len(proof_indices),
            "survivors": len(survivor_indices),
            "proof_orbit_indices": proof_indices,
            "survivor_orbit_indices": survivor_indices,
            "total_row_pairs_tested": sum(
                row["scan"]["row_pairs_tested"]
                for row in records
            ),
            "total_support_containments": sum(
                row["scan"]["support_containments"]
                for row in records
            ),
        },
        "status_ledger": {
            "candidate_formulas": "FORMULAS_GENERATED",
            "direct_containment": (
                "PROOF_GENERATED" if proof_indices else "ENUMERATED"
            ),
            "root_lp": "NOT_STARTED",
            "solver": "NOT_STARTED",
            "proof": (
                "PROOF_GENERATED"
                if proof_indices
                else "NOT_STARTED"
            ),
            "verification": "NOT_STARTED",
        },
        "scope_guardrails": {
            "all_candidate_orbits_accounted_for": True,
            "direct_containment_run": True,
            "root_lp_run": False,
            "solver_run": False,
            "verifier_run": False,
            "proof_generated": bool(proof_indices),
            "formal_orbit_pruning_authorized": False,
            "class_elimination_claimed": False,
            "C_13_7_4_equals_30_claimed": False,
        },
    }
    scan_path = output_directory / "scan.manifest.json"
    write_json(scan_path, scan_manifest)
    write_sha256_sidecar(scan_path)

    audit = audit_direct_containment_scan(
        candidate_checkpoint_directory,
        output_directory,
    )
    if audit["status"] != "PASS":
        raise DirectContainmentError(
            "independent direct-containment audit failed"
        )
    audit_path = output_directory / "independent-audit.json"
    write_json(audit_path, audit)
    write_sha256_sidecar(audit_path)

    phase_manifest = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "status": scan_manifest["status"],
        "producer": scan_manifest["producer"],
        "input": scan_manifest["input"],
        "method": scan_manifest["method"],
        "summary": {
            **scan_manifest["summary"],
            "independent_comparisons_passed": audit["summary"][
                "comparisons_passed"
            ],
            "all_scan_results_independently_recomputed": audit[
                "summary"
            ]["all_scan_results_equal"],
        },
        "status_ledger": scan_manifest["status_ledger"],
        "scope_guardrails": scan_manifest["scope_guardrails"],
        "artifacts": {
            "scan_manifest": {
                "path": "scan.manifest.json",
                "bytes": scan_path.stat().st_size,
                "sha256": sha256_file(scan_path),
            },
            "independent_audit": {
                "path": "independent-audit.json",
                "bytes": audit_path.stat().st_size,
                "sha256": sha256_file(audit_path),
            },
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
        raise DirectContainmentError(
            "temporary output artifacts remain: "
            + ", ".join(temporary_files)
        )
    return phase_manifest, scan_manifest, audit
