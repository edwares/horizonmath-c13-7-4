#!/usr/bin/env python3
"""Regenerate and audit the deterministic class-52 structural outputs."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from horizonlink import __version__  # noqa: E402
from horizonlink.canonical import (  # noqa: E402
    pretty_json_bytes,
    sha256_file,
    write_json,
    write_sha256_sidecar,
)
from horizonlink.input import load_link  # noqa: E402
from horizonlink.formulas import generate_formula_corpus  # noqa: E402
from horizonlink.manifest import build_manifest  # noqa: E402
from horizonlink.regression import run_class52_regression  # noqa: E402
from horizonlink.screening import (  # noqa: E402
    extend_manifest_with_screening,
    load_screening_ledger,
)


CLASS52 = ROOT / "data" / "class52.link.json"
GOLDEN_AUTOMORPHISMS = (
    ROOT / "tests" / "data" / "golden" / "results_class52_automorphisms.json"
)
GOLDEN_ORBITS = (
    ROOT / "tests" / "data" / "golden" / "results_class52_minpoint4_orbits.json"
)
BUILD = ROOT / "build"
SCREENING_LEDGER = ROOT / "data" / "class52.recovered-screening-ledger.json"
SOURCE_AUDIT = BUILD / "class52.candidate-screening-source-comparison.json"
FARKAS_AUDIT = BUILD / "class52.candidate-root-lp-farkas-audit.json"
VERIFICATION_AUDIT = (
    BUILD / "class52.candidate-root-lp-verification-audit.json"
)
SPLIT_FARKAS_AUDIT = (
    BUILD / "class52.candidate-lp-split-farkas-audit.json"
)
SPLIT_VERIFICATION_AUDIT = (
    BUILD / "class52.candidate-lp-split-verification-audit.json"
)
PHASE_MANIFEST = BUILD / "class52.candidate-screening-phase.manifest.json"
VERIFIER_PROVENANCE = ROOT / "verifier" / "build.provenance.json"


class RecordingResult(unittest.TestResult):
    """Capture stable test identifiers and outcomes without elapsed times."""

    def __init__(self) -> None:
        super().__init__()
        self.records: dict[str, dict[str, str]] = {}

    def _record(
        self, test: unittest.case.TestCase, status: str, detail: str | None = None
    ) -> None:
        record = {"id": test.id(), "status": status}
        if detail is not None:
            record["detail"] = detail
        self.records[test.id()] = record

    @staticmethod
    def _error_detail(err: tuple[type[BaseException], BaseException, Any]) -> str:
        exception_type, exception, _ = err
        return f"{exception_type.__name__}: {exception}"

    def addSuccess(self, test: unittest.case.TestCase) -> None:
        super().addSuccess(test)
        self._record(test, "PASS")

    def addFailure(
        self,
        test: unittest.case.TestCase,
        err: tuple[type[BaseException], BaseException, Any],
    ) -> None:
        super().addFailure(test, err)
        self._record(test, "FAIL", self._error_detail(err))

    def addError(
        self,
        test: unittest.case.TestCase,
        err: tuple[type[BaseException], BaseException, Any],
    ) -> None:
        super().addError(test, err)
        self._record(test, "ERROR", self._error_detail(err))

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self._record(test, "SKIP", reason)

    def addExpectedFailure(
        self,
        test: unittest.case.TestCase,
        err: tuple[type[BaseException], BaseException, Any],
    ) -> None:
        super().addExpectedFailure(test, err)
        self._record(test, "EXPECTED_FAILURE", self._error_detail(err))

    def addUnexpectedSuccess(self, test: unittest.case.TestCase) -> None:
        super().addUnexpectedSuccess(test)
        self._record(test, "UNEXPECTED_SUCCESS")


def run_tests() -> tuple[RecordingResult, dict[str, Any]]:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = RecordingResult()
    suite.run(result)
    report = {
        "successful": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses),
        "tests": [result.records[key] for key in sorted(result.records)],
    }
    return result, report


def source_paths() -> list[Path]:
    files = [
        ROOT / "README.md",
        ROOT / "PROVENANCE.md",
        ROOT / "RECOVERY_AUDIT.md",
        ROOT / "SCREENING_PHASE_AUDIT.md",
        ROOT / "SPLIT_FARKAS_PHASE_AUDIT.md",
        ROOT / "pyproject.toml",
    ]
    for directory in (
        ROOT / "data",
        ROOT / "schemas",
        ROOT / "scripts",
        ROOT / "src",
        ROOT / "tests",
        ROOT / "verifier",
        ROOT / "proof_dependencies",
    ):
        files.extend(
            path
            for path in directory.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
        )
    return sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())


def inventory(paths: list[Path]) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in paths
    ]


def main() -> int:
    BUILD.mkdir(parents=True, exist_ok=True)
    test_result, test_report = run_tests()

    first_link = load_link(CLASS52)
    second_link = load_link(CLASS52)
    first_ledger = load_screening_ledger(SCREENING_LEDGER)
    second_ledger = load_screening_ledger(SCREENING_LEDGER)
    first_manifest = extend_manifest_with_screening(
        build_manifest(first_link), first_ledger
    )
    second_manifest = extend_manifest_with_screening(
        build_manifest(second_link), second_ledger
    )
    manifest_byte_identity = (
        pretty_json_bytes(first_manifest) == pretty_json_bytes(second_manifest)
    )

    regression = run_class52_regression(
        first_manifest,
        GOLDEN_AUTOMORPHISMS,
        GOLDEN_ORBITS,
    )

    normalized_path = BUILD / "class52.normalized.link.json"
    manifest_path = BUILD / "class52.profile.manifest.json"
    regression_path = BUILD / "class52.regression.json"
    write_json(normalized_path, first_link.canonical_document)
    write_json(manifest_path, first_manifest)
    write_json(regression_path, regression)
    for path in (normalized_path, manifest_path, regression_path):
        write_sha256_sidecar(path)

    formula_directory = BUILD / "class52.formulas"
    formula_manifest, formula_corpus = generate_formula_corpus(
        first_manifest, formula_directory
    )
    formula_analysis_path = BUILD / "class52.formula-analysis.manifest.json"
    write_json(formula_analysis_path, formula_manifest)
    write_sha256_sidecar(formula_analysis_path)

    formula_paths = sorted(
        path
        for path in formula_directory.rglob("*")
        if path.is_file()
    )
    source_audit = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    farkas_audit = json.loads(FARKAS_AUDIT.read_text(encoding="utf-8"))
    verification_audit = json.loads(
        VERIFICATION_AUDIT.read_text(encoding="utf-8")
    )
    split_farkas_audit = json.loads(
        SPLIT_FARKAS_AUDIT.read_text(encoding="utf-8")
    )
    split_verification_audit = json.loads(
        SPLIT_VERIFICATION_AUDIT.read_text(encoding="utf-8")
    )
    phase_manifest = json.loads(
        PHASE_MANIFEST.read_text(encoding="utf-8")
    )
    verifier_provenance = json.loads(
        VERIFIER_PROVENANCE.read_text(encoding="utf-8")
    )
    verifier_artifact_checks = {
        "build_log_hash_matches": (
            sha256_file(ROOT / verifier_provenance["build_log"]["path"])
            == verifier_provenance["build_log"]["sha256"]
        ),
        "build_setup_hash_matches": (
            sha256_file(ROOT / verifier_provenance["build_setup"]["path"])
            == verifier_provenance["build_setup"]["sha256"]
        ),
        "wheel_hash_matches": (
            sha256_file(ROOT / verifier_provenance["wheel"]["path"])
            == verifier_provenance["wheel"]["sha256"]
        ),
        "dependency_hashes_match": all(
            sha256_file(ROOT / record["path"]) == record["sha256"]
            for record in verifier_provenance["dependencies"]
        ),
        "published_smoke_test_passed": (
            verifier_provenance["published_certificate_smoke_test"][
                "status"
            ]
            == "PASS"
            and verifier_provenance["published_certificate_smoke_test"][
                "used_require_unsat"
            ]
            is True
            and verifier_provenance["published_certificate_smoke_test"][
                "exit_code"
            ]
            == 0
            and verifier_provenance["published_certificate_smoke_test"][
                "reported_output"
            ]
            == "Verification succeeded."
        ),
    }
    phase_paths = sorted(
        {
            SOURCE_AUDIT,
            FARKAS_AUDIT,
            VERIFICATION_AUDIT,
            SPLIT_FARKAS_AUDIT,
            SPLIT_VERIFICATION_AUDIT,
            PHASE_MANIFEST,
            BUILD / "class52.candidate-lp-split-farkas.generation-command.log",
            *(
                path
                for directory in (
                    BUILD / "class52.candidate-screens",
                    BUILD / "class52.candidate-screening-solver",
                    BUILD / "class52.candidate-root-lp-farkas",
                    BUILD / "class52.candidate-root-lp-verification",
                    BUILD / "class52.candidate-lp-split-farkas",
                    BUILD / "class52.candidate-lp-split-verification",
                    BUILD / "archive" / "split-tree-verifier-preflight",
                )
                for path in directory.rglob("*")
                if path.is_file()
            ),
        },
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )
    generated_paths = [
        normalized_path,
        manifest_path,
        regression_path,
        formula_analysis_path,
        *formula_paths,
        *phase_paths,
    ]
    audit_passed = (
        test_result.wasSuccessful()
        and test_report["skipped"] == 0
        and manifest_byte_identity
        and first_manifest["status"] == "ENUMERATED"
        and first_manifest["screening"]["comparison"]["all_checks_passed"]
        and regression["all_checks_passed"]
        and formula_corpus["summary"]["all_comparisons_passed"]
        and source_audit["status"] == "PASS"
        and farkas_audit["status"] == "PASS"
        and verification_audit["status"] == "PASS"
        and split_farkas_audit["status"] == "PASS"
        and split_verification_audit["status"] == "PASS"
        and phase_manifest["summary"]["all_orbits_accounted_for"]
        and phase_manifest["summary"]["formally_pruned_orbits"] == 19
        and phase_manifest["summary"]["retained_orbit_count"] == 7
        and phase_manifest["summary"][
            "solver_unsat_without_verified_proof"
        ]
        == 0
        and phase_manifest["summary"]["historical_18_8_partition"][
            "all_historical_discarded_orbits_now_verified"
        ]
        is True
        and phase_manifest["summary"][
            "additional_verified_orbits_beyond_historical_discarded"
        ]
        == [14]
        and not phase_manifest["summary"]["class_formally_eliminated"]
        and all(verifier_artifact_checks.values())
    )
    audit_report = {
        "schema_version": "horizonmath.link-frontend-audit.v1",
        "tool": {"name": "horizonlink", "version": __version__},
        "status": "PASS" if audit_passed else "FAIL",
        "unit_tests": test_report,
        "determinism": {
            "independent_manifest_reruns_byte_identical": manifest_byte_identity,
        },
        "class52_structural_regression": {
            "status": regression["status"],
            "checks": len(regression["checks"]),
            "passed": sum(check["passed"] for check in regression["checks"]),
        },
        "class52_formula_regression": formula_corpus["summary"],
        "candidate_screening_phase": phase_manifest["summary"],
        "candidate_screening_audits": {
            "source_rows": source_audit["summary"],
            "exact_farkas": farkas_audit["summary"],
            "veripb_verification": verification_audit["summary"],
            "split_farkas": split_farkas_audit["summary"],
            "split_veripb_verification": split_verification_audit[
                "summary"
            ],
        },
        "verifier_artifact_checks": verifier_artifact_checks,
        "source_inventory": inventory(source_paths()),
        "generated_artifacts": inventory(generated_paths),
        "scope": {
            "structural_front_end": "ENUMERATED",
            "extension_degree_profiles": "ENUMERATED",
            "screening": "ENUMERATED_FROM_RECOVERED_LEDGER",
            "formulas": "FORMULAS_GENERATED",
            "prior_formula_metadata": "CHECKED",
            "candidate_screening_solver": {
                "SOLVER_UNSAT": 19,
                "TIMEOUT": 7,
            },
            "candidate_screening_proof": {
                "PROOF_GENERATED": 19,
                "NOT_STARTED": 7,
            },
            "candidate_screening_verification": {
                "VERIFIED_UNSAT": 19,
                "NOT_STARTED": 7,
            },
            "class_formally_eliminated": False,
        },
    }
    audit_path = BUILD / "class52.frontend.audit.json"
    write_json(audit_path, audit_report)
    write_sha256_sidecar(audit_path)

    print(
        f"{audit_report['status']}: "
        f"{test_report['tests_run']} tests; "
        f"{audit_report['class52_structural_regression']['passed']}/"
        f"{audit_report['class52_structural_regression']['checks']} "
        "class-52 checks"
    )
    return 0 if audit_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
