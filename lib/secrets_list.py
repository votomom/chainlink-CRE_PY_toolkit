from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .gateway import send_to_gateways
from .responses import (
    SecretsEntry,
    SecretsListGatewayResponse,
    merge_listed_secrets,
    normalize_secrets_list_gateway_response,
)


def list_don_hosted_secrets(
    *,
    private_key_hex: str,
    don_id: str,
    gateway_urls: Sequence[str] | str,
    message_id: Optional[str] = None,
    timeout_s: int = 30,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Calls the gateway `secrets_list` method (no payload) and returns:
      {
        "gatewayUrl": str,
        "success": bool,                  # gateway-level success
        "nodeResponses": [{success, error_message, rows}],
        "rows": [{slot_id, version, expiration}],   # merged, deduped
      }
    """
    gateway_url, result_json = send_to_gateways(
        private_key_hex=private_key_hex,
        don_id=don_id,
        method="secrets_list",
        payload=None,
        gateway_urls=gateway_urls,
        message_id=message_id,
        timeout_s=timeout_s,
        debug=debug,
    )
    response = normalize_secrets_list_gateway_response(
        gateway_url=gateway_url, gateway_json=result_json
    )
    return {
        "gatewayUrl": response.gateway_url,
        "success": response.success,
        "nodeResponses": [
            {
                "success": nr.success,
                "error_message": nr.error_message,
                "rows": [
                    {"slot_id": r.slot_id, "version": r.version, "expiration": r.expiration}
                    for r in nr.rows
                ],
            }
            for nr in response.node_responses
        ],
        "rows": [
            {"slot_id": r.slot_id, "version": r.version, "expiration": r.expiration}
            for r in merge_listed_secrets(response)
        ],
    }


def overwrite_don_hosted_secret(
    *,
    private_key_hex: str,
    don_id: str,
    gateway_urls: Sequence[str] | str,
    slot_id: int,
    encrypted_secrets_hex_or_path: str,
    minutes_until_expiration: int = 60,
    message_id: Optional[str] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Convenience wrapper: re-uploads encrypted secrets to an existing slot.
    The DON gateway has no native delete; bumping the version overwrites.
    """
    from .uploader import upload_encrypted_secrets_to_don

    return upload_encrypted_secrets_to_don(
        private_key_hex=private_key_hex,
        don_id=don_id,
        gateway_urls=gateway_urls,
        slot_id=slot_id,
        encrypted_secrets_hex_or_path=encrypted_secrets_hex_or_path,
        minutes_until_expiration=minutes_until_expiration,
        message_id=message_id,
        debug=debug,
    )
