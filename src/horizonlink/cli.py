"""Command-line interface for the deterministic structural front end."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from horizonlink.candidate_screening import (
    generate_candidate_screening_corpus,
)
from horizonlink.canonical import write_json, write_sha256_sidecar
from horizonlink.input import InputFormatError, load_link, parse_link_bytes
from horizonlink.formulas import generate_formula_corpus
from horizonlink.farkas import generate_root_lp_farkas_corpus
from horizonlink.manifest import build_format_error_manifest, build_manifest
from horizonlink.regression import run_class52_regression
from horizonlink.screening import (
    ScreeningLedgerError,
    extend_manifest_with_screening,
    load_screening_ledger,
)
from horizonlink.solver import solve_candidate_screening_corpus
from horizonlink.split_farkas import generate_lp_split_farkas_corpus


def _print_summary(value: dict[str, Any]) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _analyze(args: argparse.Namespace) -> int:
    try:
        raw = args.input.read_bytes()
    except OSError as exc:
        print(f"cannot read input: {exc}", file=sys.stderr)
        return 2
    try:
        link = parse_link_bytes(raw)
    except InputFormatError as exc:
        manifest = build_format_error_manifest(raw, exc)
        write_json(args.manifest, manifest)
        write_sha256_sidecar(args.manifest)
        _print_summary(
            {
                "status": "ERROR",
                "format_errors": len(exc.errors),
                "manifest": str(args.manifest),
            }
        )
        return 2

    if args.normalized_link is not None:
        write_json(args.normalized_link, link.canonical_document)
        write_sha256_sidecar(args.normalized_link)
    manifest = build_manifest(link, args.subset_size)
    if args.require_canonical_input and not link.content_was_canonical:
        manifest["status"] = "ERROR"
        manifest["format_validation"]["valid"] = False
        manifest["format_validation"]["errors"].append(
            {
                "path": "$",
                "code": "NONCANONICAL_INPUT",
                "message": (
                    "input content is valid but not in canonical block/source order"
                ),
            }
        )
        manifest["status_ledger"]["link"] = "ERROR"
    if args.screening_ledger is not None and manifest["status"] == "ENUMERATED":
        try:
            ledger = load_screening_ledger(args.screening_ledger)
            manifest = extend_manifest_with_screening(manifest, ledger)
        except ScreeningLedgerError as exc:
            manifest["status"] = "ERROR"
            manifest["status_ledger"]["screening"] = "ERROR"
            manifest["screening_error"] = {
                "code": "SCREENING_LEDGER",
                "message": str(exc),
            }
    write_json(args.manifest, manifest)
    write_sha256_sidecar(args.manifest)
    summary = {
        "status": manifest["status"],
        "canonical_labeled_link_sha256": manifest["input"][
            "canonical_labeled_link_sha256"
        ],
        "valid_cover": manifest["mathematical_validation"][
            "valid_15_block_C_12_6_3_cover"
        ],
        "automorphism_group_order": (
            manifest["automorphism_group"]["order"]
            if manifest["automorphism_group"]
            else None
        ),
        "candidate_subset_orbits": (
            manifest["candidate_minimum_point_sets"]["orbit_count"]
            if manifest["candidate_minimum_point_sets"]
            else None
        ),
        "exact_minimum_set_orbits": (
            manifest["exact_minimum_point_sets"]["orbit_count"]
            if manifest.get("exact_minimum_point_sets")
            else None
        ),
        "degree_profile_orbits": (
            manifest["extension_degree_profiles"]["profile_orbit_count"]
            if manifest.get("extension_degree_profiles")
            else None
        ),
        "manifest": str(args.manifest),
    }
    _print_summary(summary)
    return 0 if manifest["status"] == "ENUMERATED" else 1


def _regress_class52(args: argparse.Namespace) -> int:
    try:
        link = load_link(args.input)
    except (OSError, InputFormatError) as exc:
        report = {
            "schema_version": "horizonmath.class52-structural-regression.v1",
            "status": "ERROR",
            "all_checks_passed": False,
            "errors": (
                exc.errors
                if isinstance(exc, InputFormatError)
                else [{"code": "INPUT_READ", "message": str(exc)}]
            ),
        }
        write_json(args.output, report)
        write_sha256_sidecar(args.output)
        _print_summary(
            {"status": "ERROR", "output": str(args.output)}
        )
        return 2

    manifest = build_manifest(link, 4)
    if args.screening_ledger is not None:
        try:
            ledger = load_screening_ledger(args.screening_ledger)
            manifest = extend_manifest_with_screening(manifest, ledger)
        except ScreeningLedgerError as exc:
            report = {
                "schema_version": "horizonmath.class52-full-regression.v1",
                "status": "ERROR",
                "all_checks_passed": False,
                "errors": [
                    {
                        "code": "SCREENING_LEDGER",
                        "message": str(exc),
                    }
                ],
            }
            write_json(args.output, report)
            write_sha256_sidecar(args.output)
            _print_summary({"status": "ERROR", "output": str(args.output)})
            return 2
    if args.manifest is not None:
        write_json(args.manifest, manifest)
        write_sha256_sidecar(args.manifest)
    try:
        report = run_class52_regression(
            manifest,
            args.golden_automorphisms,
            args.golden_four_orbits,
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        report = {
            "schema_version": "horizonmath.class52-structural-regression.v1",
            "status": "ERROR",
            "all_checks_passed": False,
            "errors": [
                {
                    "code": "GOLDEN_ARTIFACT",
                    "message": str(exc),
                }
            ],
        }
        write_json(args.output, report)
        write_sha256_sidecar(args.output)
        _print_summary({"status": "ERROR", "output": str(args.output)})
        return 2
    write_json(args.output, report)
    write_sha256_sidecar(args.output)
    _print_summary(
        {
            "status": report["status"],
            "checks": len(report["checks"]),
            "passed": sum(check["passed"] for check in report["checks"]),
            "output": str(args.output),
        }
    )
    return 0 if report["all_checks_passed"] else 1


def _generate_formulas(args: argparse.Namespace) -> int:
    try:
        link = load_link(args.input)
        ledger = load_screening_ledger(args.screening_ledger)
        manifest = extend_manifest_with_screening(
            build_manifest(link, 4), ledger
        )
        manifest, corpus = generate_formula_corpus(
            manifest, args.output_directory
        )
    except (
        OSError,
        InputFormatError,
        ScreeningLedgerError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        _print_summary({"status": "ERROR", "message": str(exc)})
        return 2

    write_json(args.analysis_manifest, manifest)
    write_sha256_sidecar(args.analysis_manifest)
    _print_summary(
        {
            "status": corpus["status"],
            "instances": corpus["summary"]["instances"],
            "byte_identical": corpus["summary"][
                "byte_identical_to_prior_native_formulas"
            ],
            "canonical_equivalent": corpus["summary"][
                "canonical_row_equivalent_to_prior_formulas"
            ],
            "output_directory": str(args.output_directory),
            "analysis_manifest": str(args.analysis_manifest),
        }
    )
    return 0 if corpus["status"] == "FORMULAS_GENERATED" else 1


def _generate_candidate_screens(args: argparse.Namespace) -> int:
    try:
        link = load_link(args.input)
        manifest, corpus = generate_candidate_screening_corpus(
            build_manifest(link, 4), args.output_directory
        )
    except (OSError, InputFormatError, KeyError, TypeError, ValueError) as exc:
        _print_summary({"status": "ERROR", "message": str(exc)})
        return 2

    write_json(args.analysis_manifest, manifest)
    write_sha256_sidecar(args.analysis_manifest)
    _print_summary(
        {
            "status": corpus["status"],
            "candidate_orbits": corpus["summary"]["candidate_orbits"],
            "formulas_generated": corpus["summary"][
                "formulas_generated"
            ],
            "all_orbits_accounted_for": corpus["summary"][
                "all_orbits_accounted_for"
            ],
            "formal_orbit_pruning_authorized": corpus["scope"][
                "formal_orbit_pruning_authorized"
            ],
            "output_directory": str(args.output_directory),
            "analysis_manifest": str(args.analysis_manifest),
        }
    )
    return 0 if corpus["status"] == "FORMULAS_GENERATED" else 1


def _solve_candidate_screens(args: argparse.Namespace) -> int:
    try:
        link = load_link(args.input)
        report = solve_candidate_screening_corpus(
            build_manifest(link, 4),
            args.corpus_directory,
            args.output_directory,
            root_lp_time_limit=args.root_lp_time_limit,
            mip_time_limit=args.mip_time_limit,
            orbit_indices=args.orbit,
            historical_ledger=args.historical_ledger,
        )
    except (
        OSError,
        RuntimeError,
        InputFormatError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        _print_summary({"status": "ERROR", "message": str(exc)})
        return 2

    _print_summary(
        {
            "status": report["status"],
            "selected_orbits": report["summary"]["selected_orbits"],
            "status_counts": report["summary"]["status_counts"],
            "root_lp_status_counts": report["summary"][
                "root_lp_status_counts"
            ],
            "formula_hash_checks_passed": report["summary"][
                "formula_hash_checks_passed"
            ],
            "formal_pruning_authorized": report["summary"][
                "formal_pruning_authorized"
            ],
            "output_directory": str(args.output_directory),
        }
    )
    return 1 if report["status"] == "ERROR" else 0


def _generate_root_lp_farkas(args: argparse.Namespace) -> int:
    try:
        link = load_link(args.input)
        report = generate_root_lp_farkas_corpus(
            build_manifest(link, 4),
            args.corpus_directory,
            args.solver_manifest,
            args.output_directory,
            orbit_indices=args.orbit,
        )
    except (
        OSError,
        RuntimeError,
        InputFormatError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        _print_summary({"status": "ERROR", "message": str(exc)})
        return 2

    _print_summary(
        {
            "status": report["status"],
            "selected_orbits": report["summary"]["selected_orbits"],
            "proofs_generated": report["summary"]["proofs_generated"],
            "exact_certificates_passed": report["summary"][
                "exact_certificates_passed"
            ],
            "verified_unsat": report["summary"]["verified_unsat"],
            "formal_pruning_authorized": report["summary"][
                "formal_pruning_authorized"
            ],
            "output_directory": str(args.output_directory),
        }
    )
    return 0 if report["status"] == "PROOF_GENERATED" else 1


def _generate_lp_split_farkas(args: argparse.Namespace) -> int:
    try:
        link = load_link(args.input)
        report = generate_lp_split_farkas_corpus(
            build_manifest(link, 4),
            args.corpus_directory,
            args.solver_manifest,
            args.output_directory,
            orbit_indices=args.orbit,
            max_nodes=args.max_nodes,
            lp_time_limit=args.lp_time_limit,
            reference_release_archive=args.reference_release,
            dependency_wheels=args.dependency_wheel,
        )
    except (
        OSError,
        RuntimeError,
        InputFormatError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        _print_summary({"status": "ERROR", "message": str(exc)})
        return 2

    _print_summary(
        {
            "status": report["status"],
            "selected_orbits": report["summary"]["selected_orbits"],
            "complete_split_trees": report["summary"][
                "complete_split_trees"
            ],
            "tree_nodes": report["summary"]["tree_nodes"],
            "exact_leaf_certificates": report["summary"][
                "exact_leaf_certificates"
            ],
            "proofs_generated": report["summary"]["proofs_generated"],
            "verified_unsat": report["summary"]["verified_unsat"],
            "formal_pruning_authorized": report["summary"][
                "formal_pruning_authorized"
            ],
            "output_directory": str(args.output_directory),
        }
    )
    return 0 if report["status"] == "PROOF_GENERATED" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="horizonlink")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser(
        "analyze", help="analyze one labeled minimum C(12,6,3) link"
    )
    analyze.add_argument("input", type=Path)
    analyze.add_argument("--manifest", type=Path, required=True)
    analyze.add_argument("--normalized-link", type=Path)
    analyze.add_argument("--subset-size", type=int, default=4, choices=range(1, 13))
    analyze.add_argument(
        "--screening-ledger",
        type=Path,
        help=(
            "complete prior screening ledger to validate and continue through "
            "exact degree-profile enumeration"
        ),
    )
    analyze.add_argument("--require-canonical-input", action="store_true")
    analyze.set_defaults(func=_analyze)

    regression = subparsers.add_parser(
        "regress-class52",
        help="run the exact class-52 structural golden regression",
    )
    regression.add_argument("input", type=Path)
    regression.add_argument("--golden-automorphisms", type=Path, required=True)
    regression.add_argument("--golden-four-orbits", type=Path, required=True)
    regression.add_argument("--output", type=Path, required=True)
    regression.add_argument("--manifest", type=Path)
    regression.add_argument(
        "--screening-ledger",
        type=Path,
        help="recovered screening ledger for the full 107-profile regression",
    )
    regression.set_defaults(func=_regress_class52)

    formulas = subparsers.add_parser(
        "generate-formulas",
        help="generate corrected native OPBs after a complete screening ledger",
    )
    formulas.add_argument("input", type=Path)
    formulas.add_argument("--screening-ledger", type=Path, required=True)
    formulas.add_argument("--output-directory", type=Path, required=True)
    formulas.add_argument("--analysis-manifest", type=Path, required=True)
    formulas.set_defaults(func=_generate_formulas)

    candidate_screens = subparsers.add_parser(
        "generate-candidate-screens",
        help=(
            "generate one necessary-condition native OPB for every candidate "
            "minimum-point-set orbit"
        ),
    )
    candidate_screens.add_argument("input", type=Path)
    candidate_screens.add_argument(
        "--output-directory", type=Path, required=True
    )
    candidate_screens.add_argument(
        "--analysis-manifest", type=Path, required=True
    )
    candidate_screens.set_defaults(func=_generate_candidate_screens)

    solve_candidate_screens = subparsers.add_parser(
        "solve-candidate-screens",
        help=(
            "run controlled root-LP and MILP checks on a generated candidate "
            "screening corpus without promoting solver reports to proofs"
        ),
    )
    solve_candidate_screens.add_argument("input", type=Path)
    solve_candidate_screens.add_argument(
        "--corpus-directory", type=Path, required=True
    )
    solve_candidate_screens.add_argument(
        "--output-directory", type=Path, required=True
    )
    solve_candidate_screens.add_argument(
        "--root-lp-time-limit", type=float, default=10.0
    )
    solve_candidate_screens.add_argument(
        "--mip-time-limit", type=float, default=10.0
    )
    solve_candidate_screens.add_argument(
        "--orbit",
        type=int,
        action="append",
        help="solve only this orbit; repeat to select multiple orbits",
    )
    solve_candidate_screens.add_argument(
        "--historical-ledger",
        type=Path,
        help="optional recovered ledger for a non-authoritative comparison",
    )
    solve_candidate_screens.set_defaults(func=_solve_candidate_screens)

    root_lp_farkas = subparsers.add_parser(
        "generate-root-lp-farkas",
        help=(
            "generate exact direct Farkas proofs for screens with a fresh "
            "root-LP SOLVER_UNSAT result; verification remains separate"
        ),
    )
    root_lp_farkas.add_argument("input", type=Path)
    root_lp_farkas.add_argument(
        "--corpus-directory", type=Path, required=True
    )
    root_lp_farkas.add_argument(
        "--solver-manifest", type=Path, required=True
    )
    root_lp_farkas.add_argument(
        "--output-directory", type=Path, required=True
    )
    root_lp_farkas.add_argument(
        "--orbit",
        type=int,
        action="append",
        help=(
            "generate only this root-LP-infeasible orbit; repeat to select "
            "multiple orbits"
        ),
    )
    root_lp_farkas.set_defaults(func=_generate_root_lp_farkas)

    split_farkas = subparsers.add_parser(
        "generate-lp-split-farkas",
        help=(
            "generate complete exact LP split-tree/Farkas proofs for "
            "root-LP-feasible screens with a fresh MILP SOLVER_UNSAT result; "
            "verification remains separate"
        ),
    )
    split_farkas.add_argument("input", type=Path)
    split_farkas.add_argument(
        "--corpus-directory", type=Path, required=True
    )
    split_farkas.add_argument(
        "--solver-manifest", type=Path, required=True
    )
    split_farkas.add_argument(
        "--output-directory", type=Path, required=True
    )
    split_farkas.add_argument(
        "--orbit",
        type=int,
        action="append",
        help="generate only this eligible orbit; repeat to select several",
    )
    split_farkas.add_argument("--max-nodes", type=int, default=5000)
    split_farkas.add_argument("--lp-time-limit", type=float, default=30.0)
    split_farkas.add_argument(
        "--reference-release",
        type=Path,
        help=(
            "optional immutable class-52 release ZIP whose split-proof "
            "mechanism and script hashes are recorded as provenance"
        ),
    )
    split_farkas.add_argument(
        "--dependency-wheel",
        type=Path,
        action="append",
        help=(
            "pinned local proof dependency wheel to hash into provenance; "
            "repeat for multiple wheels"
        ),
    )
    split_farkas.set_defaults(func=_generate_lp_split_farkas)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
