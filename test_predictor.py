from src.models.predictor import RiskPredictor
from src.policy.intervention_engine import InterventionEngine


MODEL_PATH = "models/marginguard_logistic_v1.pkl"


order = {
    "customer_age": 28,
    "account_age_days": 320,
    "past_purchase_count": 6,
    "past_return_rate": 0.35,
    "past_rto_rate": 0.12,
    "product_category": "Fashion",
    "product_price": 2500,
    "product_rating": 3.8,
    "discount_percent": 25,
    "payment_method": "COD",
    "shipping_method": "Standard",
    "device_type": "Android",
    "new_device": 0,
    "is_first_order": 0,
    "used_coupon": 1,
    "session_length_minutes": 12,
    "num_product_views": 8,
    "estimated_delivery_days": 4,
    "delivery_distance_km": 180,
    "order_value": 1875,
    "gross_margin": 500
}


# 1. Predict risk
predictor = RiskPredictor(MODEL_PATH)

risk = predictor.predict_risk(order)


# 2. Decide intervention
engine = InterventionEngine()

decision = engine.recommend(order, risk)


# 3. Display result
print("\n========== MARGIN GUARD ==========")

print(f"Return risk: {decision['risk']:.2%}")

print(f"\nRecommended action:")
print(decision["recommended_action"])

print("\nExpected losses:")

for action, loss in decision["expected_losses"].items():
    print(f"  {action:<20} ₹{loss:,.2f}")

print(
    f"\nMinimum expected loss: "
    f"₹{decision['expected_loss']:,.2f}"
)

print("==================================")