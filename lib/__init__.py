"""
Python replacement for the @chainlink/functions-toolkit pieces that don't
require running JavaScript: DON-hosted secrets, request CBOR encoding,
operational helpers (cost estimation, timeouts, response listening).

Layout
------
- gateway.py          low-level JSON-RPC over the Functions gateways
- uploader.py         secrets_set: encrypt+payload+signing+upload
- secrets_list.py     secrets_list: enumerate slots/versions
- encrypt.py          ECIES + TDH2 hybrid encryption (extras)
- request_builder.py  CBOR request, DON-secrets reference, response decode
- billing.py          estimate cost, timeout expired requests (extras)
- listener.py         fetch commitment, listen for responses (extras)
"""

from __future__ import annotations

__all__ = [
    # Phase 1
    "DEFAULT_GATEWAY_URLS",
    "upload_encrypted_secrets_to_don",
    "list_don_hosted_secrets",
    "overwrite_don_hosted_secret",
    "build_secrets_payload",
    "build_gateway_request_json",
    "format_curl_command",
    "format_curl_command_powershell",
    "encrypt_secrets",
    "SecretsManager",
    "verify_offchain_secrets",
    # Phase 3
    "Location",
    "CodeLanguage",
    "ReturnType",
    "FunctionsRequestParams",
    "build_request_cbor",
    "buildRequestCBOR",
    "build_don_hosted_secrets_reference",
    "buildDONHostedEncryptedSecretsReference",
    "decode_response",
    "decodeResult",
    # Phase 2
    "RequestCommitment",
    "FulfillmentCode",
    "SubscriptionInfo",
    "SubscriptionManager",
    "ResponseListener",
    "estimate_request_cost",
    "timeout_requests",
    "fetch_request_commitment",
    "fetchRequestCommitment",
    "listen_for_response",
    "listen_for_response_from_tx",
    "listen_for_responses",
    # Offchain storage / simulation
    "create_gist",
    "delete_gist",
    "createGist",
    "deleteGist",
    "simulate_script",
    "simulateScript",
    "start_local_functions_testnet",
    "startLocalFunctionsTestnet",
    # CRE
    "CRECLI",
    "CRECommandResult",
    "CREProject",
    "CRESecrets",
    "CREWorkflow",
    "CREWorkflowClient",
    "scaffold_from_functions_request",
]

from .gateway import (  # noqa: F401
    DEFAULT_GATEWAY_URLS,
    build_gateway_request_json,
    format_curl_command,
    format_curl_command_powershell,
)
from .uploader import (  # noqa: F401
    build_secrets_payload,
    upload_encrypted_secrets_to_don,
)
from .secrets_list import (  # noqa: F401
    list_don_hosted_secrets,
    overwrite_don_hosted_secret,
)
from .request_builder import (  # noqa: F401
    CodeLanguage,
    FunctionsRequestParams,
    Location,
    ReturnType,
    buildRequestCBOR,
    buildDONHostedEncryptedSecretsReference,
    build_don_hosted_secrets_reference,
    build_request_cbor,
    decodeResult,
    decode_response,
)
from .secrets_manager import SecretsManager, verify_offchain_secrets  # noqa: F401
from .subscription_manager import SubscriptionInfo, SubscriptionManager  # noqa: F401
from .response_listener import ResponseListener  # noqa: F401
from .offchain_storage import createGist, create_gist, deleteGist, delete_gist  # noqa: F401
from .simulate import simulateScript, simulate_script  # noqa: F401
from .local_functions_testnet import (  # noqa: F401
    startLocalFunctionsTestnet,
    start_local_functions_testnet,
)
from .cre import (  # noqa: F401
    CRECLI,
    CRECommandResult,
    CREProject,
    CRESecrets,
    CREWorkflow,
    CREWorkflowClient,
    scaffold_from_functions_request,
)


def encrypt_secrets(*args, **kwargs):
    """
    Lazy import of the encrypt pipeline so the upload + list features
    can be used without the heavier crypto/web3 dependencies.

    Install extras with: `pip install -r requirements-encrypt.txt`.
    """
    try:
        from .encrypt import encrypt_secrets as _encrypt
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "encrypt_secrets() requires extra dependencies. "
            "Install with: pip install -r requirements-encrypt.txt"
        ) from exc
    return _encrypt(*args, **kwargs)


# Phase 2 helpers depend on web3; expose them through lazy proxies so users
# without web3 installed can still use Phase 1 / Phase 3.

def estimate_request_cost(*args, **kwargs):
    from .billing import estimate_request_cost as _fn

    return _fn(*args, **kwargs)


def timeout_requests(*args, **kwargs):
    from .billing import timeout_requests as _fn

    return _fn(*args, **kwargs)


def fetch_request_commitment(*args, **kwargs):
    from .listener import fetch_request_commitment as _fn

    return _fn(*args, **kwargs)


fetchRequestCommitment = fetch_request_commitment


def listen_for_response(*args, **kwargs):
    from .listener import listen_for_response as _fn

    return _fn(*args, **kwargs)


def listen_for_response_from_tx(*args, **kwargs):
    from .listener import listen_for_response_from_tx as _fn

    return _fn(*args, **kwargs)


def listen_for_responses(*args, **kwargs):
    from .listener import listen_for_responses as _fn

    return _fn(*args, **kwargs)


# Lightweight enum / dataclass re-exports (no web3 import needed).
from .listener import FulfillmentCode  # noqa: E402,F401
from .billing import RequestCommitment  # noqa: E402,F401
