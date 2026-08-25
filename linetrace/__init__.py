"""Trace what happened to a single line between two versions of a text."""

import difflib

__version__ = "0.1.0"


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

    index = line_no - 1
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if not (i1 <= index < i2):
            continue

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

    # get_opcodes() covers every index in a, so this should be unreachable
    return ("deleted", None)
