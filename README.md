# except

`except` is a small command line tool for answering a question Python makes
surprisingly hard to answer:

What exceptions can this line of code raise?

The goal is not to replace reading code. The goal is to make reading code less
lonely. Point `except` at a file and a line number, and it will walk the local
call tree, collect exception candidates, and show how those exceptions move back
toward the line you care about.

It is built for people doing real maintenance work: reviewing a risky change,
hardening a CLI, tracing a web endpoint, documenting behavior before a refactor,
or trying to understand why a line that looks harmless has teeth.

## Why Use It

Python exceptions are part of a function's contract, but they usually live in
the shadows. They can come from explicit `raise` statements, builtins like
`int()` and `open()`, implicit operations like indexing or division, and library
calls whose implementation may not even be Python source.

`except` gives you a conservative static report:

- which local calls are reachable from the selected line
- which exceptions are raised at each level
- which exceptions still escape after local `try`/`except` handling
- which exceptions are swallowed before they reach the caller
- which builtins, stdlib calls, and library calls are backed by summaries
- which imported Python modules can be traversed from real source
- which calls remain unresolved and need human attention

The main audience is Python developers who want a fast first pass before making
control-flow decisions. It is especially useful when you are deciding what to
catch, what to document, and what not to hide.

## Install

From this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

You can also run through the venv interpreter without activating it:

```powershell
.\.venv\Scripts\python.exe -m except_tool.cli path/to/file.py 12
```

Or use the installed console command:

```bash
except path/to/file.py 12
```

## Command Line

```text
except SOURCE_FILE LINE [--format summary|tree]
```

Arguments:

- `SOURCE_FILE`: path to the Python file to inspect
- `LINE`: line number containing the statement or function body to analyze

Options:

- `--format summary`: compact output grouped by explicit and implicit exception
  findings. This is the default.
- `--format tree`: two-column call-tree output showing current exceptions at
  each call level, including summary and source-confidence tags.

## Summary Output

Summary mode answers "what could reach this statement?" in a compact form.

```bash
except scratch_exception_demo.py 27
```

```text
Statement at line 27: return ratio_from_file("missing.txt", 0)

Potential exceptions (explicit raise):
- ValueError via ratio_from_file -> read_number -> parse_number (line 8): empty input

Potential exceptions (implicit operations):
- ZeroDivisionError via ratio_from_file (line 23) [arithmetic]
- FileNotFoundError via ratio_from_file -> read_number -> open (line 13) [builtin summary]
- OSError via ratio_from_file -> read_number -> open (line 13) [builtin summary]
- TypeError via ratio_from_file -> read_number -> parse_number -> int (line 8) [builtin summary]
- ValueError via ratio_from_file -> read_number -> parse_number -> int (line 8) [builtin summary]
```

## Tree Output

Tree mode is the heart of the tool. The left column is the call tree. The right
column shows the exception state at that row.

Plain exception names are exceptions that escape that call. Bracketed notes show
what happened at that level:

- `[raises ValueError]`: this call introduces `ValueError`
- `[swallows ValueError]`: this call catches `ValueError` and does not re-raise it
- `[builtin summary]`: the row comes from a known builtin exception table
- `[stdlib summary]`: the row comes from a curated stdlib summary
- `[stdlib source]`: the row was traversed from Python stdlib source
- `[library summary]`: the row comes from a curated third-party summary
- `[library source]`: the row was traversed from importable third-party Python source

```bash
except scratch_exception_demo.py 27 --format tree
```

```text
Call tree             Exceptions
ratio_from_file       FileNotFoundError, OSError, TypeError, ZeroDivisionError
                      [raises ZeroDivisionError]
  read_number         FileNotFoundError, OSError, TypeError; [swallows ValueError]
    open              FileNotFoundError, OSError; [builtin summary]
    parse_number      TypeError, ValueError; [raises ValueError]
      int             TypeError, ValueError; [builtin summary]
```

That table says `ValueError` can happen inside `parse_number`, but it is caught
inside `read_number`, so it does not escape up to `ratio_from_file`.

## Source And Summary Tags

`except` now uses a few different confidence levels when it reports a call:

- builtin summary: known exception sets for builtins like `open()` and `int()`
- stdlib summary: curated stdlib method summaries like `pathlib.Path.read_text()`
- stdlib source: imported stdlib Python source that `except` can actually walk
- library summary: curated third-party summaries such as `requests.get`
- library source: imported third-party Python source that `except` can walk

This distinction matters. It tells you whether a row was inferred from actual
Python source or from a maintained summary table.

For example, builtins now show up as first-class rows instead of unresolved
calls:

```text
Call tree             Exceptions
load_value            FileNotFoundError, OSError, TypeError, ValueError
  read_number         FileNotFoundError, OSError, TypeError, ValueError
    open              FileNotFoundError, OSError; [builtin summary]
    parse_number      TypeError, ValueError; [raises ValueError]
      int             TypeError, ValueError; [builtin summary]
```

Pure-Python stdlib code can also be traversed:

```text
Call tree             Exceptions
parse_payload         IndexError, JSONDecodeError, KeyError, TypeError
  json.loads          IndexError, JSONDecodeError, KeyError, TypeError
                      [raises IndexError, JSONDecodeError, KeyError, TypeError]
                      [stdlib source]
```

And high-value stdlib methods can use targeted summaries:

```text
Call tree             Exceptions
read_config           FileNotFoundError, OSError, UnicodeDecodeError
  pathlib.Path        -
  pathlib.Path.read_text
                      FileNotFoundError, OSError, UnicodeDecodeError
                      [stdlib summary]
```

## Library Summaries

Some third-party calls are not practical to inspect statically. A package may
be compiled, dynamic, or installed without source. For those cases, `except`
can use curated summaries for known library calls.

For example, this import:

```python
from requests import get
```

is resolved as `requests.get` and shown with a library summary:

```text
Call tree             Exceptions
fetch_status          ConnectionError, RequestException, Timeout, TooManyRedirects
  requests.get        ConnectionError, RequestException, Timeout, TooManyRedirects
                      [library summary]
```

The summary is intentionally labeled. It is useful, but it is not the same as
proving the behavior from source.

## Development

Run tests and checks through the local environment:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m isort .
.\.venv\Scripts\python.exe -m black .
.\.venv\Scripts\python.exe -m flake8 --jobs=1
```

On this Windows setup, `flake8 --jobs=1` avoids multiprocessing permission
issues while still checking the same files.

## Current Limits

`except` is useful today, but it is still conservative:

- local resolution is module-scoped
- method calls are only lightly inferred when local assignments make the target obvious
- deep dynamic dispatch is not modeled
- library knowledge still depends partly on curated summaries
- type-specific exception behavior is not yet inferred
- decorators and framework routing are parsed as ordinary Python
- implicit operation inference is intentionally broad in some places

That honesty is part of the tool. A good exception report should help you see
where your confidence ends.

## License

MIT
