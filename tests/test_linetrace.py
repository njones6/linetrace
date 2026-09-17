import unittest

from linetrace import parse_unified_diff, trace_line, trace_range, trace_range_from_diff


class TraceLineEqualTest(unittest.TestCase):
    def test_unchanged_line_maps_by_offset(self):
        old = ["a", "b", "c"]
        new = ["x", "a", "b", "c"]
        # everything in `old` sits in one equal block, shifted right by one
        for i in range(1, 4):
            self.assertEqual(trace_line(old, new, i), ("unchanged", i + 1))

    def test_identical_texts_are_all_unchanged_at_same_line(self):
        old = ["one", "two", "three"]
        new = list(old)
        for i in range(1, 4):
            self.assertEqual(trace_line(old, new, i), ("unchanged", i))


class TraceLineReplaceTest(unittest.TestCase):
    def test_one_to_one_replace_is_exact(self):
        old = ["a", "b", "c"]
        new = ["a", "B", "c"]
        self.assertEqual(trace_line(old, new, 2), ("modified", 2))

    def test_proportional_guess_for_larger_block(self):
        # old[1:4] ("b","c","d") replaced by new[1:3] ("B","C") - a 3-to-2 replace
        old = ["a", "b", "c", "d", "e"]
        new = ["a", "B", "C", "e"]
        self.assertEqual(trace_line(old, new, 2), ("modified", 2))  # offset 0 -> 1+0
        self.assertEqual(trace_line(old, new, 3), ("modified", 2))  # offset 1 -> 1+1*2//3=2
        self.assertEqual(trace_line(old, new, 4), ("modified", 3))  # offset 2 -> 1+2*2//3=3

    def test_replace_growing_block_maps_forward(self):
        # a single old line replaced by three new lines
        old = ["a", "b", "c"]
        new = ["a", "X", "Y", "Z", "c"]
        self.assertEqual(trace_line(old, new, 2), ("modified", 2))

class TraceLineDeleteTest(unittest.TestCase):
    def test_deleted_line_has_no_counterpart(self):
        old = ["a", "b", "c"]
        new = ["a", "c"]
        self.assertEqual(trace_line(old, new, 2), ("deleted", None))

    def test_all_lines_deleted(self):
        old = ["a", "b"]
        new = []
        self.assertEqual(trace_line(old, new, 1), ("deleted", None))
        self.assertEqual(trace_line(old, new, 2), ("deleted", None))


class TraceLineOutOfRangeTest(unittest.TestCase):
    def test_zero_is_out_of_range(self):
        self.assertEqual(trace_line(["a"], ["a"], 0), ("out_of_range", None))

    def test_negative_is_out_of_range(self):
        self.assertEqual(trace_line(["a"], ["a"], -1), ("out_of_range", None))

    def test_past_end_is_out_of_range(self):
        self.assertEqual(trace_line(["a", "b"], ["a", "b"], 3), ("out_of_range", None))

    def test_empty_old_text_is_always_out_of_range(self):
        self.assertEqual(trace_line([], ["a"], 1), ("out_of_range", None))


class TraceRangeTest(unittest.TestCase):
    def test_spans_multiple_opcode_blocks(self):
        old = ["a", "b", "c", "d"]
        new = ["a", "X", "c", "d"]
        results = trace_range(old, new, 1, 4)
        self.assertEqual(
            results,
            [
                (1, "unchanged", 1),
                (2, "modified", 2),
                (3, "unchanged", 3),
                (4, "unchanged", 4),
            ],
        )

    def test_matches_trace_line_for_each_member(self):
        old = ["a", "b", "c", "d", "e"]
        new = ["a", "B", "C", "e"]
        for line_no, status, new_line in trace_range(old, new, 1, 5):
            self.assertEqual(trace_line(old, new, line_no), (status, new_line))

    def test_range_mixing_found_and_out_of_range(self):
        old = ["a", "b"]
        new = ["a", "b"]
        results = trace_range(old, new, 1, 3)
        self.assertEqual(
            results,
            [
                (1, "unchanged", 1),
                (2, "unchanged", 2),
                (3, "out_of_range", None),
            ],
        )

    def test_single_line_range_equals_start_end(self):
        old = ["a", "b", "c"]
        new = ["a", "b", "c"]
        self.assertEqual(trace_range(old, new, 2, 2), [(2, "unchanged", 2)])

    def test_start_greater_than_end_raises(self):
        with self.assertRaises(ValueError):
            trace_range(["a"], ["a"], 2, 1)


