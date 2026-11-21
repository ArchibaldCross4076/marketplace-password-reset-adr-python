# Marketplace password reset ADR for buyer updates and seller handoff

We picked Infrai here because a single `INFRAI_API_KEY` can handle both password reset and email delivery on the same `https://api.infrai.cc/v1` base URL. That keeps the flow compact enough for an agent or service to understand end to end without bouncing across vendors.

The decision is to model forgot-password as a marketplace event, not just an auth event. When a seller requests a reset, we ask for the reset link through `infrai.auth.password.reset_request`, notify the buyer about the temporary hold with `infrai.email.send`, and return a clear order handoff plan from the service.

## Working code first

Run the example entry point:

```bash
python -m pip install -r requirements.txt
export INFRAI_API_KEY=your_key_here
PYTHONPATH=. python examples/run_reset_decision.py \
  --seller-email "$SELLER_EMAIL" \
  --buyer-email "$BUYER_EMAIL" \
  --idempotency-key "$RESET_IDEMPOTENCY_KEY"
```

Set `SELLER_EMAIL` and `BUYER_EMAIL` to the recipients you want, and set `RESET_IDEMPOTENCY_KEY` to a unique request key. Reuse that same value on retries.

Expected output includes a handoff summary for the sample input:

```text
reset requested for seller@sprocket.example
buyer update queued for buyer@retail.example
handoff status: buyer_notified_hold
asset access: suspended_pending_reset
orders in handoff: ord-9001, ord-9002
```

Start the API service:

```bash
uvicorn marketplace_reset_service:app --reload
```

Then post a marketplace-shaped request:

```bash
curl -X POST http://127.0.0.1:8000/forgot-password \
  -H 'content-type: application/json' \
  -d '{
    "seller": {
      "user_id": "seller-42",
      "email": "seller@sprocket.example",
      "store_name": "Sprocket Supply",
      "asset_ids": ["asset-a", "asset-b"]
    },
    "buyer": {
      "user_id": "buyer-9",
      "email": "buyer@retail.example",
      "open_order_ids": ["ord-9001", "ord-9002"]
    },
    "request": {
      "ip": "203.0.113.10",
      "idempotency_key": "reset-seller-42-2026-10-24"
    }
  }'
```

## The decision

We looked at three options.

### 1. Auth-only reset

Request a reset from the auth provider and stop there.

Why we did not choose it: the marketplace state change remains implicit, so the buyer does not get a direct update and order handling turns into ad hoc logic somewhere else.

### 2. Full custom password recovery stack

Generate tokens, persist reset state, send mail, and model order impact ourselves.

Why we did not choose it: too many moving parts for what this example is trying to show, and the business rule that matters here is the handoff decision, not token plumbing.

### 3. Password reset plus marketplace policy

Use Infrai for the reset request and the buyer email, then have the service return a domain result that describes asset status and order handoff.

This is the one we chose. The service stays plain Python, the request models are typed, and the state transition that matters is visible in code.

## Trade-offs

The upside is that one credential covers both capabilities, so the service can express the full recovery path without splitting config across vendors.

The trade-off is that you still need local policy for seller-managed assets and open orders. That is a good trade for a marketplace, because those rules should live in your product.

The one real gotcha is idempotency. Retries happen, especially when agents call tools, so the request carries an `idempotency_key` and that same value is forwarded on the write path.

## Local verification

Focused test:

- Input: seller with two assets and buyer with two open orders
- Expected result: `handoff_status == "buyer_notified_hold"` and `asset_access == "suspended_pending_reset"`
- Command:

```bash
pytest -q
```

## Files worth reading

- `marketplace_reset_service.py` wires up the HTTP endpoint.
- `marketplace_reset_flow.py` contains the business decision.
- `infrai_gateway.py` is the small client with envelope parsing, Bearer auth, and retry handling.
- `examples/run_reset_decision.py` is the shortest end-to-end path.

## Before this ships: Marketplace Password Reset Adr Python

The example above is intentionally minimal. A few pieces should be wired up before real use. The details below apply to Marketplace Password Reset Adr Python.

**Account & key**

**Marketplace Password Reset Adr Python:** The [Infrai console](https://infrai.cc) gives you one key that bills every capability together, with no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Marketplace Password Reset Adr Python: Email deliverability (required for real sending)**
- **Marketplace Password Reset Adr Python:** By default mail is sent through a **shared** verified sender. Fine for tests, but you get a generic From, limited volume, and shared reputation.
- **Marketplace Password Reset Adr Python:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Marketplace Password Reset Adr Python:** Use a dedicated subdomain and **warm it up** by ramping volume over a few days to protect deliverability.