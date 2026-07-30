"""Corrected native pseudo-Boolean model construction and serialization."""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from horizonlink.canonical import sha256_bytes


@dataclass(frozen=True)
class PBRow:
    """A unit-coefficient pseudo-Boolean inequality."""

    variables: tuple[int, ...]  # zero-based indices in the extension-block list
    relation: str
    rhs: int
    family: str
    subject: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if self.relation not in {">=", "<="}:
            raise ValueError("PB relation must be >= or <=")
        if tuple(sorted(set(self.variables))) != self.variables:
            raise ValueError("PB variables must be unique and sorted")


@dataclass(frozen=True)
class BoundedRow:
    """One mathematical row before finite bounds are serialized separately."""

    variables: tuple[int, ...]
    lower: int | None
    upper: int | None
    family: str
    subject: tuple[int, ...] | None = None

    def expand(self) -> tuple[PBRow, ...]:
        rows = []
        if self.lower is not None:
            rows.append(
                PBRow(
                    self.variables,
                    ">=",
                    self.lower,
                    self.family,
                    self.subject,
                )
            )
        if self.upper is not None:
            rows.append(
                PBRow(
                    self.variables,
                    "<=",
                    self.upper,
                    self.family,
                    self.subject,
                )
            )
        return tuple(rows)


def extension_blocks(
    point_labels: tuple[int, ...], extension_block_size: int = 7
) -> tuple[tuple[int, ...], ...]:
    return tuple(itertools.combinations(point_labels, extension_block_size))


def _containing_variables(
    block_sets: tuple[frozenset[int], ...],
    subset: Iterable[int],
) -> tuple[int, ...]:
    target = frozenset(subset)
    return tuple(
        index for index, block in enumerate(block_sets) if target <= block
    )


def _multiplicity(
    block_sets: tuple[frozenset[int], ...],
    subset: Iterable[int],
) -> int:
    target = frozenset(subset)
    return sum(target <= block for block in block_sets)


