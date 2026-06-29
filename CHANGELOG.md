# Changelog

All notable changes to UniAPI are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.3] — 2026-06-29

### Added
- Multi-key expansion on channel edit: editing a channel's API key from single to
  multiple keys (newline-separated) now deletes all siblings and recreates one
  channel per key, matching create behavior for load balancing.
- Client-side password strength validation (uppercase, digit) on registration form.
- i18n keys `password_uppercase` and `password_digit` for all 5 supported locales.

### Fixed
- Registration error messages now show specific reasons (e.g. "Password must contain
  at least one uppercase letter") pinned to the correct form field, instead of a
  generic "Registration failed" message.
- Backend `register` endpoint now catches `HTTPException` and returns unified
  `GenericApiResponse` format (matching `login` endpoint behavior).
- `_replace_channel_with_keys` now correctly reads the `groups` field from request body.
- Cross-type channel name collision in `models_display` now appends provider name
  instead of silently overwriting.
- Unused imports `sqlalchemy.select` in test, `time`/`uuid` in openai_compatible.py removed.
- `__import__("time")` replaced with proper `import time` in dependencies.py and sse_converter.py.

### Removed
- Dead code: `make_chat_completion_response()` (openai_compatible.py),
  `BaseAdaptor.convert_image_request()` (adaptor.py),
  `b64url()` (glm/auth.py).

## [1.0.2] — 2026-06-29

### Added
- Model display grouped by channel type (dedup by `ch.type`), merging duplicate
  channel names into a single entry per provider.

### Changed
- Settings page consolidated from 4 tabs to 2 tabs.
- Cleaned up unused DB columns, removed Lark OAuth, purged dead i18n keys.

### Fixed
- Restored `db.flush` in login timing guard.
- Fixed Vite build chunk config for Radix UI / qrcode.
- CI: added seed_e2e.py for test channels; E2E test data preparation.

## [1.0.1] — 2026-06-29

### Removed
- Passkey / WebAuthn
- TOTP (two-factor authentication)
- Affiliate system
- Account security settings page
- OAuth/SSO (including Lark OAuth)
- Turnstile config page
- Quota config page

## [1.0.0] — 2026-06-29

### Added
- Initial public release.

### Changed
- Codebase audit and consistency fixes.
- CI pipeline hardened with version validation from git tags.
