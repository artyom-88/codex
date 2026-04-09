# Python CI Parity

Load this file when changing tracked `.py` files in this repo or when debugging `Python Quality` or `Python Security` CI failures.

- For fast iteration, start with focused tests for the touched area.
- Before commit or push after tracked Python changes, run the exact repo CI gates:
  - `pylint --rcfile .pylintrc $(git ls-files '*.py')`
  - `bandit -q $(git ls-files '*.py')`
- Prefer the directory-based `python3 -m unittest discover -s <path> -p 'test_*.py'` commands in this repo over module-addressed `python3 -m unittest package.module` invocations when tests import local helpers such as `test_support`.
- If the change touches `skills/memory-refiner/`, run:
  - `python3 -m unittest discover -s skills/memory-refiner/tests -p 'test_*.py'`
- If the change touches `tools/signoz-codex/`, run:
  - `python3 -m unittest discover -s tools/signoz-codex/tests -p 'test_*.py'`
- Prefer extracting shared helpers over suppressing `pylint` duplicate-code warnings in tests and small utilities.
