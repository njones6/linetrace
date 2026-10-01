import argparse
import json
import sys

from . import select_file_diff, trace_range, trace_range_from_diff

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


def read_text(path, stdin_used, encoding):
    """Read a file's raw text, decoded from bytes. `path` of "-" means stdin, allowed only once.

    Reading bytes and decoding ourselves, rather than opening in text mode,
    means the same code path works for both real files and stdin - stdin's
    encoding otherwise depends on the platform's locale, which isn't a given
    for input piped from somewhere like `git show`.
    """
    if path == "-":
        if stdin_used:
            raise ValueError("cannot read stdin for more than one input")
        data = sys.stdin.buffer.read()
    else:
        with open(path, "rb") as handle:
            data = handle.read()
    try:
        return data.decode(encoding)
    except LookupError as exc:
        raise ValueError(f"unknown encoding {encoding!r}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path}: could not decode as {encoding}: {exc}") from exc


def read_lines(path, stdin_used, encoding):
    """Read a file's lines. `path` of "-" means stdin, allowed only once.

    str.splitlines() splits on CR, LF, and CRLF alike, so old and new files
    with different line-ending conventions still compare line-for-line.
    """
    return read_text(path, stdin_used, encoding).splitlines()


def build_parser():
    parser = argparse.ArgumentParser(
        prog="linetrace",
        description=(
            "Trace where a line from an old version of a text ended up in a "
            "new version, based on a diff between the two."
        ),
    )
    parser.add_argument("old", help="path to the old file, or - for stdin")
    parser.add_argument(
        "new",
        nargs="?",
        help="path to the new file, or - for stdin (omit if --diff is given)",
    )
    parser.add_argument(
        "--diff",
        metavar="PATCH",
        help=(
            "unified diff file (or - for stdin) describing the change, used "
            "instead of NEW when you don't have the new file itself"
        ),
    )
    parser.add_argument(
        "--target",
        metavar="FILE",
        help=(
            "which file to use when --diff holds a patch for several; matched "
            "against the old or new path, so a trailing part like server.py is enough"
        ),
    )
    parser.add_argument(
        "--line",
        type=parse_line_spec,
        required=True,
        metavar="N|N-M",
        help="1-indexed line number, or inclusive range N-M, in the old file to trace",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        metavar="ENC",
        help=(
            "text encoding for OLD, NEW, and PATCH (default: utf-8-sig, which "
            "reads plain UTF-8 fine and also strips a UTF-8 byte-order mark "
            "if one is present)"
        ),
    )
    return parser


def format_json(results, old_line_count):
    records = []
    for line_no, status, new_line in results:
        record = {"line": line_no, "status": status, "new_line": new_line}
        if status == "out_of_range":
            record["old_line_count"] = old_line_count
        records.append(record)
    return json.dumps(records, indent=2)


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.new is None and args.diff is None:
        print("linetrace: one of NEW or --diff is required", file=sys.stderr)
        return 2
    if args.new is not None and args.diff is not None:
        print("linetrace: NEW and --diff are mutually exclusive", file=sys.stderr)
        return 2

    if args.target is not None and args.diff is None:
        print("linetrace: --target only applies together with --diff", file=sys.stderr)
        return 2

    stdin_inputs =[value for value in (args.old, args.new, args.diff) if value == "-"]
    if len(stdin_inputs) > 1:
        print("linetrace: only one input can be -", file=sys.stderr)
        return 2

    try:
        old_lines = read_lines(args.old, stdin_used=False, encoding=args.encoding)
        if args.diff is not None:
            diff_text = read_text(args.diff, stdin_used=(args.old == "-"), encoding=args.encoding)
            diff_text = select_file_diff(diff_text, args.target)
        else:
            new_lines = read_lines(args.new, stdin_used=(args.old == "-"), encoding=args.encoding)
    except (OSError, ValueError) as exc:
        print(f"linetrace: {exc}", file=sys.stderr)
        return 2

    start, end = args.line
    if args.diff is not None:
        results = trace_range_from_diff(old_lines, diff_text, start, end)
    else:
        results = trace_range(old_lines, new_lines, start, end)
    any_out_of_range = any(status == "out_of_range" for _, status, _ in results)

    if args.format == "json":
        print(format_json(results, len(old_lines)))
    else:
        for line_no, status, new_line in results:
            if status == "out_of_range":
                message = STATUS_TEXT[status].format(line=line_no, count=len(old_lines))
            else:
                message = STATUS_TEXT[status].format(n=new_line)
            print(f"line {line_no}: {message}")

    return 1 if any_out_of_range else 0


if __name__ == "__main__":
    sys.exit(main())
