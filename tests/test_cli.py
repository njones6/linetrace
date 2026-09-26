import io
import os
import tempfile
import unittest
from unittest import mock

from linetrace.cli import read_lines, read_text


class TempFileMixin:
    def make_file(self, data):
        handle, path = tempfile.mkstemp()
        os.close(handle)
        with open(path, "wb") as f:
            f.write(data)
        self.addCleanup(os.remove, path)
        return path


class ReadTextEncodingTest(TempFileMixin, unittest.TestCase):
    def test_plain_utf8(self):
        path = self.make_file("héllo\n".encode("utf-8"))
        self.assertEqual(read_text(path, False, "utf-8-sig"), "héllo\n")

    def test_utf8_bom_is_stripped_by_default_encoding(self):
        path = self.make_file(b"\xef\xbb\xbfhello\nworld\n")
        self.assertEqual(read_text(path, False, "utf-8-sig"), "hello\nworld\n")

    def test_explicit_encoding_for_non_utf8_file(self):
        path = self.make_file("café\n".encode("latin-1"))
        self.assertEqual(read_text(path, False, "latin-1"), "café\n")

    def test_wrong_encoding_raises_value_error(self):
        path = self.make_file("café\n".encode("latin-1"))
        with self.assertRaises(ValueError):
            read_text(path, False, "utf-8-sig")

    def test_unknown_encoding_name_raises_value_error(self):
        path = self.make_file(b"hello\n")
        with self.assertRaises(ValueError):
            read_text(path, False, "not-a-real-encoding")


class ReadLinesLineEndingTest(TempFileMixin, unittest.TestCase):
    def test_crlf_file_splits_like_lf_file(self):
        crlf_path = self.make_file(b"a\r\nb\r\nc\r\n")
        lf_path = self.make_file(b"a\nb\nc\n")
        self.assertEqual(
            read_lines(crlf_path, False, "utf-8-sig"),
            read_lines(lf_path, False, "utf-8-sig"),
        )
        self.assertEqual(read_lines(crlf_path, False, "utf-8-sig"), ["a", "b", "c"])

    def test_bare_cr_file_also_splits_correctly(self):
        path = self.make_file(b"a\rb\rc")
        self.assertEqual(read_lines(path, False, "utf-8-sig"), ["a", "b", "c"])

    def test_mixed_line_endings_in_one_file(self):
        path = self.make_file(b"a\r\nb\nc\r\n")
        self.assertEqual(read_lines(path, False, "utf-8-sig"), ["a", "b", "c"])


class ReadTextStdinTest(unittest.TestCase):
    def test_stdin_used_twice_raises(self):
        with self.assertRaises(ValueError):
            read_text("-", True, "utf-8-sig")

    def test_stdin_is_decoded_with_requested_encoding(self):
        fake_stdin = mock.Mock()
        fake_stdin.buffer = io.BytesIO("café\n".encode("latin-1"))
        with mock.patch("linetrace.cli.sys.stdin", fake_stdin):
            self.assertEqual(read_text("-", False, "latin-1"), "café\n")

    def test_stdin_with_crlf_splits_like_a_file_would(self):
        fake_stdin = mock.Mock()
        fake_stdin.buffer = io.BytesIO(b"a\r\nb\r\n")
        with mock.patch("linetrace.cli.sys.stdin", fake_stdin):
            self.assertEqual(read_lines("-", False, "utf-8-sig"), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