def build_candidate_minimum_set_formula(
    point_labels: tuple[int, ...],
    link_blocks: tuple[tuple[int, ...], ...],
    candidate_minimum_points: Iterable[int],
    *,
    target_full_point_degree: int = 15,
    extension_block_count: int = 14,
    extension_block_size: int = 7,
    pair_cover_minimum: int = 7,
    triple_cover_minimum: int = 3,
) -> dict[str, Any]:
    """Build the historical candidate-minimum-point screening model.

    Every point has full degree at least ``target_full_point_degree``.  The
    selected candidate points are additionally fixed to that full degree.
    The model also enforces residual four-set coverage, the pair and triple
    lower bounds implied by a 29-block covering, and the exact number of
    extension blocks.

    This is a necessary-condition model.  Infeasibility may prune a candidate
    orbit only after a formal certificate has been verified.
    """

    normalized_candidate = tuple(
        sorted(set(int(point) for point in candidate_minimum_points))
    )
    point_set = frozenset(point_labels)
    if not normalized_candidate:
        raise ValueError("candidate minimum-point set must be nonempty")
    if not frozenset(normalized_candidate) <= point_set:
        raise ValueError("candidate minimum-point set contains an unknown point")

    blocks = extension_blocks(point_labels, extension_block_size)
    block_sets = tuple(frozenset(block) for block in blocks)
    link_sets = tuple(frozenset(block) for block in link_blocks)
    link_point_degrees = tuple(
        _multiplicity(link_sets, (point,)) for point in point_labels
    )
    minimum_extension_degrees = tuple(
        target_full_point_degree - degree for degree in link_point_degrees
    )
    if any(degree < 0 for degree in minimum_extension_degrees):
        raise ValueError("a link point degree exceeds the target full degree")

    covered_fours = {
        four
        for block in link_blocks
        for four in itertools.combinations(block, 4)
    }
    residual_fours = tuple(
        four
        for four in itertools.combinations(point_labels, 4)
        if four not in covered_fours
    )

    bounded_rows: list[BoundedRow] = []
    for four in residual_fours:
        bounded_rows.append(
            BoundedRow(
                _containing_variables(block_sets, four),
                1,
                None,
                "residual_four_coverage",
                four,
            )
        )
    candidate_set = frozenset(normalized_candidate)
    for point, minimum_degree in zip(
        point_labels, minimum_extension_degrees
    ):
        bounded_rows.append(
            BoundedRow(
                _containing_variables(block_sets, (point,)),
                minimum_degree,
                minimum_degree if point in candidate_set else None,
                "candidate_point_degree",
                (point,),
            )
        )

    pair_rows = 0
    for pair in itertools.combinations(point_labels, 2):
        lower = pair_cover_minimum - _multiplicity(link_sets, pair)
        if lower <= 0:
            continue
        bounded_rows.append(
            BoundedRow(
                _containing_variables(block_sets, pair),
                lower,
                None,
                "pair_degree_lower",
                pair,
            )
        )
        pair_rows += 1

    triple_rows = 0
    for triple in itertools.combinations(point_labels, 3):
        lower = triple_cover_minimum - _multiplicity(link_sets, triple)
        if lower <= 0:
            continue
        bounded_rows.append(
            BoundedRow(
                _containing_variables(block_sets, triple),
                lower,
                None,
                "triple_degree_lower",
                triple,
            )
        )
        triple_rows += 1

    bounded_rows.append(
        BoundedRow(
            tuple(range(len(blocks))),
            extension_block_count,
            extension_block_count,
            "extension_block_count",
            None,
        )
    )
    rows = tuple(
        row for bounded in bounded_rows for row in bounded.expand()
    )
    family_counts: dict[str, int] = {}
    for row in rows:
        family_counts[row.family] = family_counts.get(row.family, 0) + 1

    return {
        "extension_blocks": blocks,
        "extension_block_sets": block_sets,
        "bounded_rows": tuple(bounded_rows),
        "rows": rows,
        "metadata": {
            "variables": len(blocks),
            "matrix_rows": len(bounded_rows),
            "opb_constraints": len(rows),
            "residual_four_sets": len(residual_fours),
            "point_rows": len(point_labels),
            "pair_rows": pair_rows,
            "triple_rows": triple_rows,
            "extension_block_count_rows": 1,
            "candidate_minimum_points": list(normalized_candidate),
            "candidate_minimum_point_count": len(normalized_candidate),
            "link_point_degrees": list(link_point_degrees),
            "minimum_extension_degrees": list(
                minimum_extension_degrees
            ),
            "serialized_family_counts": dict(sorted(family_counts.items())),
            "model_role": "necessary-condition candidate-orbit screen",
            "formal_pruning_requires": "VERIFIED_UNSAT",
        },
    }


