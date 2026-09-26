# linetrace

Ordinary diff tools tell you *what* changed between two texts. They don't
answer a narrower, more common question: I'm looking at line 42 of the old
file, and I have no idea where that content is now, or whether it's still
there at all.

`linetrace` answers exactly that question, and nothing else. Give it an old
text, a new text, and a line number, and it tells you the fate of that line:
still there unchanged, moved and modified, or gone.

## Usage

```
linetrace OLD NEW --line N
linetrace OLD --diff PATCH --line N
```

`OLD` and `NEW` are file paths. Exactly one of `NEW` or `--diff` is required.
Among `OLD`, `NEW`, and `PATCH`, at most one can be `-` to read from stdin.
`N` can be a single line number or an inclusive range like `10-14`.

### Two files on disk

```
$ linetrace old_config.yaml new_config.yaml --line 17
line 17: unchanged, now at line 21
```

### Comparing against a previous git revision

This is the case stdin support is for: you don't want to write a temp file
just to diff against history.

```
$ git show HEAD~3:src/server.py | linetrace - src/server.py --line 88
line 88: modified, now approximately at line 94
```

### Tracing against a patch instead of a new file

If you have a unified diff (a saved PR patch, the output of `git diff`, or
`diff -u OLD NEW`) but not a checkout of the new version, pass it with
`--diff` instead of a `NEW` argument. Only `OLD` is read from disk; the
patch's hunk headers and +/-/context lines are enough to work out where
lines land.

```
$ git diff main..feature -- src/server.py > server.patch
$ linetrace src/server.py --diff server.patch --line 88
line 88: modified, now approximately at line 94
```

A patch that only covers part of the file works fine: lines outside any
hunk are assumed unchanged, shifted by whatever hunks came before them.

### A line that no longer exists

```
$ linetrace v1.txt v2.txt --line 5
line 5: deleted, no counterpart in the new text
```

### A range of lines

```
$ linetrace old_config.yaml new_config.yaml --line 15-18
line 15: unchanged, now at line 19
line 16: unchanged, now at line 20
line 17: unchanged, now at line 21
line 18: modified, now approximately at line 22
```

Each line in the range is resolved independently and printed on its own
line, in order.

### Encoding and line endings

Files and stdin are read as UTF-8 by default (`utf-8-sig`, so a leading
byte-order mark is stripped rather than glued onto the first line). Pass
`--encoding` if a file uses something else:

```
$ linetrace legacy_v1.txt legacy_v2.txt --line 5 --encoding latin-1
```

Line splitting treats CR, LF, and CRLF as equivalent line endings, so
comparing a Windows-edited file against a Unix one, or a file with mixed
endings, works the same as comparing two consistent files.

### JSON output

```
$ linetrace old_config.yaml new_config.yaml --line 15-18 --format json
[
  {
    "line": 15,
    "status": "unchanged",
    "new_line": 19
  },
  {
    "line": 18,
    "status": "modified",
    "new_line": 22
  }
]
```

`new_line` is `null` for `deleted` and `out_of_range` results. An
`out_of_range` record also carries `old_line_count`, the number of lines in
the old text, for the same reason the text output includes it in its
message.

### Exit codes

`0` if every requested line was found (unchanged, modified, or deleted are
all "found" outcomes), `1` if any requested line number doesn't exist in the
old text, `2` on usage errors such as an unreadable file or using `-` twice.

## How it works

With two files, `linetrace` runs Python's `difflib.SequenceMatcher` over
the two texts, split into lines. With `--diff`, it parses the patch's hunk
headers and line prefixes into the same shape of opcode instead, without
ever reading a new file. Either way, it looks at which opcode block
contains the requested line:

- inside an `equal` block: the line is unchanged, and its new position is
  computed from the block's offset.
- inside a `replace` block: there's no line-for-line mapping to point to,
  so the reported new line is a proportional guess based on where the old
  line sits within the replaced span.
- inside a `delete` block, or a `replace` block with no new-side lines: the
  line has nothing to map to.

The proportional guess for "modified" lines is a heuristic, not a proof.
For a one-line-to-one-line replacement it's exact; for larger blocks it's a
reasonable starting point to look near, not a guarantee.

## Installing

No dependencies beyond the standard library.

```
pip install -e .
```

or just run it in place:

```
python -m linetrace OLD NEW --line N
```

## Status

Early skeleton. Supports single lines and ranges, plus text and JSON output,
against either two files or a unified diff, with a test suite covering the
opcode resolution logic and encoding/line-ending handling. Multi-file patches
(picking one target file out of a patch touching several) are still to come.
