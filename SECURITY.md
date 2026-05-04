# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email the maintainers or use [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
3. Include steps to reproduce and potential impact

We will acknowledge receipt within 48 hours and aim to release a fix promptly.

## Scope

This application processes PDF files locally. Security considerations include:
- PDF parsing (PyMuPDF) — malformed PDFs could trigger vulnerabilities
- OCR processing (Tesseract) — image-based attacks
- File system access — input/output paths are user-controlled

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |
