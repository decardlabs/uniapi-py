# Full Codebase Fix — Progress

Plan: docs/superpowers/plans/2026-06-30-full-codebase-fix-plan.md
Branch: main
Started: 2026-06-30

## Round 1 (Security) — Complete
- [x] R1-1: Fix hardcoded root credentials
- [x] R1-2: Fix token expiry unit mismatch
- [x] R1-3: Fix sort parameter injection
- [x] R1-4: Add Pydantic schema validation to MCP endpoints
- [x] R1-5: Add session rotation on password change
- [x] R1-6: Move reset token from URL to body

## Round 2 (Billing/Budget) — In Progress
- [ ] R2-1: Add FOR UPDATE locking on balance operations
- [ ] R2-2: Pass channel_model_configs to non-stream billing
- [ ] R2-3: Add budget arbiter pre-check to fusion path
- [ ] R2-4: Fix GLM fusion adapter auth
- [ ] R2-5: Fix budget arbiter DB fallback race
- [ ] R2-6: Fix cache analytics fallback pricing

## Minor Findings
