from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from eth_account import Account

from .abi import ALLOWLIST_ABI, LINK_TOKEN_ABI, ROUTER_ABI
from .billing import RequestCommitment, estimate_request_cost, timeout_requests
from .web3_helpers import make_w3, require_web3, sign_send_wait, to_checksum


@dataclass(frozen=True)
class SubscriptionInfo:
    balance: int
    owner: str
    blockedBalance: int
    proposedOwner: str
    consumers: list[str]
    flags: str


def _router(w3, functions_router_address: str):
    return w3.eth.contract(address=to_checksum(w3, functions_router_address), abi=ROUTER_ABI)


def _link(w3, link_token_address: str):
    return w3.eth.contract(address=to_checksum(w3, link_token_address), abi=LINK_TOKEN_ABI)


def _require_owner(owner: str, signer: str, subscription_id: int) -> None:
    if owner.lower() != signer.lower():
        raise PermissionError(
            f"The current wallet {signer} is not the owner {owner} of subscription {subscription_id}"
        )


def _normalize_sub(data: Any) -> SubscriptionInfo:
    return SubscriptionInfo(
        balance=int(data["balance"] if isinstance(data, dict) else data[0]),
        owner=str(data["owner"] if isinstance(data, dict) else data[1]),
        blockedBalance=int(data["blockedBalance"] if isinstance(data, dict) else data[2]),
        proposedOwner=str(data["proposedOwner"] if isinstance(data, dict) else data[3]),
        consumers=list(data["consumers"] if isinstance(data, dict) else data[4]),
        flags=(data["flags"].hex() if isinstance(data, dict) and hasattr(data["flags"], "hex") else str(data["flags"] if isinstance(data, dict) else data[5])),
    )


def get_subscription_info(
    *,
    w3,
    functions_router_address: str,
    subscription_id: int,
) -> SubscriptionInfo:
    return _normalize_sub(_router(w3, functions_router_address).functions.getSubscription(int(subscription_id)).call())


def get_allowlist_contract(*, w3, functions_router_address: str):
    router = _router(w3, functions_router_address)
    allowlist_id = router.functions.getAllowListId().call()
    try:
        allowlist_address = router.functions.getContractById(allowlist_id).call()
    except Exception:
        return None
    if int(allowlist_address, 16) == 0:
        return None
    return w3.eth.contract(address=to_checksum(w3, allowlist_address), abi=ALLOWLIST_ABI)


def is_allowlisted(
    *,
    w3,
    functions_router_address: str,
    address: str,
) -> bool:
    allowlist = get_allowlist_contract(w3=w3, functions_router_address=functions_router_address)
    if allowlist is None:
        return True
    return bool(allowlist.functions.hasAccess(to_checksum(w3, address), []).call())


def create_subscription(
    *,
    w3,
    functions_router_address: str,
    private_key_hex: str,
    consumer_address: Optional[str] = None,
    tx_options: Optional[Dict[str, Any]] = None,
    confirmations: int = 1,
) -> Dict[str, Any]:
    acct = Account.from_key(private_key_hex)
    if not is_allowlisted(w3=w3, functions_router_address=functions_router_address, address=acct.address):
        raise PermissionError("This wallet has not been added to the Functions allow list")

    router = _router(w3, functions_router_address)
    fn = (
        router.functions.createSubscriptionWithConsumer(to_checksum(w3, consumer_address))
        if consumer_address
        else router.functions.createSubscription()
    )
    return sign_send_wait(
        w3=w3,
        private_key_hex=private_key_hex,
        contract_function=fn,
        tx_options=tx_options,
        confirmations=confirmations,
    )


def add_consumer(
    *,
    w3,
    functions_router_address: str,
    private_key_hex: str,
    subscription_id: int,
    consumer_address: str,
    tx_options: Optional[Dict[str, Any]] = None,
    confirmations: int = 1,
) -> Dict[str, Any]:
    acct = Account.from_key(private_key_hex)
    sub = get_subscription_info(w3=w3, functions_router_address=functions_router_address, subscription_id=subscription_id)
    _require_owner(sub.owner, acct.address, subscription_id)
    if consumer_address.lower() in [c.lower() for c in sub.consumers]:
        raise ValueError(f"Consumer {consumer_address} is already authorized")

    fn = _router(w3, functions_router_address).functions.addConsumer(
        int(subscription_id), to_checksum(w3, consumer_address)
    )
    return sign_send_wait(
        w3=w3,
        private_key_hex=private_key_hex,
        contract_function=fn,
        tx_options=tx_options,
        confirmations=confirmations,
    )


def remove_consumer(
    *,
    w3,
    functions_router_address: str,
    private_key_hex: str,
    subscription_id: int,
    consumer_address: str,
    tx_options: Optional[Dict[str, Any]] = None,
    confirmations: int = 1,
) -> Dict[str, Any]:
    acct = Account.from_key(private_key_hex)
    sub = get_subscription_info(w3=w3, functions_router_address=functions_router_address, subscription_id=subscription_id)
    _require_owner(sub.owner, acct.address, subscription_id)
    if consumer_address.lower() not in [c.lower() for c in sub.consumers]:
        raise ValueError(f"Consumer {consumer_address} is not authorized")

    fn = _router(w3, functions_router_address).functions.removeConsumer(
        int(subscription_id), to_checksum(w3, consumer_address)
    )
    return sign_send_wait(
        w3=w3,
        private_key_hex=private_key_hex,
        contract_function=fn,
        tx_options=tx_options,
        confirmations=confirmations,
    )


