# Contributing to Invoice Scrapper

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/<your-username>/invoice_scrapper.git
cd invoice_scrapper

# Install all dependencies (requires uv)
make install-dev

# Verify Tesseract OCR is installed
make check-tesseract

# Run the app
make run
```

## Making Changes

1. Fork the repository and create a feature branch from `main`
2. Make your changes
3. Run linting and tests:
   ```bash
   make lint
   make test
   ```
4. Commit with a descriptive message following [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   feat: add support for new field type
   fix: handle PDFs with empty pages
   ```
5. Push your branch and open a Pull Request

## Code Style

- Follow PEP 8 (enforced by `ruff`)
- Use type hints for function signatures
- Format with `make format` before committing

## Running Tests

```bash
make test              # Run all tests
make test-verbose      # With stdout visible
make test-coverage     # With coverage report
```

All tests must pass before a PR can be merged.

## Reporting Issues

- Use the GitHub issue tracker
- Include steps to reproduce, expected vs actual behavior
- Attach a sample PDF if relevant (redact sensitive data)

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