class ParseUnifiedDiffTest(unittest.TestCase):
    def test_no_hunks_is_all_equal(self):
        old = ["a", "b", "c"]
        opcodes = parse_unified_diff("--- a\n+++ b\n", len(old))
        self.assertEqual(opcodes, [("equal", 0, 3, 0, 3)])

    def test_one_to_one_replace_hunk(self):
        diff = (
            "--- a\n"
            "+++ b\n"
            "@@ -1,4 +1,4 @@\n"
            " a\n"
            "-b\n"
            "+B\n"
            " c\n"
            " d\n"
        )
        old = ["a", "b", "c", "d"]
        results = trace_range_from_diff(old, diff, 1, 4)
        self.assertEqual(
            results,
            [
                (1, "unchanged", 1),
                (2, "modified", 2),
                (3, "unchanged", 3),
                (4, "unchanged", 4),
            ],
        )

    def test_gap_before_hunk_is_unchanged(self):
        # lines 1-3 sit outside the hunk's context and are never shown, but
        # they must still resolve as unchanged, shifted by nothing since
        # nothing before the hunk changed.
        diff = "--- a\n+++ b\n@@ -4,3 +4,3 @@\n d\n-e\n+E\n f\n"
        old = ["a", "b", "c", "d", "e", "f"]
        results = trace_range_from_diff(old, diff, 1, 6)
        self.assertEqual(
            results,
            [
                (1, "unchanged", 1),
                (2, "unchanged", 2),
                (3, "unchanged", 3),
                (4, "unchanged", 4),
                (5, "modified", 5),
                (6, "unchanged", 6),
            ],
        )

    def test_trailing_lines_after_last_hunk_are_unchanged(self):
        diff = "--- a\n+++ b\n@@ -1,2 +1,2 @@\n-a\n+A\n b\n"
        old = ["a", "b", "c"]
        results = trace_range_from_diff(old, diff, 1, 3)
        self.assertEqual(
            results,
            [
                (1, "modified", 1),
                (2, "unchanged", 2),
                (3, "unchanged", 3),
            ],
        )

    def test_pure_insertion_hunk_shifts_lines_after_it(self):
        diff = "--- a\n+++ b\n@@ -2,0 +3,2 @@\n+X\n+Y\n"
        old = ["a", "b", "c"]
        results = trace_range_from_diff(old, diff, 1, 3)
        self.assertEqual(
            results,
            [
                (1, "unchanged", 1),
                (2, "unchanged", 2),
                (3, "unchanged", 5),
            ],
        )

    def test_pure_deletion_hunk_leaves_deleted_lines_unmapped(self):
        diff = "--- a\n+++ b\n@@ -1,2 +0,0 @@\n-a\n-b\n"
        old = ["a", "b", "c"]
        results = trace_range_from_diff(old, diff, 1, 3)
        self.assertEqual(
            results,
            [
                (1, "deleted", None),
                (2, "deleted", None),
                (3, "unchanged", 1),
            ],
        )

    def test_out_of_range_line_beyond_old_file(self):
        diff = "--- a\n+++ b\n@@ -1,2 +1,2 @@\n a\n a\n"
        results = trace_range_from_diff(["x", "y"], diff, 1, 3)
        self.assertEqual(results[2], (3, "out_of_range", None))


if __name__ == "__main__":
    unittest.main()