def build_corrected_formula(
    point_labels: tuple[int, ...],
    link_blocks: tuple[tuple[int, ...], ...],
    extension_degrees: Iterable[int],
    *,
    extension_block_count: int = 14,
    extension_block_size: int = 7,
    pair_cover_minimum: int = 7,
    triple_cover_minimum: int = 3,
    split_pair: Iterable[int] | None = None,
    split_value: int | None = None,
) -> dict[str, Any]:
    """Build the corrected necessary-condition model.

    For full point degree ``r_i`` and fixed link pair multiplicity
    ``ell_ij``, the extension pair multiplicity ``y_ij`` has upper bound

    ``min(6*r_i - 70 - ell_ij, 6*r_j - 70 - ell_ij)``.

    The fixed link multiplicity is subtracted exactly once.
    """

    extension_degree_vector = tuple(int(value) for value in extension_degrees)
    if len(extension_degree_vector) != len(point_labels):
        raise ValueError("extension degree vector has wrong length")
    if sum(extension_degree_vector) != (
        extension_block_count * extension_block_size
    ):
        raise ValueError("extension degree vector has the wrong total")
    if (split_pair is None) != (split_value is None):
        raise ValueError("split pair and split value must be supplied together")

    blocks = extension_blocks(point_labels, extension_block_size)
    block_sets = tuple(frozenset(block) for block in blocks)
    link_sets = tuple(frozenset(block) for block in link_blocks)
    link_point_degrees = tuple(
        _multiplicity(link_sets, (point,)) for point in point_labels
    )
    full_point_degrees = tuple(
        link_point_degrees[index] + extension_degree_vector[index]
        for index in range(len(point_labels))
    )

    covered_fours = {
        four
        for block in link_blocks
        for four in itertools.combinations(block, 4)
    }
    residual_fours = tuple(
        four
        for four in itertools.combinations(point_labels, 4)
        if four not in covered_fours
    )

    bounded_rows: list[BoundedRow] = []
    for four in residual_fours:
        bounded_rows.append(
            BoundedRow(
                _containing_variables(block_sets, four),
                1,
                None,
                "residual_four_coverage",
                four,
            )
        )
    for point, degree in zip(point_labels, extension_degree_vector):
        bounded_rows.append(
            BoundedRow(
                _containing_variables(block_sets, (point,)),
                degree,
                degree,
                "point_degree",
                (point,),
            )
        )

    pair_bounds = []
    for pair in itertools.combinations(point_labels, 2):
        link_multiplicity = _multiplicity(link_sets, pair)
        lower = pair_cover_minimum - link_multiplicity
        first, second = pair
        upper = min(
            6 * full_point_degrees[first] - 70 - link_multiplicity,
            6 * full_point_degrees[second] - 70 - link_multiplicity,
        )
        pair_bounds.append(
            {
                "pair": list(pair),
                "link_multiplicity": link_multiplicity,
                "lower": lower,
                "upper": upper,
                "valid_interval": lower <= upper,
            }
        )
        bounded_rows.append(
            BoundedRow(
                _containing_variables(block_sets, pair),
                lower,
                upper,
                "pair_degree",
                pair,
            )
        )

    triple_rows = 0
    for triple in itertools.combinations(point_labels, 3):
        lower = triple_cover_minimum - _multiplicity(link_sets, triple)
        if lower <= 0:
            continue
        bounded_rows.append(
            BoundedRow(
                _containing_variables(block_sets, triple),
                lower,
                None,
                "triple_degree",
                triple,
            )
        )
        triple_rows += 1

    bounded_rows.append(
        BoundedRow(
            tuple(range(len(blocks))),
            extension_block_count,
            extension_block_count,
            "extension_block_count",
            None,
        )
    )
    normalized_split_pair = None
    if split_pair is not None:
        normalized_split_pair = tuple(sorted(int(point) for point in split_pair))
        if len(normalized_split_pair) != 2:
            raise ValueError("split pair must contain exactly two points")
        bounded_rows.append(
            BoundedRow(
                _containing_variables(block_sets, normalized_split_pair),
                int(split_value),
                int(split_value),
                "exact_pair_split",
                normalized_split_pair,
            )
        )

    rows = tuple(
        row
        for bounded in bounded_rows
        for row in bounded.expand()
    )
    family_counts: dict[str, int] = {}
    for row in rows:
        family_counts[row.family] = family_counts.get(row.family, 0) + 1
    return {
        "extension_blocks": blocks,
        "extension_block_sets": block_sets,
        "bounded_rows": tuple(bounded_rows),
        "rows": rows,
        "metadata": {
            "variables": len(blocks),
            "matrix_rows": len(bounded_rows),
            "opb_constraints": len(rows),
            "residual_four_sets": len(residual_fours),
            "point_rows": len(point_labels),
            "pair_rows": math_comb(len(point_labels), 2),
            "triple_rows": triple_rows,
            "extension_block_count_rows": 1,
            "split_rows": 1 if normalized_split_pair is not None else 0,
            "serialized_family_counts": dict(sorted(family_counts.items())),
            "link_point_degrees": list(link_point_degrees),
            "extension_degrees": list(extension_degree_vector),
            "full_point_degrees": list(full_point_degrees),
            "pair_bounds": pair_bounds,
            "corrected_pair_upper_bound": (
                "min(6*r_i-70-ell_ij, 6*r_j-70-ell_ij)"
            ),
            "split_pair": (
                list(normalized_split_pair)
                if normalized_split_pair is not None
                else None
            ),
            "split_value": split_value,
        },
    }


def math_comb(n: int, k: int) -> int:
    """Small local combination count without another public dependency."""

    if k < 0 or k > n:
        return 0
    numerator = 1
    denominator = 1
    for value in range(1, k + 1):
        numerator *= n - value + 1
        denominator *= value
    return numerator // denominator


