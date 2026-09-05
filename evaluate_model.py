import joblib
import pandas as pd
import numpy as np

from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    confusion_matrix,
    roc_auc_score,
)

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

df = pd.read_csv(DATA_PATH)

df["order_timestamp"] = pd.to_datetime(
    df["order_timestamp"]
)

df = df.sort_values("order_timestamp").reset_index(drop=True)

# Chronological held-out test set:
# first 80% = development data
# final 20% = unseen test data
split = int(len(df) * 0.80)

test = df.iloc[split:].copy()

X_test = test[FEATURES]
y_test = test["returned"].astype(int)

model = joblib.load(MODEL_PATH)

probabilities = model.predict_proba(X_test)[:, 1]

# MarginGuard MEDIUM threshold
threshold = 0.50

predictions = (
    probabilities >= threshold
).astype(int)

tn, fp, fn, tp = confusion_matrix(
    y_test,
    predictions
).ravel()

precision = precision_score(
    y_test,
    predictions,
    zero_division=0
)

recall = recall_score(
    y_test,
    predictions,
    zero_division=0
)

f1 = f1_score(
    y_test,
    predictions,
    zero_division=0
)

accuracy = accuracy_score(
    y_test,
    predictions
)

auc = roc_auc_score(
    y_test,
    probabilities
)

print("\n" + "=" * 60)
print("MARGINGUARD HELD-OUT MODEL EVALUATION")
print("=" * 60)

print(f"Total dataset:        {len(df):,}")
print(f"Training/development: {split:,}")
print(f"Held-out test set:    {len(test):,}")
print()

print(f"Threshold:            {threshold:.2f}")
print(f"Precision:            {precision:.4f}")
print(f"Recall:               {recall:.4f}")
print(f"F1 Score:             {f1:.4f}")
print(f"Accuracy:             {accuracy:.4f}")
print(f"ROC-AUC:              {auc:.4f}")
print()

print("CONFUSION MATRIX")
print(f"True Negatives:       {tn:,}")
print(f"False Positives:      {fp:,}")
print(f"False Negatives:      {fn:,}")
print(f"True Positives:       {tp:,}")

print()
print("FALSE-POSITIVE RATE")
fpr = fp / (fp + tn) if (fp + tn) else 0
print(f"FPR:                  {fpr:.4f}")

print("=" * 60)

# ============================================================
# SAVE RESULTS
# ============================================================

from pathlib import Path

results_dir = Path("evaluation_results")
results_dir.mkdir(exist_ok=True)

results_file = results_dir / "model_evaluation.txt"

with open(results_file, "w", encoding="utf-8") as f:
    f.write("MARGIN GUARD HELD-OUT MODEL EVALUATION\n")
    f.write("=" * 60 + "\n\n")

    f.write(f"Total dataset: {len(df):,}\n")
    f.write(f"Training/development set: {split:,}\n")
    f.write(f"Held-out test set: {len(test):,}\n\n")

    f.write(f"Threshold: {threshold:.2f}\n")
    f.write(f"Precision: {precision:.4f}\n")
    f.write(f"Recall: {recall:.4f}\n")
    f.write(f"F1 Score: {f1:.4f}\n")
    f.write(f"Accuracy: {accuracy:.4f}\n")
    f.write(f"ROC-AUC: {auc:.4f}\n\n")

    f.write("CONFUSION MATRIX\n")
    f.write("-" * 60 + "\n")
    f.write(f"True Negatives: {tn:,}\n")
    f.write(f"False Positives: {fp:,}\n")
    f.write(f"False Negatives: {fn:,}\n")
    f.write(f"True Positives: {tp:,}\n\n")

    f.write("FALSE-POSITIVE RATE\n")
    f.write("-" * 60 + "\n")

    fpr = fp / (fp + tn) if (fp + tn) else 0

    f.write(f"FPR: {fpr:.4f}\n")

print(f"\nResults saved to: {results_file}")