def fund_subscription(
    *,
    w3,
    link_token_address: str,
    functions_router_address: str,
    private_key_hex: str,
    subscription_id: int,
    juels_amount: int | str,
    tx_options: Optional[Dict[str, Any]] = None,
    confirmations: int = 1,
) -> Dict[str, Any]:
    try:
        from eth_abi import encode
    except ModuleNotFoundError as exc:
        raise RuntimeError("fund_subscription requires `eth-abi`") from exc

    acct = Account.from_key(private_key_hex)
    amount = int(juels_amount)
    if amount <= 0:
        raise ValueError("juels_amount must be greater than 0")

    token = _link(w3, link_token_address)
    balance = int(token.functions.balanceOf(acct.address).call())
    if amount > balance:
        raise ValueError(f"Insufficient LINK balance: need {amount}, have {balance}")

    # Same payload as ethers defaultAbiCoder.encode(['uint64'], [subscriptionId]).
    data = encode(["uint64"], [int(subscription_id)])
    fn = token.functions.transferAndCall(to_checksum(w3, functions_router_address), amount, data)
    return sign_send_wait(
        w3=w3,
        private_key_hex=private_key_hex,
        contract_function=fn,
        tx_options=tx_options,
        confirmations=confirmations,
    )


def cancel_subscription(
    *,
    w3,
    functions_router_address: str,
    private_key_hex: str,
    subscription_id: int,
    refund_address: Optional[str] = None,
    tx_options: Optional[Dict[str, Any]] = None,
    confirmations: int = 1,
) -> Dict[str, Any]:
    acct = Account.from_key(private_key_hex)
    sub = get_subscription_info(w3=w3, functions_router_address=functions_router_address, subscription_id=subscription_id)
    _require_owner(sub.owner, acct.address, subscription_id)
    refund = to_checksum(w3, refund_address or acct.address)
    fn = _router(w3, functions_router_address).functions.cancelSubscription(int(subscription_id), refund)
    return sign_send_wait(
        w3=w3,
        private_key_hex=private_key_hex,
        contract_function=fn,
        tx_options=tx_options,
        confirmations=confirmations,
    )


def request_subscription_transfer(
    *,
    w3,
    functions_router_address: str,
    private_key_hex: str,
    subscription_id: int,
    new_owner: str,
    tx_options: Optional[Dict[str, Any]] = None,
    confirmations: int = 1,
) -> Dict[str, Any]:
    acct = Account.from_key(private_key_hex)
    sub = get_subscription_info(w3=w3, functions_router_address=functions_router_address, subscription_id=subscription_id)
    _require_owner(sub.owner, acct.address, subscription_id)
    fn = _router(w3, functions_router_address).functions.proposeSubscriptionOwnerTransfer(
        int(subscription_id), to_checksum(w3, new_owner)
    )
    return sign_send_wait(
        w3=w3,
        private_key_hex=private_key_hex,
        contract_function=fn,
        tx_options=tx_options,
        confirmations=confirmations,
    )


def accept_sub_transfer(
    *,
    w3,
    functions_router_address: str,
    private_key_hex: str,
    subscription_id: int,
    tx_options: Optional[Dict[str, Any]] = None,
    confirmations: int = 1,
) -> Dict[str, Any]:
    fn = _router(w3, functions_router_address).functions.acceptSubscriptionOwnerTransfer(int(subscription_id))
    return sign_send_wait(
        w3=w3,
        private_key_hex=private_key_hex,
        contract_function=fn,
        tx_options=tx_options,
        confirmations=confirmations,
    )


