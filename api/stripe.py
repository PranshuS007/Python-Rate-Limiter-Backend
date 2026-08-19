from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config.settings import settings

try:
    import stripe as stripe_sdk
except ImportError:
    stripe_sdk = None


router = APIRouter(prefix="/api", tags=["checkout"])


class CheckoutRequest(BaseModel):
    plan: str


PRICE_PLANS = {
    "drop-in": {
        "name": "Drop-in Yoga Class",
        "description": "One class at Still Studio",
        "unit_amount": 2200,
    },
    "five-pack": {
        "name": "5 Class Pack",
        "description": "Five yoga classes, valid for three months",
        "unit_amount": 9500,
    },
    "ten-pack": {
        "name": "10 Class Pack",
        "description": "Ten yoga classes, valid for six months",
        "unit_amount": 17000,
    },
}


@router.post("/checkout")
async def create_checkout_session(payload: CheckoutRequest, request: Request):
    if stripe_sdk is None:
        raise HTTPException(status_code=503, detail="Stripe is not installed on the server.")

    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe checkout is not configured yet.")

    plan = PRICE_PLANS.get(payload.plan)
    if plan is None:
        raise HTTPException(status_code=400, detail="Unknown pricing option.")

    stripe_sdk.api_key = settings.stripe_secret_key
    base_url = str(request.base_url)

    try:
        session = stripe_sdk.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": settings.stripe_currency,
                    "product_data": {
                        "name": plan["name"],
                        "description": plan["description"],
                    },
                    "unit_amount": plan["unit_amount"],
                },
                "quantity": 1,
            }],
            success_url=f"{base_url}classes?success=1&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}classes?cancelled=1",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to start Stripe checkout.") from exc

    return {"url": session.url}


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    if stripe_sdk is None or not settings.stripe_webhook_secret:
        return {"received": True, "verified": False}

    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    try:
        stripe_sdk.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook.") from exc

    return {"received": True, "verified": True}
