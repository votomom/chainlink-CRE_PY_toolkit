from __future__ import annotations

from typing import Any, Dict, Optional


def require_web3():
    try:
        from web3 import Web3  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("This helper requires `web3` (pip install -r requirements-encrypt.txt)") from exc
    return Web3


def make_w3(rpc_url: str):
    Web3 = require_web3()
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ValueError("web3 connection failed")
    return w3


def receipt_summary(receipt: Any) -> Dict[str, Any]:
    return {
        "transactionHash": receipt.transactionHash.hex(),
        "status": int(receipt.status),
        "blockNumber": int(receipt.blockNumber),
        "gasUsed": int(receipt.gasUsed),
    }


def sign_send_wait(
    *,
    w3,
    private_key_hex: str,
    contract_function,
    tx_options: Optional[Dict[str, Any]] = None,
    confirmations: int = 1,
    timeout_s: int = 180,
) -> Dict[str, Any]:
    from eth_account import Account

    acct = Account.from_key(private_key_hex)
    opts = dict(tx_options or {})
    tx_args: Dict[str, Any] = {
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
    }

    if "gasPrice" in opts:
        tx_args["gasPrice"] = int(opts.pop("gasPrice"))
    elif "maxFeePerGas" in opts or "maxPriorityFeePerGas" in opts:
        if "maxFeePerGas" in opts:
            tx_args["maxFeePerGas"] = int(opts.pop("maxFeePerGas"))
        if "maxPriorityFeePerGas" in opts:
            tx_args["maxPriorityFeePerGas"] = int(opts.pop("maxPriorityFeePerGas"))
    else:
        tx_args["gasPrice"] = int(w3.eth.gas_price)

    if "value" in opts:
        tx_args["value"] = int(opts.pop("value"))

    tx_args.update(opts)
    if "gas" not in tx_args:
        tx_args["gas"] = contract_function.estimate_gas({"from": acct.address})

    tx = contract_function.build_transaction(tx_args)
    signed = acct.sign_transaction(tx)
    raw = getattr(signed, "rawTransaction", None) or getattr(signed, "raw_transaction")
    tx_hash = w3.eth.send_raw_transaction(raw)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout_s)

    if confirmations > 1:
        import time

        target = receipt.blockNumber + confirmations - 1
        while w3.eth.block_number < target:
            time.sleep(2)

    return receipt_summary(receipt)


def to_checksum(w3, address: str) -> str:
    Web3 = require_web3()
    return Web3.to_checksum_address(address)
