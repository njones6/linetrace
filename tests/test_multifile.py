import unittest

from linetrace import select_file_diff, split_file_diffs, trace_range_from_diff

GIT_PATCH = """\
commit 1234
Author: someone

    two files

diff --git a/src/server.py b/src/server.py
index 111..222 100644
--- a/src/server.py
+++ b/src/server.py
@@ -2,2 +2,3 @@
 b
+inserted
 c
diff --git a/docs/server.md b/docs/server.md
index 333..444 100644
--- a/docs/server.md
+++ b/docs/server.md
@@ -1,2 +1,2 @@
-old title
+new title
 body
"""

PLAIN_PATCH = """\
--- one.txt\t2024-01-01 00:00:00
+++ one.txt\t2024-01-02 00:00:00
@@ -1,2 +1,2 @@
-x
+y
 z
--- two.txt\t2024-01-01 00:00:00
+++ two.txt\t2024-01-02 00:00:00
@@ -1 +1,2 @@
 q
+r
"""


class SplitFileDiffsTest(unittest.TestCase):
    def test_git_patch_yields_one_entry_per_file(self):
        files = split_file_diffs(GIT_PATCH)
        self.assertEqual([(old, new) for old, new, _ in files],
                         [("src/server.py", "src/server.py"), ("docs/server.md", "docs/server.md")])

    def test_text_holds_only_that_files_hunks(self):
        _, _, text = split_file_diffs(GIT_PATCH)[0]
        self.assertIn("+inserted", text)
        self.assertNotIn("new title", text)

    def test_plain_diff_u_output_without_git_headers(self):
        files = split_file_diffs(PLAIN_PATCH)
        self.assertEqual([old for old, _, _ in files], ["one.txt", "two.txt"])

    def test_removed_line_that_looks_like_a_file_header_stays_in_its_hunk(self):
        patch = (
            "--- a.txt\n+++ a.txt\n"
            "@@ -1,3 +1,2 @@\n"
            " keep\n"
            "--- not a header\n"
            "+++ also not a header\n"
            " end\n"
        )
        # old side: keep, "-- not a header", end -> 3 lines; new side: keep, "++ also...", end -> 3
        patch = patch.replace("@@ -1,3 +1,2 @@", "@@ -1,3 +1,3 @@")
        files = split_file_diffs(patch)
        self.assertEqual(len(files), 1)
        self.assertIn("--- not a header", files[0][2])

    def test_pure_rename_uses_git_header_paths(self):
        patch = "diff --git a/old.txt b/new.txt\nsimilarity index 100%\nrename from old.txt\nrename to new.txt\n"
        self.assertEqual(split_file_diffs(patch), [("old.txt", "new.txt", "")])

    def test_bare_hunks_with_no_headers_give_no_files(self):
        self.assertEqual(split_file_diffs("@@ -1 +1 @@\n-a\n+b\n"), [])


class SelectFileDiffTest(unittest.TestCase):
    def test_multi_file_patch_without_target_is_an_error(self):
        with self.assertRaises(ValueError) as ctx:
            select_file_diff(GIT_PATCH)
        self.assertIn("--target", str(ctx.exception))

    def test_single_file_patch_needs_no_target(self):
        text = select_file_diff(split_file_text(PLAIN_PATCH, 0))
        self.assertIn("+y", text)

    def test_bare_hunks_are_returned_unchanged(self):
        bare = "@@ -1 +1 @@\n-a\n+b\n"
        self.assertEqual(select_file_diff(bare), bare)

    def test_exact_path_match(self):
        self.assertIn("+inserted", select_file_diff(GIT_PATCH, "src/server.py"))

    def test_trailing_components_match(self):
        self.assertIn("new title", select_file_diff(GIT_PATCH, "server.md"))

    def test_leading_dot_slash_is_ignored(self):
        self.assertIn("+inserted", select_file_diff(GIT_PATCH, "./src/server.py"))

    def test_matches_new_path_after_a_rename(self):
        patch = "--- old.txt\n+++ new.txt\n@@ -1 +1 @@\n-a\n+b\n"
        self.assertIn("+b", select_file_diff(patch, "new.txt"))
        self.assertIn("+b", select_file_diff(patch, "old.txt"))

    def test_unknown_target_is_an_error(self):
        with self.assertRaises(ValueError):
            select_file_diff(GIT_PATCH, "missing.py")

    def test_partial_name_does_not_match_mid_component(self):
        with self.assertRaises(ValueError):
            select_file_diff(GIT_PATCH, "erver.py")

    def test_ambiguous_target_is_an_error(self):
        patch = (
            "--- a/x/f.txt\n+++ b/x/f.txt\n@@ -1 +1 @@\n-a\n+b\n"
            "--- a/y/f.txt\n+++ b/y/f.txt\n@@ -1 +1 @@\n-c\n+d\n"
        )
        with self.assertRaises(ValueError):
            select_file_diff(patch, "f.txt")
        self.assertIn("+b", select_file_diff(patch, "x/f.txt"))


def split_file_text(patch, index):
    return split_file_diffs(patch)[index][2]


class TraceThroughSelectedFileTest(unittest.TestCase):
    def test_selected_hunks_map_lines_for_that_file_only(self):
        old = ["a", "b", "c"]
        text = select_file_diff(GIT_PATCH, "src/server.py")
        results = trace_range_from_diff(old, text, 3, 3)
        self.assertEqual(results, [(3, "unchanged", 4)])

        other = ["old title", "body"]
        text = select_file_diff(GIT_PATCH, "docs/server.md")
        results = trace_range_from_diff(other, text, 1, 2)
        self.assertEqual(results, [(1, "modified", 1), (2, "unchanged", 2)])


if __name__ == "__main__":
    unittest.main()
