# Development

```bash
uv sync
uv run pre-commit install
scripts/lint
scripts/test
scripts/develop
```

The pre-commit hooks run the formatter, the linter, the type checker, and the
tests before each commit. CI runs the same hooks on all files, so a commit that
passes locally also passes the gate. `scripts/lint` runs all hooks except the
tests on all files.

`scripts/develop` starts Home Assistant from `config/` with the demo
integration and a few sample scenes, and it links this component into it.
