"""Trace what happened to a single line between two versions of a text."""

import difflib

__version__ = "0.1.0"


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


def trace_range(old_lines, new_lines, start, end):
    """Trace every line from `start` to `end` (1-indexed, inclusive).

    Equivalent to calling trace_line for each line in the range, but builds
    the SequenceMatcher once and reuses its opcodes instead of redoing the
    diff for every line.

    Returns a list of (line_no, status, new_line_no) tuples, one per line.
    """
    if start > end:
        raise ValueError(f"range start ({start}) must be <= end ({end})")

    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    opcodes = matcher.get_opcodes()

    results = []
    for line_no in range(start, end + 1):
        if line_no < 1 or line_no > len(old_lines):
            results.append((line_no, "out_of_range", None))
            continue
        status, new_line = _resolve(_opcode_at(opcodes, line_no - 1), line_no - 1)
        results.append((line_no, status, new_line))
    return results
