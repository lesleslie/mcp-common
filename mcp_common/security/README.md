# Security Layer

## Responsibilities

Centralizes API key hygiene and payload sanitization so downstream servers avoid duplicating defensive code.

## Modules

- `api_keys.py` — Validation routines that enforce key length, format, and presence. Downstream settings classes defer to these checks through helpers like `validate_api_key_startup`.
- `sanitization.py` — Normalizes potentially unsafe strings, applying character whitelists and masking patterns before logging or returning responses.

Consume these helpers from settings or adapters to fail fast when configuration is invalid, and keep sensitive output scrubbed before it reaches logs or clients.
