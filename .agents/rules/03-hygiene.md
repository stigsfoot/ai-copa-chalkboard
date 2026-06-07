# Developer Hygiene Guidelines

You must follow these rules during development:

1.  **Secrets Management**: Never commit credentials, passwords, or API keys. Always read `GEMINI_API_KEY` and other sensitive parameters from environment variables or a local `.env` (which must be ignored in `.gitignore`).
2.  **Linting & Formatting**: Follow code style guidelines. Run `ruff check` and `ruff format` to keep python imports and layouts clean.
3.  **TDD Workflow**: When adding new functionality, write a failing test in the `tests/` directory first, and then implement code to make it green.
4.  **Verification**: Always run `python -m pytest` after making changes to ensure you didn't break existing functionality.
