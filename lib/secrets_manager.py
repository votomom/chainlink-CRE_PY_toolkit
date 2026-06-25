from __future__ import annotations

import json
from typing import Any, Dict, Optional, Sequence
from urllib.parse import urlparse

import requests

from .abi import COORDINATOR_ABI, ROUTER_ABI, format_bytes32_string
from .gateway import is_hex_string
from .request_builder import build_don_hosted_secrets_reference
from .secrets_list import list_don_hosted_secrets
from .uploader import upload_encrypted_secrets_to_don
from .web3_helpers import make_w3, require_web3


def _validate_urls(urls: Sequence[str]) -> list[str]:
    if not urls:
        raise ValueError("Must provide a non-empty array of secrets URLs")
    out = []
    for url in urls:
        if not isinstance(url, str):
            raise TypeError("All secrets URLs must be strings")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"Invalid secrets URL: {url}")
        out.append(url)
    return out


def verify_offchain_secrets(secrets_urls: Sequence[str], *, timeout_s: int = 30) -> bool:
    last: Optional[str] = None
    for url in _validate_urls(secrets_urls):
        response = requests.get(url, timeout=timeout_s)
        response.raise_for_status()
        data = response.json()
        encrypted = data.get("encryptedSecrets") if isinstance(data, dict) else None
        if not isinstance(encrypted, str) or not is_hex_string(encrypted):
            raise ValueError(f"{url} did not return a valid encryptedSecrets hex string")
        if last is not None and encrypted != last:
            raise ValueError(f"{url} returned a different encryptedSecrets value")
        last = encrypted
    return True


class SecretsManager:
    def __init__(
        self,
        *,
        signer: Optional[Any] = None,
        private_key_hex: Optional[str] = None,
        provider: Optional[Any] = None,
        rpc_url: Optional[str] = None,
        functionsRouterAddress: Optional[str] = None,
        functions_router_address: Optional[str] = None,
        donId: Optional[str] = None,
        don_id: Optional[str] = None,
    ) -> None:
        if signer is not None:
            private_key_hex = getattr(signer, "key", None) or getattr(signer, "private_key", None) or private_key_hex
        if private_key_hex is None:
            raise ValueError("private_key_hex is required")

        self.private_key_hex = str(private_key_hex)
        self.w3 = provider or (make_w3(rpc_url) if rpc_url else None)
        if self.w3 is None:
            raise ValueError("provider or rpc_url is required")
        self.rpc_url = rpc_url
        self.functionsRouterAddress = functionsRouterAddress or functions_router_address
        self.donId = donId or don_id
        if not self.functionsRouterAddress:
            raise ValueError("functionsRouterAddress is required")
        if not self.donId:
            raise ValueError("donId is required")

        self.functionsCoordinatorAddress: Optional[str] = None
        self.initialized = False

    def initialize(self) -> None:
        Web3 = require_web3()
        router = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.functionsRouterAddress),
            abi=ROUTER_ABI,
        )
        self.functionsCoordinatorAddress = router.functions.getContractById(
            format_bytes32_string(self.donId)
        ).call()
        self.initialized = True

    def _ensure_initialized(self) -> None:
        if not self.initialized:
            self.initialize()

    def fetchKeys(self) -> Dict[str, Any]:
        self._ensure_initialized()
        Web3 = require_web3()
        coord = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.functionsCoordinatorAddress),
            abi=COORDINATOR_ABI,
        )
        threshold_bytes = coord.functions.getThresholdPublicKey().call()
        don_public_key = coord.functions.getDONPublicKey().call().hex()
        return {
            "thresholdPublicKey": json.loads(bytes(threshold_bytes).decode("utf-8")),
            "donPublicKey": don_public_key.removeprefix("0x"),
        }

    def encryptSecretsUrls(self, secretsUrls: Sequence[str]) -> str:
        from .encrypt import _ethcrypto_encrypt_with_public_key

        urls = _validate_urls(secretsUrls)
        don_public_key = self.fetchKeys()["donPublicKey"]
        return "0x" + _ethcrypto_encrypt_with_public_key(don_public_key, " ".join(urls).encode("utf-8"))

    def verifyOffchainSecrets(self, secretsUrls: Sequence[str]) -> bool:
        return verify_offchain_secrets(secretsUrls)

    def encryptSecrets(self, secrets: Dict[str, str]) -> Dict[str, str]:
        from .encrypt import encrypt_secrets

        if not self.rpc_url:
            raise ValueError("rpc_url is required for encryptSecrets")
        artifacts = encrypt_secrets(
            secrets_map=secrets,
            private_key_hex=self.private_key_hex,
            rpc_url=self.rpc_url,
            functions_router_address=self.functionsRouterAddress,
            don_id=self.donId,
        )
        return {"encryptedSecrets": artifacts.encrypted_secrets_hex}

    def uploadEncryptedSecretsToDON(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return upload_encrypted_secrets_to_don(
            private_key_hex=self.private_key_hex,
            don_id=self.donId,
            gateway_urls=config["gatewayUrls"],
            slot_id=int(config["slotId"]),
            encrypted_secrets_hex_or_path=config["encryptedSecretsHexstring"],
            minutes_until_expiration=int(config["minutesUntilExpiration"]),
        )

    def listDONHostedEncryptedSecrets(self, gatewayUrls: Sequence[str]) -> Dict[str, Any]:
        result = list_don_hosted_secrets(
            private_key_hex=self.private_key_hex,
            don_id=self.donId,
            gateway_urls=gatewayUrls,
        )
        err = None
        failed = [nr for nr in result.get("nodeResponses", []) if not nr.get("success")]
        if failed:
            err = "One or more nodes failed to respond with success"
        return {"result": result, "error": err} if err else {"result": result}

    def buildDONHostedEncryptedSecretsReference(self, config: Dict[str, int]) -> str:
        return build_don_hosted_secrets_reference(
            slot_id=int(config["slotId"]),
            version=int(config["version"]),
        )


__all__ = ["SecretsManager", "verify_offchain_secrets"]
