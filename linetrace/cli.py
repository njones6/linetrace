import argparse
import sys

from . import trace_range

STATUS_TEXT = {
    "unchanged": "unchanged, now at line {n}",
    "modified": "modified, now approximately at line {n}",
    "deleted": "deleted, no counterpart in the new text",
    "out_of_range": "line {line} does not exist in the old text ({count} lines)",
}


def parse_line_spec(value):
    """Parse a --line argument: either "N" or a range "N-M"."""
    start_str, sep, end_str = value.partition("-")
    try:
        start = int(start_str)
        end = int(end_str) if sep else start
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid line number or range: {value!r}")
    if start > end:
        raise argparse.ArgumentTypeError(f"range start must be <= end: {value!r}")
    return (start, end)


def read_lines(path, stdin_used):
    """Read a file's lines. `path` of "-" means stdin, allowed only once."""
    if path == "-":
        if stdin_used:
            raise ValueError("cannot read stdin for both files")
        text = sys.stdin.read()
    else:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    return text.splitlines()


def build_parser():
    parser = argparse.ArgumentParser(
        prog="linetrace",
        description=(
            "Trace where a line from an old version of a text ended up in a "
            "new version, based on a diff between the two."
        ),
    )
    parser.add_argument("old", help="path to the old file, or - for stdin")
    parser.add_argument("new", help="path to the new file, or - for stdin")
    parser.add_argument(
        "--line",
        type=parse_line_spec,
        required=True,
        metavar="N|N-M",
        help="1-indexed line number, or inclusive range N-M, in the old file to trace",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.old == "-" and args.new == "-":
        print("linetrace: only one of OLD/NEW can be -", file=sys.stderr)
        return 2

    try:
        old_lines = read_lines(args.old, stdin_used=False)
        new_lines = read_lines(args.new, stdin_used=(args.old == "-"))
    except (OSError, ValueError) as exc:
        print(f"linetrace: {exc}", file=sys.stderr)
        return 2

    start, end = args.line
    results = trace_range(old_lines, new_lines, start, end)

    any_out_of_range = False
    for line_no, status, new_line in results:
        if status == "out_of_range":
            any_out_of_range = True
            message = STATUS_TEXT[status].format(line=line_no, count=len(old_lines))
        else:
            message = STATUS_TEXT[status].format(n=new_line)
        print(f"line {line_no}: {message}")

    return 1 if any_out_of_range else 0


if __name__ == "__main__":
    sys.exit(main())
