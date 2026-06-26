# Contributing to RecallPy

Thanks for your interest! RecallPy is an open-source project and we welcome contributions of all kinds.

## Ways to contribute

- **Report a bug** — open a [GitHub issue](https://github.com/rehanpunjwani/TokenGuard/issues) with steps to reproduce.
- **Suggest a feature** — describe what you're trying to solve and how you envision it working.
- **Submit a PR** — see [Development guide](docs/development.md) for setup, testing, and code style.
- **Improve docs** — the documentation site lives under `docs/` and uses mkdocs-material.

## Pull request guidelines

1. **Start with an issue** — let's discuss before you write code, especially for larger changes.
2. **Keep PRs focused** — one feature or fix per PR. Refactoring belongs in its own PR.
3. **Run the checks** before opening:
   ```bash
   pip install -e ".[dev]"
   ruff check src/ tests/
   ruff format --check src/ tests/
    ty check src/ tests/
   pytest
   ```
4. **No hardcoded secrets** — API keys and tokens must be read from environment variables (see `settings.py` for examples).
5. **Add or update tests** — every new feature or bug fix should include a test.

## Commit style

Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, etc. Keep the subject line under 72 characters.

## Questions?

Open a [Discussion](https://github.com/rehanpunjwani/TokenGuard/discussions) or ping in the issue tracker.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
