# except

`except` is a command line tool for exploring the potential exception surface of
a Python statement.

You point it at a Python file and a line number. The tool:

- locates the statement on that line
- finds function calls made by that statement
- resolves calls to functions defined in the same file
- walks the reachable call tree
- reports explicit `raise` sites and unresolved calls

This first implementation is intentionally conservative. It does not claim to
prove the exact runtime behavior. Instead, it gives a useful static starting
point for answering: "what exceptions could this statement trigger?"

## Usage

```bash
python -m except_tool.cli path/to/file.py 12
```

Or after installation:

```bash
except path/to/file.py 12
```

## Example output

```text
Statement at line 18: data = load_config(path)

Potential exceptions:
- ValueError via load_config -> parse_config (line 7)

Unresolved calls:
- open via load_config
```

## Limitations

- only resolves functions defined in the same module
- does not yet model imports, methods, dynamic dispatch, decorators, or type-based dispatch
- only reports explicit `raise` statements from resolved functions
- does not infer all implicit exceptions from operations such as indexing or arithmetic
