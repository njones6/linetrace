"""Trace what happened to a single line between two versions of a text."""

import difflib
import re

__version__ = "0.1.0"

_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _opcode_at(opcodes, index):
    """Find the opcode tuple covering `index` on the a-side, or None if past the end."""
    for tag, i1, i2, j1, j2 in opcodes:
        if i1 <= index < i2:
            return tag, i1, i2, j1, j2
    # get_opcodes() covers every index in a, so this is unreachable in practice
    return None


def _resolve(opcode, index):
    if opcode is None:
        return ("deleted", None)

    tag, i1, i2, j1, j2 = opcode

    if tag == "equal":
        offset = index - i1
        return ("unchanged", j1 + offset + 1)

    if tag == "replace" and j2 > j1:
        old_span = i2 - i1
        new_span = j2 - j1
        offset = index - i1
        approx = j1 + (offset * new_span) // old_span
        return ("modified", approx + 1)

    # tag is "delete", or "replace" with an empty new-side span
    return ("deleted", None)


def trace_line(old_lines, new_lines, line_no):
    """Find out what became of line `line_no` (1-indexed) from old_lines in new_lines.

    Returns a tuple (status, new_line_no):
      ("unchanged", n)  - the line is present verbatim at new line n
      ("modified", n)   - the line's neighborhood was replaced; n is the
                           best-guess landing spot, proportional to where the
                           line sat within the replaced block
      ("deleted", None) - the line has no counterpart in the new text
      ("out_of_range", None) - line_no does not exist in old_lines
    """
    if line_no < 1 or line_no > len(old_lines):
        return ("out_of_range", None)

    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    opcode = _opcode_at(matcher.get_opcodes(), line_no - 1)
    return _resolve(opcode, line_no - 1)


def _trace_range_with_opcodes(opcodes, old_line_count, start, end):
    if start > end:
        raise ValueError(f"range start ({start}) must be <= end ({end})")

    results = []
    for line_no in range(start, end + 1):
        if line_no < 1 or line_no > old_line_count:
            results.append((line_no, "out_of_range", None))
            continue
        status, new_line = _resolve(_opcode_at(opcodes, line_no - 1), line_no - 1)
        results.append((line_no, status, new_line))
    return results


def trace_range(old_lines, new_lines, start, end):
    """Trace every line from `start` to `end` (1-indexed, inclusive).

    Equivalent to calling trace_line for each line in the range, but builds
    the SequenceMatcher once and reuses its opcodes instead of redoing the
    diff for every line.

    Returns a list of (line_no, status, new_line_no) tuples, one per line.
    """
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    return _trace_range_with_opcodes(matcher.get_opcodes(), len(old_lines), start, end)


def parse_unified_diff(diff_text, old_line_count):
    """Parse a unified diff into difflib-style opcodes over `old_line_count` lines.

    Only hunk headers and the +/-/space line prefixes are read; the actual
    old and new file contents are never consulted, so this works from a
    patch alone. A patch covering more than one file will have its hunks
    read as if they all applied to the same file - callers are expected to
    pass a single-file diff.

    Returns a list of (tag, i1, i2, j1, j2) tuples covering every index in
    [0, old_line_count), in the same shape as difflib.SequenceMatcher.get_opcodes().
    """
    opcodes = []
    old_pos = 0
    new_pos = 0

    lines = diff_text.splitlines()
    idx = 0
    while idx < len(lines):
        match = _HUNK_HEADER_RE.match(lines[idx])
        if match is None:
            idx += 1
            continue

        old_start_raw = int(match.group(1))
        old_len = int(match.group(2)) if match.group(2) is not None else 1
        new_start_raw = int(match.group(3))
        new_len = int(match.group(4)) if match.group(4) is not None else 1
        idx += 1

        # A zero-length side means "no lines here", and the unified diff
        # format then gives that side's position directly rather than as a
        # 1-indexed line number, so it needs no -1 to become a 0-index.
        old_start = old_start_raw if old_len == 0 else old_start_raw - 1
        new_start = new_start_raw if new_len == 0 else new_start_raw - 1

        if old_start > old_pos:
            gap = old_start - old_pos
            opcodes.append(("equal", old_pos, old_start, new_pos, new_pos + gap))
            new_pos += gap
        old_pos = old_start
        new_pos = new_start

        old_consumed = 0
        new_consumed = 0
        run_removed = 0
        run_added = 0

        def flush_run():
            nonlocal run_removed, run_added, old_pos, new_pos
            if not run_removed and not run_added:
                return
            i1, j1 = old_pos, new_pos
            old_pos += run_removed
            new_pos += run_added
            if run_removed and run_added:
                opcodes.append(("replace", i1, old_pos, j1, new_pos))
            elif run_removed:
                opcodes.append(("delete", i1, old_pos, j1, j1))
            else:
                opcodes.append(("insert", i1, i1, j1, new_pos))
            run_removed = run_added = 0

        while (old_consumed < old_len or new_consumed < new_len) and idx < len(lines):
            line = lines[idx]
            if line.startswith(" "):
                flush_run()
                opcodes.append(("equal", old_pos, old_pos + 1, new_pos, new_pos + 1))
                old_pos += 1
                new_pos += 1
                old_consumed += 1
                new_consumed += 1
            elif line.startswith("-"):
                run_removed += 1
                old_consumed += 1
            elif line.startswith("+"):
                run_added += 1
                new_consumed += 1
            elif line.startswith("\\"):
                pass  # "\ No newline at end of file"
            else:
                break
            idx += 1
        flush_run()

    if old_pos < old_line_count:
        opcodes.append(("equal", old_pos, old_line_count, new_pos, new_pos + (old_line_count - old_pos)))

    return opcodes


def trace_range_from_diff(old_lines, diff_text, start, end):
    """Like trace_range, but the new text is described by a unified diff instead of given directly.

    Useful when you have the old file on disk and a patch (say, from
    `git diff` or a saved PR patch) but not a checkout of the new version.
    """
    opcodes = parse_unified_diff(diff_text, len(old_lines))
    return _trace_range_with_opcodes(opcodes, len(old_lines), start, end)
