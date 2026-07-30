#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import sys
from typing import Iterable


Block = tuple[int, ...]
Link = tuple[Block, ...]


def normalize(link: Iterable[Iterable[int]]) -> Link:
    return tuple(sorted(tuple(sorted(int(x) for x in block)) for block in link))


def compact_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def pretty_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def labeled_hash(link: Link, point_count: int) -> str:
    payload = {
        "blocks": [list(block) for block in normalize(link)],
        "points": list(range(point_count)),
    }
    return sha256(compact_bytes(payload)).hexdigest()


def valid_cover(
    link: Link,
    *,
    point_count: int,
    block_size: int,
    block_count: int,
    strength: int,
) -> bool:
    if len(link) != block_count or len(set(link)) != block_count:
        return False
    if any(
        len(block) != block_size
        or len(set(block)) != block_size
        or any(point < 0 or point >= point_count for point in block)
        for block in link
    ):
        return False
    covered = {
        subset for block in link for subset in combinations(block, strength)
    }
    return len(covered) == len(list(combinations(range(point_count), strength)))


def point_data(link: Link, point_count: int):
    sets = tuple(set(block) for block in link)
    degrees = tuple(sum(point in block for block in sets) for point in range(point_count))
    pairs = {
        pair: sum(set(pair) <= block for block in sets)
        for pair in combinations(range(point_count), 2)
    }
    triples = {
        triple: sum(set(triple) <= block for block in sets)
        for triple in combinations(range(point_count), 3)
    }
    fingerprints = []
    for point in range(point_count):
        neighborhood = []
        for other in range(point_count):
            if other == point:
                continue
            pair = tuple(sorted((point, other)))
            neighborhood.append((degrees[other], pairs[pair]))
        fingerprints.append((degrees[point], tuple(sorted(neighborhood))))
    return sets, degrees, pairs, triples, tuple(fingerprints)


def independent_signature(link: Link, point_count: int) -> tuple[object, ...]:
    sets, degrees, pairs, triples, fingerprints = point_data(link, point_count)
    block_intersections = tuple(
        sorted(
            len(sets[left] & sets[right])
            for left in range(len(sets))
            for right in range(left)
        )
    )
    return (
        tuple(sorted(degrees)),
        tuple(sorted(pairs.values())),
        tuple(sorted(triples.values())),
        tuple(sorted(fingerprints)),
        block_intersections,
    )


