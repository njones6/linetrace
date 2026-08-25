import argparse
import sys

from . import trace_line

STATUS_TEXT = {
    "unchanged": "unchanged, now at line {n}",
    "modified": "modified, now approximately at line {n}",
    "deleted": "deleted, no counterpart in the new text",
    "out_of_range": "line {line} does not exist in the old text ({count} lines)",
}


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
        type=int,
        required=True,
        metavar="N",
        help="1-indexed line number in the old file to trace",
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

    status, new_line = trace_line(old_lines, new_lines, args.line)

    if status == "out_of_range":
        message = STATUS_TEXT[status].format(line=args.line, count=len(old_lines))
    else:
        message = STATUS_TEXT[status].format(n=new_line)

    print(f"line {args.line}: {message}")
    return 0 if status != "out_of_range" else 1


if __name__ == "__main__":
    sys.exit(main())
