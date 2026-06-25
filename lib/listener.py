from __future__ import annotations

import time
from enum import IntEnum
from typing import Any, Callable, Dict, Optional, Union

from .abi import COORDINATOR_ABI, ROUTER_ABI, format_bytes32_string
from .billing import RequestCommitment


class FulfillmentCode(IntEnum):
    FULFILLED = 0
    USER_CALLBACK_ERROR = 1
    INVALID_REQUEST_ID = 2
    COST_EXCEEDS_COMMITMENT = 3
    INSUFFICIENT_GAS_PROVIDED = 4
    SUBSCRIPTION_BALANCE_INVARIANT_VIOLATION = 5
    INVALID_COMMITMENT = 6


def _require_web3():
    try:
        from web3 import Web3  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("This helper requires `web3` (pip install -r requirements-encrypt.txt)") from exc
    return Web3


def _to_bytes32(request_id: Union[str, bytes]) -> bytes:
    if isinstance(request_id, bytes):
        if len(request_id) != 32:
            raise ValueError("request_id bytes must be length 32")
        return request_id
    raw = request_id.removeprefix("0x")
    out = bytes.fromhex(raw)
    if len(out) != 32:
        raise ValueError("request_id hex must decode to 32 bytes")
    return out


def _coordinator_address(w3, functions_router_address: str, don_id: str) -> str:
    Web3 = _require_web3()
    router = w3.eth.contract(
        address=Web3.to_checksum_address(functions_router_address),
        abi=ROUTER_ABI,
    )
    return router.functions.getContractById(format_bytes32_string(don_id)).call()


def fetch_request_commitment(
    *,
    w3,
    functions_router_address: str,
    don_id: str,
    request_id: Union[str, bytes],
    to_block: Union[int, str] = "latest",
    past_blocks_to_search: int = 1000,
) -> RequestCommitment:
    """
    Reads the on-chain commitment by scanning `OracleRequest` events on the
    DON's coordinator (mirrors `fetchRequestCommitment` in the JS toolkit).
    """
    Web3 = _require_web3()

    coord_addr = _coordinator_address(w3, functions_router_address, don_id)
    coord = w3.eth.contract(address=Web3.to_checksum_address(coord_addr), abi=COORDINATOR_ABI)

    latest = w3.eth.block_number
    if to_block == "latest":
        end_block = latest
    else:
        end_block = min(int(to_block), latest)
    from_block = max(0, end_block - past_blocks_to_search)

    rid = _to_bytes32(request_id)
    event_filter = coord.events.OracleRequest.create_filter(
        from_block=from_block,
        to_block=end_block,
        argument_filters={"requestId": rid},
    )
    logs = event_filter.get_all_entries()
    if not logs:
        raise LookupError(
            f"no OracleRequest event for requestId 0x{rid.hex()} between blocks {from_block}-{end_block}"
        )

    c = logs[0]["args"]["commitment"]
    return RequestCommitment(
        requestId=bytes(c["requestId"]),
        coordinator=str(c["coordinator"]),
        estimatedTotalCostJuels=int(c["estimatedTotalCostJuels"]),
        client=str(c["client"]),
        subscriptionId=int(c["subscriptionId"]),
        callbackGasLimit=int(c["callbackGasLimit"]),
        adminFee=int(c["adminFee"]),
        donFee=int(c["donFee"]),
        gasOverheadBeforeCallback=int(c["gasOverheadBeforeCallback"]),
        gasOverheadAfterCallback=int(c["gasOverheadAfterCallback"]),
        timeoutTimestamp=int(c["timeoutTimestamp"]),
    )


def _format_response(args: Dict[str, Any]) -> Dict[str, Any]:
    err_bytes = bytes(args["err"]) if args.get("err") else b""
    response_bytes = bytes(args["response"]) if args.get("response") else b""
    return_data = bytes(args["callbackReturnData"]) if args.get("callbackReturnData") else b""
    return {
        "requestId": "0x" + bytes(args["requestId"]).hex(),
        "subscriptionId": int(args["subscriptionId"]),
        "totalCostInJuels": int(args["totalCostJuels"]),
        "transmitter": str(args["transmitter"]),
        "fulfillmentCode": int(args["resultCode"]),
        "responseBytesHexstring": "0x" + response_bytes.hex(),
        "errorString": err_bytes.decode("utf-8", errors="replace"),
        "returnDataBytesHexstring": "0x" + return_data.hex(),
    }


