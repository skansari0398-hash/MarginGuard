import joblib
import pandas as pd
import numpy as np

from src.policy.intervention_engine import InterventionEngine


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_PATH = "models/marginguard_logistic_v1.pkl"
DATA_PATH = "data/marginguard_synthetic_orders.csv"

FEATURES = [
    "customer_age",
    "account_age_days",
    "past_purchase_count",
    "past_return_rate",
    "past_rto_rate",
    "product_category",
    "product_price",
    "product_rating",
    "discount_percent",
    "payment_method",
    "shipping_method",
    "device_type",
    "new_device",
    "is_first_order",
    "used_coupon",
    "session_length_minutes",
    "num_product_views",
    "estimated_delivery_days",
    "delivery_distance_km",
    "order_value",
    "gross_margin",
]

THRESHOLD = 0.50


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(DATA_PATH)

df["order_timestamp"] = pd.to_datetime(
    df["order_timestamp"]
)

df = df.sort_values(
    "order_timestamp"
).reset_index(drop=True)


# ============================================================
# CHRONOLOGICAL HOLD-OUT
# ============================================================

split = int(len(df) * 0.80)

test = df.iloc[split:].copy()

X_test = test[FEATURES]
y_test = test["returned"].astype(int)


# ============================================================
# LOAD MODEL
# ============================================================

model = joblib.load(MODEL_PATH)

probabilities = model.predict_proba(
    X_test
)[:, 1]

predictions = (
    probabilities >= THRESHOLD
).astype(int)


# ============================================================
# INTERVENTION ENGINE
# ============================================================

engine = InterventionEngine()


# ============================================================
# ECONOMIC EVALUATION
# ============================================================

expected_loss_no_action_total = 0.0
expected_loss_with_action_total = 0.0

false_positive_cost_total = 0.0

flagged_orders = 0
intervention_orders = 0

action_counts = {
    "NO_ACTION": 0,
    "VERIFY": 0,
    "COD_CONFIRMATION": 0,
    "MANUAL_REVIEW": 0,
}

false_positive_action_counts = {
    "VERIFY": 0,
    "COD_CONFIRMATION": 0,
    "MANUAL_REVIEW": 0,
    "NO_ACTION": 0,
}


# ============================================================
# PROCESS EACH HELD-OUT ORDER
# ============================================================

for index, (_, row) in enumerate(test.iterrows()):

    order = row.to_dict()

    risk = float(
        probabilities[index]
    )

    actual_return = int(
        y_test.iloc[index]
    )

    # --------------------------------------------------------
    # Get MarginGuard's cost-sensitive decision
    # --------------------------------------------------------

    decision = engine.recommend(
        order,
        risk
    )

    action = decision[
        "recommended_action"
    ]

    no_action_loss = float(
        decision[
            "expected_losses"
        ][
            "NO_ACTION"
        ]
    )

    selected_loss = float(
        decision[
            "expected_loss"
        ]
    )

    expected_loss_no_action_total += (
        no_action_loss
    )

    expected_loss_with_action_total += (
        selected_loss
    )

    action_counts[action] += 1

    # --------------------------------------------------------
    # Flagged order
    # --------------------------------------------------------

    if risk >= THRESHOLD:

        flagged_orders += 1

        if action != "NO_ACTION":
            intervention_orders += 1

    # --------------------------------------------------------
    # FALSE POSITIVE
    #
    # Model says risky, but the order did not return.
    # --------------------------------------------------------

    if risk >= THRESHOLD and actual_return == 0:

        false_positive_action_counts[action] += 1

        # Cost of the intervention itself.
        #
        # These match the current MarginGuard
        # intervention-engine assumptions.
        # They are demo-stage assumptions, not
        # measured treatment costs.

        gross_margin = float(
            order.get(
                "gross_margin",
                0
            )
        )

        if action == "VERIFY":

            intervention_cost = (
                18.0
                + (
                    0.025
                    * gross_margin
                )
            )

        elif action == "COD_CONFIRMATION":

            intervention_cost = 7.0

        elif action == "MANUAL_REVIEW":

            intervention_cost = (
                65.0
                + (
                    0.050
                    * gross_margin
                )
            )

        else:

            intervention_cost = 0.0

        false_positive_cost_total += (
            intervention_cost
        )


# ============================================================
# FINAL METRICS
# ============================================================

total_test_orders = len(test)

total_expected_loss_avoided = (
    expected_loss_no_action_total
    - expected_loss_with_action_total
)

average_loss_avoided_per_order = (
    total_expected_loss_avoided
    / total_test_orders
)

flagged_rate = (
    flagged_orders
    / total_test_orders
)

intervention_rate = (
    intervention_orders
    / total_test_orders
)

average_false_positive_cost = (
    false_positive_cost_total
    / max(
        1,
        sum(
            false_positive_action_counts.values()
        )
    )
)


# ============================================================
# OUTPUT
# ============================================================

print()
print("=" * 64)
print("MARGIN GUARD ECONOMIC / FALSE-POSITIVE EVALUATION")
print("=" * 64)

print()
print("DATASET")
print("-" * 64)

print(
    f"Total dataset:                 {len(df):,}"
)

print(
    f"Development / training:        {split:,}"
)

print(
    f"Held-out test set:             {total_test_orders:,}"
)

print(
    f"Risk threshold:                {THRESHOLD:.2f}"
)


print()
print("RISK SCREENING")
print("-" * 64)

print(
    f"Orders flagged as risky:       {flagged_orders:,}"
)

