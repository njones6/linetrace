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
```

`OLD` and `NEW` are file paths. Either one (but not both) can be `-` to read
from stdin. `N` can be a single line number or an inclusive range like `10-14`.

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

### Exit codes

`0` if every requested line was found (unchanged, modified, or deleted are
all "found" outcomes), `1` if any requested line number doesn't exist in the
old text, `2` on usage errors such as an unreadable file or using `-` twice.

## How it works

`linetrace` runs Python's `difflib.SequenceMatcher` over the two texts,
split into lines, and looks at which opcode block contains the requested
line:

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

Early skeleton. Supports single lines and ranges; JSON output, unified diff
input, a real test suite, and CRLF/encoding handling are still to come.