def listen_for_response(
    *,
    w3,
    functions_router_address: str,
    request_id: Union[str, bytes],
    timeout_s: float = 300.0,
    poll_interval_s: float = 2.0,
    from_block: Optional[Union[int, str]] = None,
) -> Dict[str, Any]:
    """
    Polls `RequestProcessed` on the FunctionsRouter for a given `request_id`.
    Returns the decoded response dict; raises `TimeoutError` if not seen.
    """
    Web3 = _require_web3()
    router = w3.eth.contract(
        address=Web3.to_checksum_address(functions_router_address),
        abi=ROUTER_ABI,
    )

    rid = _to_bytes32(request_id)
    start_block = w3.eth.block_number if from_block is None else from_block
    event_filter = router.events.RequestProcessed.create_filter(
        from_block=start_block,
        argument_filters={"requestId": rid},
    )

    deadline = time.monotonic() + float(timeout_s)
    while time.monotonic() < deadline:
        for ev in event_filter.get_new_entries():
            args = ev["args"]
            if args["resultCode"] == FulfillmentCode.INVALID_REQUEST_ID:
                continue
            return _format_response(args)
        time.sleep(poll_interval_s)
    raise TimeoutError(f"response for {('0x' + rid.hex())} not received within {timeout_s}s")


def listen_for_response_from_tx(
    *,
    w3,
    functions_router_address: str,
    tx_hash: str,
    timeout_s: float = 300.0,
    confirmations: int = 1,
    poll_interval_s: float = 2.0,
) -> Dict[str, Any]:
    """
    Waits for the request transaction, extracts the requestId from logs,
    then waits for the matching `RequestProcessed`.
    """
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout_s)
    if confirmations > 1:
        target_block = receipt.blockNumber + confirmations - 1
        while w3.eth.block_number < target_block:
            time.sleep(poll_interval_s)

    if not receipt.logs:
        raise ValueError("tx receipt has no logs - request likely reverted")

    # FunctionsClient emits `RequestSent(bytes32 indexed id)` and the router emits
    # `RequestStart(bytes32 indexed requestId, ...)` - the requestId sits in topic[1]
    # of the first matching log.
    request_id = bytes(receipt.logs[0]["topics"][1])
    return listen_for_response(
        w3=w3,
        functions_router_address=functions_router_address,
        request_id=request_id,
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
        from_block=receipt.blockNumber,
    )


def listen_for_responses(
    *,
    w3,
    functions_router_address: str,
    subscription_id: int,
    callback: Callable[[Dict[str, Any]], None],
    poll_interval_s: float = 2.0,
    from_block: Optional[Union[int, str]] = None,
    stop_after: Optional[int] = None,
) -> int:
    """
    Streams `RequestProcessed` events for a subscription. Calls `callback`
    once per response. Blocks until `stop_after` events are received (when
    set) or `KeyboardInterrupt`. Returns the count of dispatched events.
    """
    Web3 = _require_web3()
    router = w3.eth.contract(
        address=Web3.to_checksum_address(functions_router_address),
        abi=ROUTER_ABI,
    )

    start_block = w3.eth.block_number if from_block is None else from_block
    event_filter = router.events.RequestProcessed.create_filter(
        from_block=start_block,
        argument_filters={"subscriptionId": int(subscription_id)},
    )

    delivered = 0
    try:
        while stop_after is None or delivered < stop_after:
            for ev in event_filter.get_new_entries():
                args = ev["args"]
                if args["resultCode"] == FulfillmentCode.INVALID_REQUEST_ID:
                    continue
                callback(_format_response(args))
                delivered += 1
                if stop_after is not None and delivered >= stop_after:
                    break
            time.sleep(poll_interval_s)
    except KeyboardInterrupt:
        pass
    return delivered


fetchRequestCommitment = fetch_request_commitment
