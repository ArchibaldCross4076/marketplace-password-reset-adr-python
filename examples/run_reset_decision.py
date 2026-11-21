import argparse

from marketplace_reset_flow import (
    InfraiMarketplaceNotifier,
    MarketplaceForgotPasswordInput,
    MarketplaceResetCoordinator,
)

parser = argparse.ArgumentParser(description="Request a seller reset and notify a buyer")
parser.add_argument("--seller-email", required=True)
parser.add_argument("--buyer-email", required=True)
parser.add_argument("--idempotency-key", required=True)
args = parser.parse_args()

sample = MarketplaceForgotPasswordInput.model_validate(
    {
        "seller": {
            "user_id": "seller-42",
            "email": args.seller_email,
            "store_name": "Sprocket Supply",
            "asset_ids": ["asset-a", "asset-b"],
        },
        "buyer": {
            "user_id": "buyer-9",
            "email": args.buyer_email,
            "open_order_ids": ["ord-9001", "ord-9002"],
        },
        "request": {
            "ip": "203.0.113.10",
            "idempotency_key": args.idempotency_key,
        },
    }
)

result = MarketplaceResetCoordinator(InfraiMarketplaceNotifier()).run(sample)

print(f"reset requested for {result.reset_email_target}")
print(f"buyer update queued for {sample.buyer.email}")
print(f"handoff status: {result.handoff_status}")
print(f"asset access: {result.asset_access}")
print(f"orders in handoff: {', '.join(result.affected_orders)}")
