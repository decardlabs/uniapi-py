# Changelog

All notable changes to UniAPI are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-30

### Security
- Replaced hardcoded root credentials with UNIAPI_ROOT_PASSWORD env var
- Fixed token expiry unit mismatch (ms vs s) — tokens now expire correctly
- Added sort parameter allowlist to prevent attribute enumeration
- Added Pydantic validation to MCP server endpoints
- Added session rotation on password change (session_version field)
- Removed email from reset-password URL to prevent log exposure
- Added FOR UPDATE locking to all balance operations

### Billing
- Added channel-level pricing overrides to non-stream billing path
- Integrated budget arbiter (pre_check/post_settle) with fusion engine
- Fixed GLM fusion adapter auth (Bearer to JWT)
- Fixed budget arbiter DB fallback race condition
- Fixed cache analytics fallback pricing (1:1 to average model prices)

### Stability
- Added asyncio.Lock to channel failure/429 tracking dicts
- Fixed fallback not resetting original channel failure count
- Fixed TOCTOU race in _is_channel_in_cooldown
- Added safe model lookup (supported.get vs dict access)
- Migrated SSE stream usage callback to queue-based architecture
- Added GeneratorExit handling to SSE streaming

### Quality
- Fixed CORS config (wildcard + credentials)
- Added session_secret warning when not configured
- Made rate limiter proxy-aware (X-Forwarded-For)
- Fixed channel bulk-delete (by name to by ID)
- Added password reset rate limiting
- Fixed _get_path_for_mode returning absolute URLs
- Fixed downgrade_response_format reading wrong field
- Added try/except to _seed_defaults and adaptor registry imports
- Added RelayMode.UNKNOWN for unknown request paths

## [1.0.4] — 2026-06-30

### Fixed
- EditUserPage layout: Group now standalone full-width row; Balance, Register Time,
  Last Modified each as separate full-width rows with Input disabled.
- All fields now use consistent Input component sizing (h-9, px-3 py-2).

### Removed
- Dead import `TimestampDisplay` from EditUserPage.
- Dead code: `make_chat_completion_response()`, `BaseAdaptor.convert_image_request()`,
  `b64url()` in glm/auth.py.

### Changed
- `__import__("time")` replaced with proper `import time` in dependencies.py and sse_converter.py.
- `_replace_channel_with_keys` now correctly reads `groups` field from request body.
- Cross-type channel name collision in models_display appends provider name instead of silent overwrite.

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
