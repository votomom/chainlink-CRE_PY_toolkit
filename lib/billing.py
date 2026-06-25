from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Optional

from .abi import COORDINATOR_ABI, ROUTER_ABI, format_bytes32_string


@dataclass(frozen=True)
class RequestCommitment:
    requestId: bytes  # 32 bytes
    coordinator: str
    estimatedTotalCostJuels: int
    client: str
    subscriptionId: int
    callbackGasLimit: int
    adminFee: int
    donFee: int
    gasOverheadBeforeCallback: int
    gasOverheadAfterCallback: int
    timeoutTimestamp: int

    def as_tuple(self) -> tuple:
        return (
            self.requestId,
            self.coordinator,
            self.estimatedTotalCostJuels,
            self.client,
            self.subscriptionId,
            self.callbackGasLimit,
            self.adminFee,
            self.donFee,
            self.gasOverheadBeforeCallback,
            self.gasOverheadAfterCallback,
            self.timeoutTimestamp,
        )


def _require_web3():
    try:
        from web3 import Web3  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("This helper requires `web3` (pip install -r requirements-encrypt.txt)") from exc
    return Web3


def _coordinator_for_don(w3, functions_router_address: str, don_id: str):
    Web3 = _require_web3()
    router = w3.eth.contract(
        address=Web3.to_checksum_address(functions_router_address),
        abi=ROUTER_ABI,
    )
    coord_addr = router.functions.getContractById(format_bytes32_string(don_id)).call()
    return w3.eth.contract(address=Web3.to_checksum_address(coord_addr), abi=COORDINATOR_ABI)


def estimate_request_cost(
    *,
    w3,
    functions_router_address: str,
    don_id: str,
    subscription_id: int,
    callback_gas_limit: int,
    gas_price_wei: int,
    request_data: Optional[bytes] = None,
) -> int:
    """
    Returns the estimated maximum cost in juels (1e18 juels = 1 LINK).

    Mirrors `SubscriptionManager.estimateFunctionsRequestCost` in the JS
    toolkit. `request_data` defaults to empty bytes (toolkit behavior).
    """
    if callback_gas_limit <= 0:
        raise ValueError("callback_gas_limit must be > 0")
    if gas_price_wei <= 0:
        raise ValueError("gas_price_wei must be > 0")

    Web3 = _require_web3()
    router = w3.eth.contract(
        address=Web3.to_checksum_address(functions_router_address),
        abi=ROUTER_ABI,
    )
    # Will revert if the limit exceeds the subscription tier's maximum.
    router.functions.isValidCallbackGasLimit(int(subscription_id), int(callback_gas_limit)).call()

    coord = _coordinator_for_don(w3, functions_router_address, don_id)
    return int(
        coord.functions.estimateCost(
            int(subscription_id),
            request_data or b"",
            int(callback_gas_limit),
            int(gas_price_wei),
        ).call()
    )


def timeout_requests(
    *,
    w3,
    functions_router_address: str,
    private_key_hex: str,
    commitments: Iterable[RequestCommitment | Dict[str, Any]],
    gas_price_wei: Optional[int] = None,
    gas_limit: Optional[int] = None,
    confirmations: int = 1,
) -> Dict[str, Any]:
    """
    Submits `FunctionsRouter.timeoutRequests` to refund expired requests.

    Per toolkit, `adminFee` is forced to 0 (the router compares against the
    stored commitment hash where adminFee was 0 at request time).
    """
    Web3 = _require_web3()
    from eth_account import Account

    acct = Account.from_key(private_key_hex)
    router = w3.eth.contract(
        address=Web3.to_checksum_address(functions_router_address),
        abi=ROUTER_ABI,
    )

    cleaned: list = []
    for c in commitments:
        if isinstance(c, RequestCommitment):
            data = asdict(c)
        elif isinstance(c, dict):
            data = dict(c)
        else:
            raise TypeError("commitments must be RequestCommitment or dict")
        data["adminFee"] = 0
        cleaned.append(RequestCommitment(**data).as_tuple())

    if not cleaned:
        raise ValueError("commitments must be non-empty")

    fn = router.functions.timeoutRequests(cleaned)
    tx_args: Dict[str, Any] = {
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gasPrice": int(gas_price_wei) if gas_price_wei is not None else int(w3.eth.gas_price),
    }
    tx_args["gas"] = int(gas_limit) if gas_limit is not None else fn.estimate_gas({"from": acct.address})
    tx = fn.build_transaction(tx_args)

    signed = acct.sign_transaction(tx)
    raw = getattr(signed, "rawTransaction", None) or getattr(signed, "raw_transaction")
    tx_hash = w3.eth.send_raw_transaction(raw)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    return {
        "tx_hash": tx_hash.hex(),
        "status": int(receipt.status),
        "block_number": int(receipt.blockNumber),
        "gas_used": int(receipt.gasUsed),
    }
