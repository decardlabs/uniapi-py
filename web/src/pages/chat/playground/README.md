# Playground Architecture

This directory hosts the modularized implementation for the modern chat playground. The previous inline documentation from `PlaygroundPage.tsx` now lives here so the page component can stay concise.

## Local Storage Layout

All conversation and preference data stays in the browser. Nothing is persisted on the server.

- **Conversation (`STORAGE_KEYS.CONVERSATION`)**

  ```json
  {
    "id": "uuid",
    "timestamp": 1700000000000,
    "createdBy": "alice",
    "messages": [ ... ]
  }
  ```

- **Model (`STORAGE_KEYS.MODEL`)** – last selected model id.
- **Token (`STORAGE_KEYS.TOKEN`)** – last selected token key.
- **Parameters (`STORAGE_KEYS.PARAMETERS`)** – serialized sliders, toggles, and system prompt text.

## State Lifecycle

1. `useConversationPersistence` restores the last conversation, generates a new UUID for clears, and keeps storage synced.
2. `useModelAndTokenBrowser` fetches tokens, channel metadata, and user models, then normalizes the suggestion lists.
3. `usePlaygroundParameters` loads parameter defaults, validates them against model capabilities, and writes back to storage when sliders change.
4. `usePlaygroundViewModel` composes everything and feeds `usePlaygroundChat` plus the UI components.

## Capability Validation

When the selected model changes, unsupported parameters (e.g., `topK`, reasoning effort, thinking budget) revert to safe defaults before being saved. Claude medium-only reasoning rules follow `isOpenAIMediumOnlyReasoningModel`.

## Data Safety

- Data never leaves the browser unless the user explicitly issues API calls.
- Clearing the conversation only removes the transcript; model selection and parameter presets stay to reduce friction.
- Use a trusted browser, keep extensions audited, and wipe localStorage via the Clear button if needed.

See `docs/arch/modern-frontend-structure.md` for the global guidelines covering file-size limits and layering expectations.
