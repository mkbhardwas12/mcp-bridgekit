# Stripe integration skeleton — add after creating a Stripe account
#
# from fastapi import APIRouter, Request
# import stripe
#
# stripe_router = APIRouter()
# stripe.api_key = "sk_test_..."
#
# PRICES = {
#     "free": {"conversations": 10, "price": 0},
#     "pro":  {"conversations": -1, "price": 2900},  # $29/mo in cents
# }
#
# @stripe_router.post("/webhook")
# async def stripe_webhook(request: Request):
#     payload = await request.body()
#     # Verify signature + handle checkout.session.completed
#     return {"status": "ok"}
#
# @stripe_router.get("/pricing")
# async def pricing():
#     return PRICES
