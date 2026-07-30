from __future__ import annotations

from pathlib import Path
from typing import Any

from horizonlink.candidate_screening import (
    generate_candidate_screening_corpus,
)
from horizonlink.canonical import sha256_file, write_json


def build_candidate_fixture(
    structural_manifest: dict[str, Any],
    parent: Path,
    *,
    orbit_index: int,
    root_lp_status: str,
    mip_status: str,
    historical_disposition: str | None = None,
) -> tuple[Path, Path]:
    """Build a source-complete candidate corpus and a minimal solver ledger.

    The proof generators use the solver ledger only to enforce status and
    formula-hash boundaries. The LP/Farkas calculations are recomputed from
    the generated formula during each test.
    """

    candidate_directory = parent / "candidate-screens"
    _, corpus = generate_candidate_screening_corpus(
        structural_manifest,
        candidate_directory,
    )
    formula_record = next(
        record
        for record in corpus["instances"]
        if int(record["orbit_index"]) == orbit_index
    )
    corpus_path = candidate_directory / "corpus.manifest.json"
    exploratory_disposition = (
        "SCREENED_OUT_SOLVER_ONLY"
        if mip_status == "SOLVER_UNSAT"
        else "RETAINED"
    )
    solver_record = {
        "orbit_index": orbit_index,
        "status": "SOLVER_UNSAT",
        "formula": {
            "actual_sha256": formula_record["formula"]["sha256"],
        },
        "root_lp": {"status": root_lp_status},
        "mip": {"status": mip_status},
    }
    if historical_disposition is not None:
        historical_exploratory = (
            "SCREENED_OUT_SOLVER_ONLY"
            if historical_disposition == "DISCARDED"
            else "RETAINED"
        )
        solver_record["historical_comparison"] = {
            "historical_disposition": historical_disposition,
            "historical_exploratory_disposition": historical_exploratory,
            "fresh_exploratory_disposition": exploratory_disposition,
            "equal": historical_exploratory == exploratory_disposition,
            "interpretation": (
                "A difference may reflect solver/version/runtime progress; "
                "it does not alter formal status."
            ),
        }
    solver_manifest = {
        "schema_version": "horizonmath.test-solver-ledger.v1",
        "status": "SOLVER_UNSAT",
        "input": {
            "canonical_labeled_link_sha256": structural_manifest["input"][
                "canonical_labeled_link_sha256"
            ],
            "corpus_manifest_sha256": sha256_file(corpus_path),
        },
        "instances": [solver_record],
    }
    solver_path = parent / "solver_run.manifest.json"
    write_json(solver_path, solver_manifest)
    return candidate_directory, solver_path
