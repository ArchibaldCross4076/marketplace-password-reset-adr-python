from marketplace_reset_flow import (
    MarketplaceForgotPasswordInput,
    MarketplaceResetCoordinator,
)


class FakeGateway:
    def __init__(self) -> None:
        self.reset_emails = []
        self.buyer_notifications = []

    def request_password_reset(self, seller_email: str, idempotency_key: str) -> None:
        self.reset_emails.append((seller_email, idempotency_key))

    def notify_buyer(self, buyer_email: str, seller_store_name: str, order_ids, asset_ids, idempotency_key) -> str:
        self.buyer_notifications.append((buyer_email, seller_store_name, list(order_ids), list(asset_ids), idempotency_key))
        return "msg-123"


def test_marketplace_reset_suspends_assets_and_marks_orders_on_hold() -> None:
    payload = MarketplaceForgotPasswordInput.model_validate(
        {
            "seller": {
                "user_id": "seller-42",
                "email": "seller@sprocket.example",
                "store_name": "Sprocket Supply",
                "asset_ids": ["asset-a", "asset-b"],
            },
            "buyer": {
                "user_id": "buyer-9",
                "email": "buyer@retail.example",
                "open_order_ids": ["ord-9001", "ord-9002"],
            },
            "request": {
                "ip": "203.0.113.10",
                "idempotency_key": "reset-seller-42-2026-10-24",
            },
        }
    )
    gateway = FakeGateway()
    result = MarketplaceResetCoordinator(gateway).run(payload)

    assert gateway.reset_emails == [("seller@sprocket.example", "reset-seller-42-2026-10-24")]
    assert result.handoff_status == "buyer_notified_hold"
    assert result.asset_access == "suspended_pending_reset"
    assert result.buyer_message_id == "msg-123"
    assert result.affected_orders == ["ord-9001", "ord-9002"]


def test_notifier_forwards_idempotency_to_both_write_requests(monkeypatch):
    from infrai_gateway import InfraiClient
    import marketplace_reset_flow as flow

    calls = []
    client = InfraiClient(api_key="local-test")

    def capture(path, body):
        calls.append((path, body))
        return {"data": {"message_id": "msg-test"}}

    monkeypatch.setattr(client, "_post", capture)
    monkeypatch.setattr(flow, "infrai", client)
    notifier = flow.InfraiMarketplaceNotifier()
    notifier.request_password_reset("seller@example.com", "retry-key")
    notifier.notify_buyer("buyer@example.com", "Store", [], [], "retry-key")

    assert [path for path, _ in calls] == ["/auth/password/reset_request", "/email/send"]
    assert all(body["idempotency_key"] == "retry-key" for _, body in calls)