class SubscriptionManager:
    def __init__(
        self,
        *,
        signer: Optional[Any] = None,
        private_key_hex: Optional[str] = None,
        provider: Optional[Any] = None,
        rpc_url: Optional[str] = None,
        linkTokenAddress: Optional[str] = None,
        link_token_address: Optional[str] = None,
        functionsRouterAddress: Optional[str] = None,
        functions_router_address: Optional[str] = None,
    ) -> None:
        if signer is not None:
            private_key_hex = getattr(signer, "key", None) or getattr(signer, "private_key", None) or private_key_hex
        if private_key_hex is None:
            raise ValueError("private_key_hex is required")

        self.private_key_hex = str(private_key_hex)
        self.w3 = provider or (make_w3(rpc_url) if rpc_url else None)
        if self.w3 is None:
            raise ValueError("provider or rpc_url is required")
        self.linkTokenAddress = linkTokenAddress or link_token_address
        self.functionsRouterAddress = functionsRouterAddress or functions_router_address
        if not self.functionsRouterAddress:
            raise ValueError("functionsRouterAddress is required")
        self.initialized = False
        self.functionsAllowList = None

    def initialize(self) -> None:
        self.functionsAllowList = get_allowlist_contract(
            w3=self.w3, functions_router_address=self.functionsRouterAddress
        )
        self.initialized = True

    def isAllowlisted(self, addr: str) -> bool:
        if not self.initialized:
            self.initialize()
        return is_allowlisted(w3=self.w3, functions_router_address=self.functionsRouterAddress, address=addr)

    def createSubscription(self, subCreateConfig: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cfg = subCreateConfig or {}
        tx_options = (cfg.get("txOptions") or {}).get("overrides") or cfg.get("tx_options")
        confirmations = (cfg.get("txOptions") or {}).get("confirmations", cfg.get("confirmations", 1))
        return create_subscription(
            w3=self.w3,
            functions_router_address=self.functionsRouterAddress,
            private_key_hex=self.private_key_hex,
            consumer_address=cfg.get("consumerAddress") or cfg.get("consumer_address"),
            tx_options=tx_options,
            confirmations=confirmations,
        )

    def addConsumer(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return add_consumer(
            w3=self.w3,
            functions_router_address=self.functionsRouterAddress,
            private_key_hex=self.private_key_hex,
            subscription_id=int(config["subscriptionId"]),
            consumer_address=config["consumerAddress"],
            tx_options=(config.get("txOptions") or {}).get("overrides"),
            confirmations=(config.get("txOptions") or {}).get("confirmations", 1),
        )

    def fundSubscription(self, config: Dict[str, Any]) -> Dict[str, Any]:
        if not self.linkTokenAddress:
            raise ValueError("linkTokenAddress is required")
        return fund_subscription(
            w3=self.w3,
            link_token_address=self.linkTokenAddress,
            functions_router_address=self.functionsRouterAddress,
            private_key_hex=self.private_key_hex,
            subscription_id=int(config["subscriptionId"]),
            juels_amount=config["juelsAmount"],
            tx_options=(config.get("txOptions") or {}).get("overrides"),
            confirmations=(config.get("txOptions") or {}).get("confirmations", 1),
        )

    def getSubscriptionInfo(self, subscriptionId: int | str) -> SubscriptionInfo:
        return get_subscription_info(
            w3=self.w3,
            functions_router_address=self.functionsRouterAddress,
            subscription_id=int(subscriptionId),
        )

    def cancelSubscription(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return cancel_subscription(
            w3=self.w3,
            functions_router_address=self.functionsRouterAddress,
            private_key_hex=self.private_key_hex,
            subscription_id=int(config["subscriptionId"]),
            refund_address=config.get("refundAddress"),
            tx_options=(config.get("txOptions") or {}).get("overrides"),
            confirmations=(config.get("txOptions") or {}).get("confirmations", 1),
        )

    def removeConsumer(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return remove_consumer(
            w3=self.w3,
            functions_router_address=self.functionsRouterAddress,
            private_key_hex=self.private_key_hex,
            subscription_id=int(config["subscriptionId"]),
            consumer_address=config["consumerAddress"],
            tx_options=(config.get("txOptions") or {}).get("overrides"),
            confirmations=(config.get("txOptions") or {}).get("confirmations", 1),
        )

    def requestSubscriptionTransfer(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return request_subscription_transfer(
            w3=self.w3,
            functions_router_address=self.functionsRouterAddress,
            private_key_hex=self.private_key_hex,
            subscription_id=int(config["subscriptionId"]),
            new_owner=config["newOwner"],
            tx_options=(config.get("txOptions") or {}).get("overrides"),
            confirmations=(config.get("txOptions") or {}).get("confirmations", 1),
        )

    def acceptSubTransfer(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return accept_sub_transfer(
            w3=self.w3,
            functions_router_address=self.functionsRouterAddress,
            private_key_hex=self.private_key_hex,
            subscription_id=int(config["subscriptionId"]),
            tx_options=(config.get("txOptions") or {}).get("overrides"),
            confirmations=(config.get("txOptions") or {}).get("confirmations", 1),
        )

    def timeoutRequests(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return timeout_requests(
            w3=self.w3,
            functions_router_address=self.functionsRouterAddress,
            private_key_hex=self.private_key_hex,
            commitments=config["requestCommitments"],
            confirmations=(config.get("txOptions") or {}).get("confirmations", 1),
        )

    def estimateFunctionsRequestCost(self, config: Dict[str, Any]) -> int:
        return estimate_request_cost(
            w3=self.w3,
            functions_router_address=self.functionsRouterAddress,
            don_id=config["donId"],
            subscription_id=int(config["subscriptionId"]),
            callback_gas_limit=int(config["callbackGasLimit"]),
            gas_price_wei=int(config["gasPriceWei"]),
        )


__all__ = [
    "SubscriptionInfo",
    "SubscriptionManager",
    "accept_sub_transfer",
    "add_consumer",
    "cancel_subscription",
    "create_subscription",
    "fund_subscription",
    "get_subscription_info",
    "is_allowlisted",
    "remove_consumer",
    "request_subscription_transfer",
]
