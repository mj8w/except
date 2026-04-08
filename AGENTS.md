# Project Guidance

## Python CLI Modules

- Keep CLI entry-point modules import-safe.
- Before `main()` runs, module-level code should be limited to imports, constants, type aliases, and function or class declarations.
- Do not perform analysis, file I/O, argument parsing, logging setup with side effects, or other runtime work at import time.
- Put execution behind `if __name__ == "__main__": raise SystemExit(main())`.

## Formatting And Checks

- Keep every line under 100 characters.
- Keep every statement on a single physical line; do not wrap statements across multiple lines.
- After making a change, run `isort` configured for single-line imports, then `black`, then `flake8`.
