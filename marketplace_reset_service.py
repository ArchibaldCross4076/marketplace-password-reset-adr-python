from fastapi import FastAPI

from marketplace_reset_flow import (
    InfraiMarketplaceNotifier,
    MarketplaceForgotPasswordInput,
    MarketplaceResetCoordinator,
    MarketplaceResetDecision,
)

app = FastAPI(title="Marketplace password reset ADR service")
coordinator = MarketplaceResetCoordinator(InfraiMarketplaceNotifier())


@app.post("/forgot-password", response_model=MarketplaceResetDecision)
def forgot_password(payload: MarketplaceForgotPasswordInput) -> MarketplaceResetDecision:
    return coordinator.run(payload)
