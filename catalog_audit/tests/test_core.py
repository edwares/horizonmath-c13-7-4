import unittest

from catalog_audit.core import exact_isomorphism, normalize_link, validate_link


BASE = normalize_link(
    [
        (0, 1, 4, 5, 8, 9),
        (0, 2, 4, 6, 8, 10),
        (0, 3, 4, 7, 8, 11),
        (0, 1, 6, 7, 10, 11),
        (0, 2, 5, 7, 9, 11),
        (0, 3, 5, 6, 9, 10),
        (2, 3, 4, 5, 10, 11),
        (1, 3, 4, 6, 9, 11),
        (1, 2, 4, 7, 9, 10),
        (2, 3, 6, 7, 8, 9),
        (1, 3, 5, 7, 8, 10),
        (1, 2, 5, 6, 8, 11),
        (0, 1, 2, 3, 4, 5),
        (0, 1, 4, 5, 6, 7),
        (0, 1, 8, 9, 10, 11),
    ]
)


def relabel(link, permutation):
    return normalize_link(
        tuple(tuple(permutation[point] for point in block) for block in link)
    )


class CoreTests(unittest.TestCase):
    def test_exact_isomorphism_accepts_deterministic_relabelings(self):
        permutations_to_test = [
            tuple(range(12)),
            tuple(reversed(range(12))),
            (1, 0, 3, 2, 5, 4, 7, 6, 9, 8, 11, 10),
        ]
        for permutation in permutations_to_test:
            self.assertTrue(
                exact_isomorphism(
                    BASE, relabel(BASE, permutation), point_count=12
                )
            )

    def test_exact_isomorphism_rejects_changed_block(self):
        changed = list(BASE)
        changed[-1] = (0, 2, 8, 9, 10, 11)
        self.assertFalse(exact_isomorphism(BASE, changed, point_count=12))

    def test_validation_detects_duplicate_block(self):
        changed = list(BASE)
        changed[-1] = changed[-2]
        report = validate_link(
            changed,
            point_count=12,
            block_size=6,
            block_count=15,
            cover_strength=3,
        )
        self.assertFalse(report["valid"])
        self.assertIn("duplicate blocks", report["problems"])


if __name__ == "__main__":
    unittest.main()