print(
    f"Risky-order rate:              {flagged_rate:.4%}"
)

print(
    f"Orders receiving intervention: {intervention_orders:,}"
)

print(
    f"Intervention rate:             {intervention_rate:.4%}"
)


print()
print("INTERVENTION MIX")
print("-" * 64)

for action, count in action_counts.items():

    percentage = (
        count
        / total_test_orders
    )

    print(
        f"{action:<25} {count:>8,} "
        f"({percentage:.2%})"
    )


print()
print("FALSE POSITIVE COST")
print("-" * 64)

false_positive_count = sum(
    false_positive_action_counts.values()
)

print(
    f"False positives:               "
    f"{false_positive_count:,}"
)

print(
    f"False-positive intervention cost:"
    f" ₹{false_positive_cost_total:,.2f}"
)

print(
    f"Average FP intervention cost:  "
    f"₹{average_false_positive_cost:,.2f}"
)


print()
print("FALSE POSITIVE ACTION MIX")
print("-" * 64)

for action, count in (
    false_positive_action_counts.items()
):

    if false_positive_count > 0:

        percentage = (
            count
            / false_positive_count
        )

    else:

        percentage = 0.0

    print(
        f"{action:<25} {count:>8,} "
        f"({percentage:.2%})"
    )


print()
print("EXPECTED LOSS ECONOMICS")
print("-" * 64)

print(
    f"Expected loss without action: "
    f"₹{expected_loss_no_action_total:,.2f}"
)

print(
    f"Expected loss with MarginGuard:"
    f" ₹{expected_loss_with_action_total:,.2f}"
)

print(
    f"Expected loss avoided:         "
    f"₹{total_expected_loss_avoided:,.2f}"
)

print(
    f"Average loss avoided/order:    "
    f"₹{average_loss_avoided_per_order:,.2f}"
)


print()
print("=" * 64)
print("IMPORTANT ASSUMPTION")
print("=" * 64)

print(
    "Intervention effectiveness and intervention costs "
    "are currently demo-stage configurable assumptions."
)

print(
    "They should be estimated from historical intervention "
    "outcomes or controlled/quasi-experimental evaluation "
    "in production."
)

print("=" * 64)
print()
# ============================================================
# SAVE RESULTS
# ============================================================

from pathlib import Path

results_dir = Path("evaluation_results")
results_dir.mkdir(exist_ok=True)

results_file = results_dir / "economic_evaluation.txt"

with open(results_file, "w", encoding="utf-8") as f:

    f.write("MARGIN GUARD ECONOMIC / FALSE-POSITIVE EVALUATION\n")
    f.write("=" * 64 + "\n\n")

    f.write("DATASET\n")
    f.write("-" * 64 + "\n")
    f.write(f"Total dataset:                 {len(df):,}\n")
    f.write(f"Development / training:        {split:,}\n")
    f.write(f"Held-out test set:             {total_test_orders:,}\n")
    f.write(f"Risk threshold:                {THRESHOLD:.2f}\n\n")

    f.write("RISK SCREENING\n")
    f.write("-" * 64 + "\n")
    f.write(f"Orders flagged as risky:       {flagged_orders:,}\n")
    f.write(f"Risky-order rate:              {flagged_rate:.4%}\n")
    f.write(f"Orders receiving intervention: {intervention_orders:,}\n")
    f.write(f"Intervention rate:             {intervention_rate:.4%}\n\n")

    f.write("INTERVENTION MIX\n")
    f.write("-" * 64 + "\n")

    for action, count in action_counts.items():
        percentage = count / total_test_orders
        f.write(
            f"{action:<25} {count:>8,} "
            f"({percentage:.2%})\n"
        )

    f.write("\nFALSE POSITIVE COST\n")
    f.write("-" * 64 + "\n")
    f.write(
        f"False positives:               "
        f"{false_positive_count:,}\n"
    )
    f.write(
        f"False-positive intervention cost:"
        f" ₹{false_positive_cost_total:,.2f}\n"
    )
    f.write(
        f"Average FP intervention cost:  "
        f"₹{average_false_positive_cost:,.2f}\n"
    )

    f.write("\nFALSE POSITIVE ACTION MIX\n")
    f.write("-" * 64 + "\n")

    for action, count in false_positive_action_counts.items():

        percentage = (
            count / false_positive_count
            if false_positive_count > 0
            else 0
        )

        f.write(
            f"{action:<25} {count:>8,} "
            f"({percentage:.2%})\n"
        )

    f.write("\nEXPECTED LOSS ECONOMICS\n")
    f.write("-" * 64 + "\n")
    f.write(
        f"Expected loss without action: "
        f"₹{expected_loss_no_action_total:,.2f}\n"
    )
    f.write(
        f"Expected loss with MarginGuard:"
        f" ₹{expected_loss_with_action_total:,.2f}\n"
    )
    f.write(
        f"Expected loss avoided:         "
        f"₹{total_expected_loss_avoided:,.2f}\n"
    )
    f.write(
        f"Average loss avoided/order:    "
        f"₹{average_loss_avoided_per_order:,.2f}\n"
    )

    f.write("\nIMPORTANT ASSUMPTION\n")
    f.write("=" * 64 + "\n")
    f.write(
        "Intervention effectiveness and intervention costs are "
        "demo-stage configurable assumptions.\n"
    )
    f.write(
        "Production should estimate these from historical "
        "intervention outcomes or controlled/quasi-experimental "
        "evaluation.\n"
    )

print(f"\nResults saved to: {results_file}")