def render_native_opb(
    rows: Iterable[PBRow],
    *,
    variable_count: int,
    class_index: int,
    case_id: int,
    profile_id: int,
    split_pair: Iterable[int] | None = None,
    split_value: int | None = None,
) -> bytes:
    """Render the historical native OPB byte format deterministically."""

    materialized = tuple(rows)
    lines = [
        f"* #variable= {variable_count} #constraint= {len(materialized)}",
        f"* class {class_index} case {case_id} profile {profile_id}",
        (
            "* exact native pseudo-Boolean transcription of "
            "portable_corrected_model.py"
        ),
    ]
    if split_pair is not None:
        normalized_pair = tuple(sorted(int(point) for point in split_pair))
        if split_value is None:
            raise ValueError("split value is required with a split pair")
        lines.append(
            "* exhaustive split: extension pair degree "
            f"{normalized_pair} = {split_value}"
        )
    for row in materialized:
        terms = " ".join(f"+1 x{variable + 1}" for variable in row.variables)
        lines.append(f"{terms} {row.relation} {row.rhs} ;")
    return ("\n".join(lines) + "\n").encode("utf-8")


def render_candidate_screening_opb(
    rows: Iterable[PBRow],
    *,
    variable_count: int,
    class_index: int,
    orbit_index: int,
    candidate_minimum_points: Iterable[int],
) -> bytes:
    """Render a deterministic native OPB candidate-orbit screen."""

    materialized = tuple(rows)
    candidate = tuple(sorted(int(point) for point in candidate_minimum_points))
    lines = [
        f"* #variable= {variable_count} #constraint= {len(materialized)}",
        f"* class {class_index} candidate-minimum-point orbit {orbit_index}",
        f"* candidate full-degree-15 points {candidate}",
        "* necessary-condition screen; formal pruning requires VERIFIED_UNSAT",
    ]
    for row in materialized:
        terms = " ".join(f"+1 x{variable + 1}" for variable in row.variables)
        lines.append(f"{terms} {row.relation} {row.rhs} ;")
    return ("\n".join(lines) + "\n").encode("utf-8")


def canonical_formula_sha256(
    rows: Iterable[PBRow], *, variable_count: int
) -> str:
    """Hash the same ordered canonical row representation as the prior audit."""

    canonical_rows = []
    for row in rows:
        if row.relation == ">=":
            relation = ">="
            rhs = row.rhs
            coefficient = 1
        else:
            relation = ">="
            rhs = -row.rhs
            coefficient = -1
        canonical_rows.append(
            (
                relation,
                rhs,
                tuple(
                    (variable + 1, coefficient)
                    for variable in row.variables
                ),
            )
        )
    payload = {"variables": variable_count, "rows": canonical_rows}
    encoded = json.dumps(
        payload, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalized_native_row_sha256(rows: Iterable[PBRow]) -> str:
    """Hash the native unit-row representation used by validate_opb.py."""

    payload = [
        (row.relation, row.rhs, row.variables)
        for row in rows
    ]
    return sha256_bytes(json.dumps(payload, separators=(",", ":")).encode())


def write_native_opb(
    path: Path,
    rows: Iterable[PBRow],
    *,
    variable_count: int,
    class_index: int,
    case_id: int,
    profile_id: int,
    split_pair: Iterable[int] | None = None,
    split_value: int | None = None,
) -> dict[str, Any]:
    payload = render_native_opb(
        rows,
        variable_count=variable_count,
        class_index=class_index,
        case_id=case_id,
        profile_id=profile_id,
        split_pair=split_pair,
        split_value=split_value,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "path": str(path),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def write_candidate_screening_opb(
    path: Path,
    rows: Iterable[PBRow],
    *,
    variable_count: int,
    class_index: int,
    orbit_index: int,
    candidate_minimum_points: Iterable[int],
) -> dict[str, Any]:
    payload = render_candidate_screening_opb(
        rows,
        variable_count=variable_count,
        class_index=class_index,
        orbit_index=orbit_index,
        candidate_minimum_points=candidate_minimum_points,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "path": str(path),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }
