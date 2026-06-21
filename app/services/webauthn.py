"""WebAuthn (Passkey) service for passwordless authentication."""

from __future__ import annotations

import json
import secrets
import time
from typing import Optional

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

# In-memory challenge store
# register: {challenge_b64: {user_id, type, expires}}
# login: {challenge_b64: {type, expires}}
_in_progress_challenges: dict[str, dict] = {}

CHALLENGE_TIMEOUT = 300  # 5 minutes

# Default RP configuration
RP_NAME = "UniAPI"


def _store_challenge(challenge_b64: str, data: dict) -> None:
    """Store a challenge with expiry."""
    data["expires"] = int(time.time()) + CHALLENGE_TIMEOUT
    _in_progress_challenges[challenge_b64] = data


def _consume_challenge(challenge_b64: str) -> Optional[dict]:
    """Retrieve and remove a challenge. Returns None if expired."""
    data = _in_progress_challenges.pop(challenge_b64, None)
    if data is None:
        return None
    if int(time.time()) > data.get("expires", 0):
        return None
    return data


def generate_registration_opts(
    rp_id: str,
    rp_name: str,
    user_name: str,
    user_id_str: str,
    user_display_name: str,
    existing_credential_ids: list[str],
) -> dict:
    """Generate WebAuthn registration options and store challenge.

    Returns a dict suitable for returning as `publicKey` in the API response.
    """
    exclude_credentials = []
    for cid in existing_credential_ids:
        try:
            from webauthn import base64url_to_bytes
            exclude_credentials.append(
                PublicKeyCredentialDescriptor(id=base64url_to_bytes(cid))
            )
        except Exception:
            pass

    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_name=user_name,
        user_id=user_id_str.encode("utf-8"),
        user_display_name=user_display_name,
        timeout=60000,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude_credentials or None,
    )

    # Store challenge for later verification
    from webauthn.helpers import bytes_to_base64url
    challenge_b64 = bytes_to_base64url(options.challenge)
    _store_challenge(challenge_b64, {
        "type": "registration",
        "user_id_str": user_id_str,
    })

    # Convert to JSON-serializable dict
    public_key = json.loads(options_to_json(options))
    return public_key


def verify_registration(
    credential: dict,
    expected_rp_id: str,
    expected_origin: str,
) -> Optional[dict]:
    """Verify a registration response.

    Returns the verified credential data dict on success, or None on failure.
    """
    from webauthn.helpers import bytes_to_base64url

    challenge_b64 = None
    try:
        # Extract challenge from the credential response
        client_data = credential.get("response", {}).get("clientDataJSON", "")
        if client_data:
            import base64
            import json as _json
            padded = client_data + "=" * (4 - len(client_data) % 4)
            decoded = base64.urlsafe_b64decode(padded)
            client_data_json = _json.loads(decoded)
            challenge_b64 = client_data_json.get("challenge", "")
    except Exception:
        return None

    if not challenge_b64:
        return None

    stored = _consume_challenge(challenge_b64)
    if stored is None:
        return None

    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge_b64.encode("utf-8") if isinstance(challenge_b64, str) else challenge_b64,
            expected_rp_id=expected_rp_id,
            expected_origin=expected_origin,
            require_user_verification=False,
        )

        return {
            "credential_id": bytes_to_base64url(verification.credential_id),
            "public_key": verification.credential_public_key,  # already bytes
            "sign_count": verification.sign_count,
        }
    except Exception:
        return None


def generate_authentication_opts(
    rp_id: str,
    credential_descriptors: list[dict],
) -> dict:
    """Generate WebAuthn authentication (login) options.

    Args:
        credential_descriptors: list of {"id": "<credential_id_b64>"} for
            the user's registered credentials.
    """
    allow_credentials = []
    for cd in credential_descriptors:
        try:
            from webauthn import base64url_to_bytes
            allow_credentials.append(
                PublicKeyCredentialDescriptor(id=base64url_to_bytes(cd["id"]))
            )
        except Exception:
            pass

    options = generate_authentication_options(
        rp_id=rp_id,
        timeout=60000,
        allow_credentials=allow_credentials or None,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    # Store challenge for later verification
    from webauthn.helpers import bytes_to_base64url
    challenge_b64 = bytes_to_base64url(options.challenge)
    _store_challenge(challenge_b64, {"type": "authentication"})

    public_key = json.loads(options_to_json(options))
    return public_key


def verify_authentication(
    credential: dict,
    expected_rp_id: str,
    expected_origin: str,
    credential_public_key: bytes,
    credential_current_sign_count: int,
) -> Optional[dict]:
    """Verify an authentication (login) response.

    Returns updated credential data dict on success, or None on failure.
    """
    from webauthn.helpers import bytes_to_base64url

    challenge_b64 = None
    try:
        client_data = credential.get("response", {}).get("clientDataJSON", "")
        if client_data:
            import base64
            import json as _json
            padded = client_data + "=" * (4 - len(client_data) % 4)
            decoded = base64.urlsafe_b64decode(padded)
            client_data_json = _json.loads(decoded)
            challenge_b64 = client_data_json.get("challenge", "")
    except Exception:
        return None

    if not challenge_b64:
        return None

    stored = _consume_challenge(challenge_b64)
    if stored is None:
        return None

    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge_b64.encode("utf-8") if isinstance(challenge_b64, str) else challenge_b64,
            expected_rp_id=expected_rp_id,
            expected_origin=expected_origin,
            credential_public_key=credential_public_key,
            credential_current_sign_count=credential_current_sign_count,
            require_user_verification=False,
        )

        return {
            "credential_id": bytes_to_base64url(verification.credential_id),
            "sign_count": verification.new_sign_count,
        }
    except Exception:
        return None