def independent_isomorphic(left: Link, right: Link, point_count: int) -> bool:
    """Independent exact checker based on restricted block-incidence patterns."""

    a = normalize(left)
    b = normalize(right)
    if independent_signature(a, point_count) != independent_signature(b, point_count):
        return False
    sets_a, _, pairs_a, triples_a, fingerprints_a = point_data(a, point_count)
    sets_b, _, pairs_b, triples_b, fingerprints_b = point_data(b, point_count)
    target_block_masks = {
        sum(1 << point for point in block) for block in b
    }
    mapping = [-1] * point_count
    assigned: list[int] = []
    used: set[int] = set()

    def restricted_patterns(
        blocks: tuple[set[int], ...], ordered_points: list[int]
    ) -> Counter[tuple[bool, ...]]:
        return Counter(
            tuple(point in block for point in ordered_points) for block in blocks
        )

    def compatible(source: int, target: int) -> bool:
        for old_source in assigned:
            old_target = mapping[old_source]
            if pairs_a[tuple(sorted((source, old_source)))] != pairs_b[
                tuple(sorted((target, old_target)))
            ]:
                return False
        for left, right in combinations(assigned, 2):
            if triples_a[tuple(sorted((source, left, right)))] != triples_b[
                tuple(sorted((target, mapping[left], mapping[right])))
            ]:
                return False
        sources = assigned + [source]
        targets = [mapping[old] for old in assigned] + [target]
        return restricted_patterns(sets_a, sources) == restricted_patterns(
            sets_b, targets
        )

    def search() -> bool:
        if len(assigned) == point_count:
            mapped = {
                sum(1 << mapping[point] for point in block) for block in a
            }
            return mapped == target_block_masks

        best_source = -1
        best_targets: list[int] | None = None
        for source in range(point_count):
            if mapping[source] >= 0:
                continue
            candidates = [
                target
                for target in range(point_count)
                if target not in used
                and fingerprints_a[source] == fingerprints_b[target]
                and compatible(source, target)
            ]
            if not candidates:
                return False
            if best_targets is None or (len(candidates), source) < (
                len(best_targets),
                best_source,
            ):
                best_source = source
                best_targets = candidates
        assert best_targets is not None
        for target in best_targets:
            mapping[best_source] = target
            assigned.append(best_source)
            used.add(target)
            if search():
                return True
            used.remove(target)
            assigned.pop()
            mapping[best_source] = -1
        return False

    return search()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    spec_path = args.input.resolve()
    run_dir = args.run_dir.resolve()
    run_path = run_dir / "catalog.audit.manifest.json"
    numbering_path = run_dir / "numbering.manifest.json"
    ledger_path = run_dir / "completion-ledger.jsonl"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    run = json.loads(run_path.read_text(encoding="utf-8"))
    numbering = json.loads(numbering_path.read_text(encoding="utf-8"))
    parameters = spec["parameters"]
    point_count = int(parameters["point_count"])
    block_size = int(parameters["block_size"])
    block_count = int(parameters["link_block_count"])
    strength = int(parameters["cover_strength"])
    errors: list[dict[str, object]] = []

    def check(condition: bool, code: str, detail: object = None) -> None:
        if not condition:
            errors.append({"code": code, "detail": detail})

    check(run["input"]["sha256"] == digest(spec_path), "INPUT_HASH_MISMATCH")
    check(
        run["outputs"]["completion_ledger"]["sha256"] == digest(ledger_path),
        "LEDGER_HASH_MISMATCH",
    )
    check(
        run["outputs"]["numbering_manifest"]["sha256"] == digest(numbering_path),
        "NUMBERING_HASH_MISMATCH",
    )
    entries = numbering["entries"]
    check(len(entries) == 68, "NUMBERING_ENTRY_COUNT", len(entries))
    check(
        [entry["class_index"] for entry in entries] == list(range(1, 69)),
        "NUMBERING_INDEX_SEQUENCE",
    )

    representatives: list[Link] = []
    for entry in entries:
        link = normalize(entry["normalized_labeled_link"])
        representatives.append(link)
        check(
            valid_cover(
                link,
                point_count=point_count,
                block_size=block_size,
                block_count=block_count,
                strength=strength,
            ),
            "INVALID_NUMBERED_LINK",
            entry["class_index"],
        )
        check(
            entry["canonical_labeled_link_sha256"]
            == labeled_hash(link, point_count),
            "NUMBERED_LINK_HASH_MISMATCH",
            entry["class_index"],
        )

    signature_buckets: defaultdict[tuple[object, ...], list[int]] = defaultdict(list)
    for index, link in enumerate(representatives[:67], 1):
        signature_buckets[independent_signature(link, point_count)].append(index)

    pairwise_collisions: list[list[int]] = []
    for left in range(68):
        for right in range(left):
            if independent_signature(
                representatives[left], point_count
            ) != independent_signature(representatives[right], point_count):
                continue
            if independent_isomorphic(
                representatives[left], representatives[right], point_count
            ):
                pairwise_collisions.append([right + 1, left + 1])
    check(not pairwise_collisions, "NUMBERED_LINKS_ISOMORPHIC", pairwise_collisions)

    template = spec["first_template"]
    fixed = normalize(template["fixed_blocks"])
    files = tuple(tuple(file) for file in template["files"])
    domains = tuple(
        tuple(tuple(choice) for choice in domain)
        for domain in template["choice_domains"]
    )
    expected_count = 1
    for domain in domains:
        expected_count *= len(domain)

    ledger_rows = ledger_path.read_text(encoding="utf-8").splitlines()
    check(len(ledger_rows) == expected_count, "LEDGER_ROW_COUNT", len(ledger_rows))
    counts = [0] * 67
    invalid_completion_count = 0
    ambiguous_completion_count = 0
    wrong_assignment_count = 0
    hash_mismatch_count = 0
    row_problem_samples: list[dict[str, object]] = []

    for completion_index, (choices, line) in enumerate(
        zip(product(*domains), ledger_rows), 1
    ):
        row = json.loads(line)
        appended = [
            tuple(sorted(files[index] + tuple(choice)))
            for index, choice in enumerate(choices)
        ]
        link = normalize(tuple(fixed) + tuple(appended))
        row_ok = True
        if row["completion_index"] != completion_index or row["choices"] != [
            list(choice) for choice in choices
        ]:
            row_ok = False
        is_valid = valid_cover(
            link,
            point_count=point_count,
            block_size=block_size,
            block_count=block_count,
            strength=strength,
        )
        if not is_valid or not row["valid_cover"]:
            invalid_completion_count += 1
            row_ok = False
        if row["canonical_labeled_link_sha256"] != labeled_hash(link, point_count):
            hash_mismatch_count += 1
            row_ok = False

        candidates = signature_buckets[independent_signature(link, point_count)]
        matches = [
            index
            for index in candidates
            if independent_isomorphic(
                link, representatives[index - 1], point_count
            )
        ]
        if len(matches) != 1:
            ambiguous_completion_count += 1
            row_ok = False
        else:
            counts[matches[0] - 1] += 1
            if row["discovered_class_index"] != matches[0]:
                wrong_assignment_count += 1
                row_ok = False
        if not row_ok and len(row_problem_samples) < 20:
            row_problem_samples.append(
                {
                    "completion_index": completion_index,
                    "candidate_classes": candidates,
                    "exact_matches": matches,
                    "recorded_class": row.get("discovered_class_index"),
                }
            )

    check(invalid_completion_count == 0, "INVALID_COMPLETIONS", invalid_completion_count)
    check(
        ambiguous_completion_count == 0,
        "NONUNIQUE_COMPLETION_ASSIGNMENTS",
        ambiguous_completion_count,
    )
    check(
        wrong_assignment_count == 0,
        "WRONG_COMPLETION_ASSIGNMENTS",
        wrong_assignment_count,
    )
    check(hash_mismatch_count == 0, "COMPLETION_HASH_MISMATCHES", hash_mismatch_count)
    check(
        counts == run["enumeration"]["full_class_counts"],
        "FULL_COUNT_MISMATCH",
        {"independent": counts, "recorded": run["enumeration"]["full_class_counts"]},
    )
    check(sum(counts) == expected_count, "FULL_COUNT_SUM", sum(counts))
    check(
        representatives[51]
        == normalize(spec["historical_catalog"]["archived_representatives"][51]),
        "CLASS52_SELECTION_MISMATCH",
    )
    check(
        labeled_hash(representatives[51], point_count)
        == "034d4c7cd44947c6fe2e8d562850611670af399f5d850b2c141990152a6af571",
        "CLASS52_CANONICAL_HASH_MISMATCH",
    )
    check(
        representatives[67]
        == normalize(spec["second_template"]["representatives"][0]),
        "CLASS68_FIG6_SELECTION_MISMATCH",
    )
    claim_auth = run["claim_authorization"]
    check(
        claim_auth["two_template_exhaustiveness"] is False,
        "UNAUTHORIZED_TEMPLATE_EXHAUSTIVENESS_CLAIM",
    )
    check(
        claim_auth["global_68_class_exhaustiveness"] is False,
        "UNAUTHORIZED_GLOBAL_EXHAUSTIVENESS_CLAIM",
    )
    check(
        claim_auth["claim_C_13_7_4_equals_30"] is False,
        "UNAUTHORIZED_COVERING_NUMBER_CLAIM",
    )

    audit = {
        "schema_version": "horizonmath.link-catalog-independent-audit.v1",
        "status": "PASS" if not errors else "FAIL",
        "implementation_independence": {
            "imports_production_classifier_core": False,
            "isomorphism_method": (
                "Independent point-map backtracking preserving pair and triple "
                "multiplicities and the complete restricted block-incidence "
                "pattern at every node; exact mapped-block equality at leaves."
            ),
            "hashes_used_only_for_identity_not_isomorphism": True,
        },
        "inputs": {
            "catalog_input_sha256": digest(spec_path),
            "catalog_run_manifest_sha256": digest(run_path),
            "numbering_manifest_sha256": digest(numbering_path),
            "completion_ledger_sha256": digest(ledger_path),
        },
        "audited": {
            "numbering_entries": len(entries),
            "completion_rows": len(ledger_rows),
            "independent_class_counts": counts,
            "pairwise_numbered_link_collisions": pairwise_collisions,
            "invalid_completion_count": invalid_completion_count,
            "ambiguous_completion_count": ambiguous_completion_count,
            "wrong_assignment_count": wrong_assignment_count,
            "completion_hash_mismatch_count": hash_mismatch_count,
            "row_problem_samples": row_problem_samples,
            "class52_canonical_labeled_link_sha256": labeled_hash(
                representatives[51], point_count
            ),
        },
        "claim_boundary": {
            "recovered_template_catalog_consistency_audited": not errors,
            "two_template_exhaustiveness_proved": False,
            "global_68_class_exhaustiveness_claim_authorized": False,
            "another_class_analyzed": False,
        },
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(pretty_bytes(audit))
    print(
        json.dumps(
            {
                "status": audit["status"],
                "output": str(args.output.resolve()),
                "sha256": digest(args.output),
                "completion_rows": len(ledger_rows),
                "errors": len(errors),
            },
            sort_keys=True,
        )
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

