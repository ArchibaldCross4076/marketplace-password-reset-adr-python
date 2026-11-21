from typing import List, Protocol

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from infrai_gateway import infrai


class SellerAccount(BaseModel):
    user_id: str
    email: EmailStr
    store_name: str
    asset_ids: List[str] = Field(default_factory=list)


class BuyerAccount(BaseModel):
    user_id: str
    email: EmailStr
    open_order_ids: List[str] = Field(default_factory=list)


class ResetRequestContext(BaseModel):
    ip: str
    idempotency_key: str


class MarketplaceForgotPasswordInput(BaseModel):
    seller: SellerAccount
    buyer: BuyerAccount
    request: ResetRequestContext


class MarketplaceResetDecision(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    reset_requested: bool
    reset_email_target: EmailStr
    buyer_update_sent: bool
    buyer_message_id: str
    asset_access: str
    handoff_status: str
    affected_orders: List[str]
    affected_assets: List[str]


class PasswordAndEmailPort(Protocol):
    def request_password_reset(self, seller_email: str, idempotency_key: str) -> None:
        ...

    def notify_buyer(self, buyer_email: str, seller_store_name: str, order_ids: List[str], asset_ids: List[str], idempotency_key: str) -> str:
        ...


class InfraiMarketplaceNotifier:
    def request_password_reset(self, seller_email: str, idempotency_key: str) -> None:
        infrai.auth.password.reset_request(email=seller_email, idempotency_key=idempotency_key)

    def notify_buyer(self, buyer_email: str, seller_store_name: str, order_ids: List[str], asset_ids: List[str], idempotency_key: str) -> str:
        orders = ", ".join(order_ids) if order_ids else "none"
        assets = ", ".join(asset_ids) if asset_ids else "none"
        env = infrai.email.send(
            to=buyer_email,
            idempotency_key=idempotency_key,
            subject=f"Update for your orders from {seller_store_name}",
            body=(
                f"We received a password reset request for the seller account behind {seller_store_name}. "
                f"Orders on temporary hold: {orders}. Seller-managed assets pending review: {assets}. "
                f"We will resume handoff after account access is restored."
            ),
        )
        return str(env["data"]["message_id"])


class MarketplaceResetCoordinator:
    def __init__(self, gateway: PasswordAndEmailPort):
        self.gateway = gateway

    def run(self, payload: MarketplaceForgotPasswordInput) -> MarketplaceResetDecision:
        self.gateway.request_password_reset(
            seller_email=str(payload.seller.email),
            idempotency_key=payload.request.idempotency_key,
        )
        message_id = self.gateway.notify_buyer(
            buyer_email=str(payload.buyer.email),
            seller_store_name=payload.seller.store_name,
            order_ids=payload.buyer.open_order_ids,
            asset_ids=payload.seller.asset_ids,
            idempotency_key=payload.request.idempotency_key,
        )
        handoff_status = "buyer_notified_hold" if payload.buyer.open_order_ids else "no_open_orders"
        asset_access = "suspended_pending_reset" if payload.seller.asset_ids else "no_managed_assets"
        return MarketplaceResetDecision(
            reset_requested=True,
            reset_email_target=payload.seller.email,
            buyer_update_sent=True,
            buyer_message_id=message_id,
            asset_access=asset_access,
            handoff_status=handoff_status,
            affected_orders=payload.buyer.open_order_ids,
            affected_assets=payload.seller.asset_ids,
        )
