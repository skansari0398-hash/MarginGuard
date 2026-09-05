from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import pandas as pd
import numpy as np
from pathlib import Path

from src.models.predictor import RiskPredictor
from src.policy.intervention_engine import InterventionEngine
from src.policy.seller_policy import SellerPolicy
from src.intelligence.device_intelligence import DeviceIntelligence
from src.actions.action_executor import ActionExecutor
from src.ingestion.order_ingestion import OrderIngestionService


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="MarginGuard API",
    description="AI-powered merchant return risk and intervention engine",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def normalize_device_identifiers(df):
    """
    Normalize device and account identifiers before
    running device intelligence.

    Missing values such as NaN, "nan", "none", and
    "null" must never be treated as real device IDs.
    """
    df = df.copy()

    device_columns = [
        "customer_account_id",
        "device_fingerprint_id",
    ]

    for column in device_columns:
        if column not in df.columns:
            continue

        # Convert common string representations of missing values
        # into actual pandas NaN values.
        df[column] = df[column].replace(
            [
                "",
                "nan",
                "NaN",
                "NAN",
                "none",
                "None",
                "NONE",
                "null",
                "NULL",
            ],
            np.nan,
        )

        # Remove accidental whitespace from string identifiers.
        if df[column].dtype == "object":
            df[column] = df[column].apply(
                lambda value:
                    value.strip()
                    if isinstance(value, str)
                    else value
            )

    return df
# ============================================================
# MODEL + POLICY ENGINE + INTELLIGENCE
# ============================================================

MODEL_PATH = "models/marginguard_logistic_v1.pkl"

predictor = RiskPredictor(MODEL_PATH)
engine = InterventionEngine()
seller_policy = SellerPolicy()
device_intelligence = DeviceIntelligence()
action_executor = ActionExecutor()
order_ingestion = OrderIngestionService()

# Stores the most recently analyzed dataset
# ============================================================
# ORDER DATA STORES
# ============================================================

# Historical / batch analysis dataset.
# Used for analytics and customer-history enrichment.
latest_analysis_df = None

# Stores orders received through the real-time webhook.
# Kept separate from batch-analysis data.
live_orders_df = None

# Dedicated live-order analysis store.
# This is the authoritative source for orders created
# through MarginMart / webhook ingestion.
live_order_store = {}

# Latest live order ID for dashboard retrieval.
latest_live_order_id = None


# ============================================================
# REQUIRED FEATURES
# ============================================================

REQUIRED_FEATURES = [
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
    "gross_margin"
]
# ============================================================
# LIVE ORDER ENRICHMENT
# ============================================================

def is_missing_value(value):
    """
    Return True when a value should be treated as unavailable.
    """
    if value is None:
        return True

    if isinstance(value, str):
        return value.strip().lower() in {
            "",
            "nan",
            "none",
            "null",
        }

    try:
        return bool(pd.isna(value))
    except Exception:
        return False


# ============================================================
# LIVE CUSTOMER HISTORY
# ============================================================

def is_missing_value(value):
    """
    Return True when a value should be treated as unavailable.
    """

    if value is None:
        return True

    if isinstance(value, str):
        return value.strip().lower() in {
            "",
            "nan",
            "none",
            "null",
        }

    try:
        return bool(pd.isna(value))
    except Exception:
        return False


# Dedicated historical customer dataset used by live orders.
customer_history_df = None

HISTORY_COLUMNS = [
    "customer_id",
    "customer_age",
    "account_age_days",
    "past_purchase_count",
    "past_return_rate",
    "past_rto_rate",
]


def load_customer_history():
    """
    Load historical customer behavior for live-order enrichment.

    MarginMart sends current transaction context only.

    MarginGuard owns historical behavioral features:
        - customer_age
        - account_age_days
        - past_purchase_count
        - past_return_rate
        - past_rto_rate
    """

    global customer_history_df

    candidate_paths = [
        "marginguard_synthetic_orders_v2.csv",
        "marginguard_synthetic_orders.csv",
        "marginguard_simulation_ground_truth.csv",

        "data/marginguard_synthetic_orders_v2.csv",
        "data/marginguard_synthetic_orders.csv",
        "data/marginguard_simulation_ground_truth.csv",

        "datasets/marginguard_synthetic_orders_v2.csv",
        "datasets/marginguard_synthetic_orders.csv",
        "datasets/marginguard_simulation_ground_truth.csv",

        "train.csv",
        "data/train.csv",
    ]

    for candidate in candidate_paths:

        path = Path(candidate)

        if not path.exists():
            continue

        try:

            df = pd.read_csv(path)

            if "customer_id" not in df.columns:
                continue

            available_columns = [
                column
                for column in HISTORY_COLUMNS
                if column in df.columns
            ]

            required_history = [
                "customer_id",
                "customer_age",
                "account_age_days",
                "past_purchase_count",
                "past_return_rate",
                "past_rto_rate",
            ]

            if not all(
                column in available_columns
                for column in required_history
            ):
                continue

            history = df[available_columns].copy()

            history["customer_id"] = (
                history["customer_id"]
                .astype(str)
                .str.strip()
            )

            customer_history_df = history

            return {
                "loaded": True,
                "path": str(path),
                "rows": int(len(history)),
            }

        except Exception:
            continue

    customer_history_df = None

    return {
        "loaded": False,
        "path": None,
        "rows": 0,
    }


HISTORY_LOAD_STATUS = load_customer_history()


def enrich_live_order(order):
    """
    Enrich a live storefront order with historical customer behavior.

    IMPORTANT:
    Historical behavior comes from MarginGuard's server-side
    customer-history layer.

    The storefront cannot override these values.
    """

    global latest_analysis_df
    global customer_history_df

    enriched = dict(order)

    customer_id = enriched.get("customer_id")

    if is_missing_value(customer_id):

        raise HTTPException(
            status_code=400,
            detail=(
                "customer_id is required for live orders. "
                "MarginGuard uses customer_id to retrieve "
                "historical customer behavior."
            ),
        )

    customer_id = str(customer_id).strip()

    enriched["customer_id"] = customer_id

    # --------------------------------------------------------
    # Select history source
    # --------------------------------------------------------

    history_source = customer_history_df

    
    if history_source is None:

        raise HTTPException(
            status_code=503,
            detail=(
                "MarginGuard customer history is not loaded. "
                "Place the historical CSV in the project/data "
                "folder or run Batch Analysis first."
            ),
        )

    if "customer_id" not in history_source.columns:

        raise HTTPException(
            status_code=503,
            detail=(
                "Historical data does not contain customer_id. "
                "Live customer enrichment cannot continue."
            ),
        )

    # --------------------------------------------------------
    # Find customer's historical records
    # --------------------------------------------------------

    history = history_source[
        history_source["customer_id"]
        .astype(str)
        .str.strip()
        == customer_id
    ]

    if history.empty:

        raise HTTPException(
            status_code=404,
            detail=(
                f"No historical profile found for "
                f"customer_id={customer_id}."
            ),
        )

    # Use the most recent available historical record.
    row = history.iloc[-1]

    # --------------------------------------------------------
    # Server-authoritative behavioral features
    # --------------------------------------------------------

    historical_fields = [
        "customer_age",
        "account_age_days",
        "past_purchase_count",
        "past_return_rate",
        "past_rto_rate",
    ]

    missing_fields = []

    for field in historical_fields:

        if field not in row.index:
            missing_fields.append(field)
            continue

        if is_missing_value(row[field]):
            missing_fields.append(field)
            continue

        # IMPORTANT:
        # Never trust the storefront's value for these fields.
        enriched[field] = row[field]

    if missing_fields:

        raise HTTPException(
            status_code=503,
            detail=(
                f"Customer history for customer_id={customer_id} "
                f"is incomplete. Missing: {missing_fields}"
            ),
        )

    # --------------------------------------------------------
    # Provenance metadata
    # --------------------------------------------------------

    enriched["customer_history_source"] = (
        "SERVER_SIDE_HISTORY"
    )

    enriched["customer_history_records_found"] = (
        int(len(history))
    )

    return enriched

# ============================================================
# HELPERS
# ============================================================

def get_risk_level(risk):
    """Convert probability into a human-readable risk level."""

    if risk >= 0.90:
        return "CRITICAL"

    elif risk >= 0.75:
        return "HIGH"

    elif risk >= 0.50:
        return "MEDIUM"

    else:
        return "LOW"


def safe_round(value, digits=2):
    """
    Safely round numeric values.
    Returns None for NaN/Infinity so API responses remain JSON-safe.
    """

    try:
        value = float(value)

        if not np.isfinite(value):
            return None

        return round(value, digits)

    except (TypeError, ValueError):
        return None


def clean_value(value):
    """
    Convert NumPy/Pandas values into JSON-safe Python values.
    """

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        if not np.isfinite(float(value)):
            return None
        return float(value)

    if isinstance(value, np.bool_):
        return bool(value)

    if pd.isna(value):
        return None

    return value


def clean_order_dict(order):
    """
    Convert a Pandas row dictionary into JSON-safe values.
    """

    clean_order = {}

    for key, value in order.items():
        clean_order[key] = clean_value(value)

    return clean_order


def clean_expected_losses(expected_losses):
    """
    Convert intervention loss dictionary into JSON-safe values.
    """

    cleaned = {}

    for action, loss in expected_losses.items():
        cleaned[action] = safe_round(loss, 2)

    return cleaned

# ============================================================
# CUSTOMER HISTORY STATUS
# ============================================================

@app.get("/history/status")
def history_status():
    """
    Show whether the live customer-history layer is available.
    """

    return {
        "loaded": customer_history_df is not None,

        "rows": (
            int(len(customer_history_df))
            if customer_history_df is not None
            else 0
        ),

        "source": "SERVER_SIDE_HISTORY",

        "initial_load": HISTORY_LOAD_STATUS,

        "columns": (
            [
                column
                for column in HISTORY_COLUMNS
                if column in customer_history_df.columns
            ]
            if customer_history_df is not None
            else []
        ),
    }

# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "name": "MarginGuard",
        "status": "running"
    }


# ============================================================
# SINGLE ORDER PREDICTION
# ============================================================

@app.post("/predict")
def predict(order: dict):

    # --------------------------------------------------------
    # Predict return risk
    # --------------------------------------------------------

    risk = predictor.predict_risk(order)


    # --------------------------------------------------------
    # Select cost-sensitive intervention
    # --------------------------------------------------------

    decision = engine.recommend(
        order,
        risk
    )


    # --------------------------------------------------------
    # Model explanation
    # --------------------------------------------------------

    explanation = predictor.explain(
        order,
        top_n=8
    )


    # --------------------------------------------------------
    # Device Intelligence
    #
    # This is an additional evidence layer.
    # It does NOT modify the existing ML model input.
    # --------------------------------------------------------

    device_info = device_intelligence.analyze_order(
        order
    )


    # --------------------------------------------------------
    # Risk factors
    # --------------------------------------------------------

    risk_factors = get_risk_factors(
        order,
        device_info
    )


    # --------------------------------------------------------
    # SELLER POLICY DECISION
    # --------------------------------------------------------

    policy_decision = seller_policy.evaluate(
        order,
        risk
    )


    # --------------------------------------------------------
    # Loss economics
    # --------------------------------------------------------

    no_action_loss = float(
        decision["expected_losses"]["NO_ACTION"]
    )

    expected_loss = float(
        decision["expected_loss"]
    )

    loss_avoided = (
        no_action_loss -
        expected_loss
    )


    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {

        # ML risk
        "return_risk":
            safe_round(risk, 4),

        "return_risk_percentage":
            f"{risk:.2%}",


        # RTO risk
        "rto_risk":
            safe_round(
                decision["rto_risk"],
                4
            ),

        "rto_risk_percentage":
            f"{decision['rto_risk']:.2%}",


        # Recommendation
        "recommended_action":
            decision["recommended_action"],


        # Economics
        "expected_loss":
            safe_round(
                expected_loss,
                2
            ),

        "expected_loss_no_action":
            safe_round(
                no_action_loss,
                2
            ),

        "loss_avoided":
            safe_round(
                loss_avoided,
                2
            ),

        "return_cost":
            safe_round(
                decision["return_cost"],
                2
            ),

        "rto_cost":
            safe_round(
                decision["rto_cost"],
                2
            ),


        # All intervention scenarios
        "expected_losses":
            clean_expected_losses(
                decision["expected_losses"]
            ),


        # Risk level
        "risk_level":
            get_risk_level(risk),


        # Supporting evidence
        "risk_factors":
            risk_factors,

        "device_intelligence":
            device_info,

        "policy":
            policy_decision,

        "explanation":
            explanation
    }


# ============================================================
# BATCH PREDICTION
# ============================================================

@app.post("/batch-predict")
async def batch_predict(
    file: UploadFile = File(...)
):

    global latest_analysis_df


    # --------------------------------------------------------
    # Validate file
    # --------------------------------------------------------

    if not file.filename.lower().endswith(".csv"):

        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file."
        )


    # --------------------------------------------------------
    # Read uploaded CSV
    # --------------------------------------------------------

    contents = await file.read()

    from io import BytesIO

    try:

        df = pd.read_csv(
            BytesIO(contents)
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=f"Could not read CSV file: {exc}"
        )


    # --------------------------------------------------------
    # Validate required columns
    # --------------------------------------------------------

    missing = [
        column
        for column in REQUIRED_FEATURES
        if column not in df.columns
    ]

    if missing:

        raise HTTPException(
            status_code=400,
            detail=f"Missing columns: {missing}"
        )


    # --------------------------------------------------------
    # DEVICE INTELLIGENCE
    #
    # This enriches the uploaded dataset with device-level
    # evidence without changing the existing ML model inputs.
    # --------------------------------------------------------

    try:

        # Normalize missing device identifiers first.
        df = normalize_device_identifiers(df)

        # Build device-level evidence from the complete dataset.
        df = device_intelligence.analyze_dataset(
            df
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Device intelligence analysis failed: {exc}"
        )


    # --------------------------------------------------------
    # Predict return risk
    #
    # IMPORTANT:
    # Only the original 21 trained features are passed to
    # the existing ML model.
    # --------------------------------------------------------

    try:

        risks = predictor.predict_batch(
            df[REQUIRED_FEATURES]
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Risk prediction failed: {exc}"
        )

    df["predicted_return_probability"] = risks


    # --------------------------------------------------------
    # Calculate intervention for every order
    # --------------------------------------------------------

    decisions = []

    for _, row in df.iterrows():

        order = row.to_dict()

        decision = engine.recommend(
            order,
            float(
                row[
                    "predicted_return_probability"
                ]
            )
        )

        decisions.append(
            decision
        )


    # --------------------------------------------------------
    # Store decision results
    # --------------------------------------------------------

    df["recommended_action"] = [
        decision["recommended_action"]
        for decision in decisions
    ]

    df["expected_loss"] = [
        decision["expected_loss"]
        for decision in decisions
    ]

    df["expected_loss_no_action"] = [
        decision["expected_losses"]["NO_ACTION"]
        for decision in decisions
    ]


    # --------------------------------------------------------
    # IMPORTANT:
    # Persist the additional economics in the dataframe.
    #
    # This fixes the detail modal showing:
    # RTO Risk = 0%
    # Return Cost = ₹0
    # RTO Cost = ₹0
    # --------------------------------------------------------

    df["rto_risk"] = [
        decision["rto_risk"]
        for decision in decisions
    ]

    df["return_cost"] = [
        decision["return_cost"]
        for decision in decisions
    ]

    df["rto_cost"] = [
        decision["rto_cost"]
        for decision in decisions
    ]


    # --------------------------------------------------------
    # Merchant-level economics
    # --------------------------------------------------------

    baseline_loss = (
        df["expected_loss_no_action"]
        .sum()
    )

    optimized_loss = (
        df["expected_loss"]
        .sum()
    )

    savings = (
        baseline_loss -
        optimized_loss
    )

    savings_percentage = (
        savings /
        baseline_loss *
        100
        if baseline_loss > 0
        else 0
    )


    # --------------------------------------------------------
    # Intervention distribution
    # --------------------------------------------------------

    action_counts = (
        df["recommended_action"]
        .value_counts()
        .to_dict()
    )


    # --------------------------------------------------------
    # Device intelligence summary
    # --------------------------------------------------------

    device_summary = {}

    if "device_risk_signal" in df.columns:

        device_summary["elevated_device_risk_orders"] = int(
            (
                df["device_risk_signal"]
                .astype(str)
                .str.upper()
                .isin(
                    [
                        "ELEVATED",
                        "HIGH",
                        "MULTI_ACCOUNT"
                    ]
                )
            ).sum()
        )

    if "device_multi_account_flag" in df.columns:

        device_summary["multi_account_device_orders"] = int(
            pd.to_numeric(
                df["device_multi_account_flag"],
                errors="coerce"
            )
            .fillna(0)
            .astype(bool)
            .sum()
        )

    if "device_account_count" in df.columns:

        device_summary["max_linked_accounts"] = int(
            pd.to_numeric(
                df["device_account_count"],
                errors="coerce"
            )
            .fillna(0)
            .max()
        )


    # --------------------------------------------------------
    # Save latest analysis
    # --------------------------------------------------------

    latest_analysis_df = df.copy()


    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {

        "orders_analyzed":
            len(df),

        "baseline_expected_loss":
            safe_round(
                baseline_loss,
                2
            ),

        "optimized_expected_loss":
            safe_round(
                optimized_loss,
                2
            ),

        "expected_savings":
            safe_round(
                savings,
                2
            ),

        "savings_percentage":
            safe_round(
                savings_percentage,
                2
            ),

        "action_distribution":
            action_counts,

        "device_intelligence":
            device_summary
    }


# ============================================================
# RISK FACTORS
# ============================================================

def get_risk_factors(
    order,
    device_info=None
):

    factors = []


    # --------------------------------------------------------
    # Historical return rate
    # --------------------------------------------------------

    past_return_rate = float(
        order.get(
            "past_return_rate",
            0
        )
    )

    if past_return_rate >= 0.60:

        factors.append({
            "factor":
                "High historical return rate",

            "value":
                f"{past_return_rate * 100:.1f}%",

            "impact":
                "HIGH"
        })

    elif past_return_rate >= 0.30:

        factors.append({
            "factor":
                "Elevated historical return rate",

            "value":
                f"{past_return_rate * 100:.1f}%",

            "impact":
                "MEDIUM"
        })


    # --------------------------------------------------------
    # RTO rate
    # --------------------------------------------------------

    past_rto_rate = float(
        order.get(
            "past_rto_rate",
            0
        )
    )

    if past_rto_rate >= 0.30:

        factors.append({
            "factor":
                "Elevated RTO history",

            "value":
                f"{past_rto_rate * 100:.1f}%",

            "impact":
                "HIGH"
        })

    elif past_rto_rate >= 0.15:

        factors.append({
            "factor":
                "Elevated RTO history",

            "value":
                f"{past_rto_rate * 100:.1f}%",

            "impact":
                "MEDIUM"
        })


    # --------------------------------------------------------
    # Payment method
    # --------------------------------------------------------

    payment_method = str(
        order.get(
            "payment_method",
            ""
        )
    )

    if payment_method.upper() == "COD":

        factors.append({
            "factor":
                "Cash-on-delivery payment",

            "value":
                "COD",

            "impact":
                "MEDIUM"
        })


    # --------------------------------------------------------
    # Delivery distance
    # --------------------------------------------------------

    distance = float(
        order.get(
            "delivery_distance_km",
            0
        )
    )

    if distance >= 300:

        factors.append({
            "factor":
                "Long delivery distance",

            "value":
                f"{distance:.1f} km",

            "impact":
                "MEDIUM"
        })

    elif distance >= 150:

        factors.append({
            "factor":
                "Long delivery distance",

            "value":
                f"{distance:.1f} km",

            "impact":
                "LOW"
        })


    # --------------------------------------------------------
    # New device
    # --------------------------------------------------------

    new_device = order.get(
        "new_device",
        False
    )

    if (
        str(new_device).lower()
        in [
            "true",
            "1",
            "yes"
        ]
        or new_device == 1
    ):

        factors.append({
            "factor":
                "New device detected",

            "value":
                "Yes",

            "impact":
                "MEDIUM"
        })


    # --------------------------------------------------------
    # Discount
    # --------------------------------------------------------

    discount = float(
        order.get(
            "discount_percent",
            0
        )
    )

    if discount >= 40:

        factors.append({
            "factor":
                "High discount applied",

            "value":
                f"{discount:.1f}%",

            "impact":
                "MEDIUM"
        })

    elif discount >= 25:

        factors.append({
            "factor":
                "High discount applied",

            "value":
                f"{discount:.1f}%",

            "impact":
                "LOW"
        })


    # --------------------------------------------------------
    # Product rating
    # --------------------------------------------------------

    rating = float(
        order.get(
            "product_rating",
            5
        )
    )

    if rating <= 3.0:

        factors.append({
            "factor":
                "Low product rating",

            "value":
                f"{rating:.2f}",

            "impact":
                "MEDIUM"
        })


    # --------------------------------------------------------
    # Delivery time
    # --------------------------------------------------------

    delivery_days = float(
        order.get(
            "estimated_delivery_days",
            0
        )
    )

    if delivery_days >= 5:

        factors.append({
            "factor":
                "Long estimated delivery",

            "value":
                f"{delivery_days:.1f} days",

            "impact":
                "MEDIUM"
        })


    # --------------------------------------------------------
    # DEVICE INTELLIGENCE RISK FACTORS
    # --------------------------------------------------------

    if device_info:

        device_account_count = device_info.get(
            "device_account_count",
            0
        )

        device_previous_returns = device_info.get(
            "device_previous_returns",
            0
        )

        device_previous_rtos = device_info.get(
            "device_previous_rtos",
            0
        )

        device_multi_account_flag = device_info.get(
            "device_multi_account_flag",
            False
        )

        device_risk_signal = str(
            device_info.get(
                "device_risk_signal",
                "LOW"
            )
        ).upper()


        # Multiple accounts

        if device_multi_account_flag:

            factors.append({
                "factor":
                    "Multiple customer accounts linked to device",

                "value":
                    f"{device_account_count} accounts",

                "impact":
                    "HIGH"
            })


        # Previous returns

        if device_previous_returns >= 3:

            factors.append({
                "factor":
                    "Device associated with previous returns",

                "value":
                    f"{device_previous_returns} previous returns",

                "impact":
                    "HIGH"
            })

        elif device_previous_returns > 0:

            factors.append({
                "factor":
                    "Device associated with previous returns",

                "value":
                    f"{device_previous_returns} previous returns",

                "impact":
                    "MEDIUM"
            })


        # Previous RTOs

        if device_previous_rtos >= 2:

            factors.append({
                "factor":
                    "Device associated with previous RTOs",

                "value":
                    f"{device_previous_rtos} previous RTOs",

                "impact":
                    "HIGH"
            })

        elif device_previous_rtos > 0:

            factors.append({
                "factor":
                    "Device associated with previous RTOs",

                "value":
                    f"{device_previous_rtos} previous RTOs",

                "impact":
                    "MEDIUM"
            })


        # Overall device signal

        if device_risk_signal in [
            "HIGH",
            "ELEVATED",
            "MULTI_ACCOUNT"
        ]:

            factors.append({
                "factor":
                    "Elevated device-level risk",

                "value":
                    device_risk_signal,

                "impact":
                    "HIGH"
            })


    return factors

# ============================================================
# LIVE ORDERS QUEUE
# ============================================================

@app.get("/orders/live")
def live_orders(limit: int = 50):

    global live_orders_df

    limit = min(
        max(limit, 1),
        100
    )

    if live_orders_df is None or live_orders_df.empty:
        return {
            "orders": [],
            "total": 0,
            "risky": 0,
            "clear": 0
        }

    orders = live_orders_df.copy()

    # Newest orders first.
    if "ingested_at" in orders.columns:
        orders = orders.sort_values(
            "ingested_at",
            ascending=False
        )

    orders = orders.head(limit).copy()

    # --------------------------------------------------------
    # Add human-readable risk level
    # --------------------------------------------------------

    if "predicted_return_probability" in orders.columns:
        orders["risk_level"] = (
            orders["predicted_return_probability"]
            .apply(get_risk_level)
        )

    # --------------------------------------------------------
    # Determine risky orders
    #
    # MEDIUM / HIGH / CRITICAL = risky
    # LOW = clear
    # --------------------------------------------------------

    if "predicted_return_probability" in orders.columns:
        orders["is_risky"] = (
            pd.to_numeric(
                orders[
                    "predicted_return_probability"
                ],
                errors="coerce"
            ).fillna(0) >= 0.50
        )
    else:
        orders["is_risky"] = False

    # --------------------------------------------------------
    # Select frontend fields
    # --------------------------------------------------------

    columns = [
        "order_id",
        "ingested_at",
        "customer_id",
        "customer_account_id",
        "product_id",
        "product_category",
        "payment_method",
        "shipping_method",
        "order_value",
        "gross_margin",
        "predicted_return_probability",
        "risk_level",
        "is_risky",
        "recommended_action",
        "expected_loss",
        "expected_loss_no_action",
        "rto_risk",
        "return_cost",
        "rto_cost",
        "device_fingerprint_id",
    ]

    available_columns = [
        column
        for column in columns
        if column in orders.columns
    ]

    result = orders[
        available_columns
    ].copy()

    # --------------------------------------------------------
    # Numeric cleanup
    # --------------------------------------------------------

    numeric_columns = [
        "predicted_return_probability",
        "rto_risk",
        "order_value",
        "gross_margin",
        "expected_loss",
        "expected_loss_no_action",
        "return_cost",
        "rto_cost",
    ]

    for column in numeric_columns:

        if column not in result.columns:
            continue

        result[column] = pd.to_numeric(
            result[column],
            errors="coerce"
        )

        result[column] = result[column].fillna(0)

    # --------------------------------------------------------
    # Counts
    # --------------------------------------------------------

    total = len(live_orders_df)

    risky = 0

    if "predicted_return_probability" in live_orders_df.columns:
        risky = int(
            (
                pd.to_numeric(
                    live_orders_df[
                        "predicted_return_probability"
                    ],
                    errors="coerce"
                )
                .fillna(0)
                >= 0.50
            ).sum()
        )

    clear = total - risky

    return {
        "orders": result.to_dict(
            orient="records"
        ),
        "total": total,
        "risky": risky,
        "clear": clear
    }

# ============================================================
# HIGH-RISK ORDERS
# ============================================================

@app.get("/orders/high-risk")
def high_risk_orders(
    limit: int = 20
):

    if latest_analysis_df is None:

        raise HTTPException(
            status_code=400,
            detail="Run batch prediction first."
        )


    # Keep limit between 1 and 100

    limit = min(
        max(limit, 1),
        100
    )


    # --------------------------------------------------------
    # Work on a copy
    # --------------------------------------------------------

    orders = latest_analysis_df.copy()


    # --------------------------------------------------------
    # DEVICE PRIORITY
    #
    # Investigation queue prioritizes:
    #
    # 1. Multi-account devices
    # 2. Elevated device signals
    # 3. Highest ML return risk
    #
    # This does NOT change the ML prediction.
    # It only changes the investigation queue ordering.
    # --------------------------------------------------------

    if "device_multi_account_flag" in orders.columns:

        orders["queue_multi_account"] = (
            pd.to_numeric(
                orders["device_multi_account_flag"],
                errors="coerce"
            )
            .fillna(0)
            .astype(bool)
            .astype(int)
        )

    else:

        orders["queue_multi_account"] = 0


    if "device_risk_signal" in orders.columns:

        orders["queue_device_priority"] = (
            orders["device_risk_signal"]
            .astype(str)
            .str.upper()
            .map({
                "MULTI_ACCOUNT": 3,
                "HIGH": 2,
                "ELEVATED": 1
            })
            .fillna(0)
        )

    else:

        orders["queue_device_priority"] = 0


    # --------------------------------------------------------
    # Sort investigation queue
    #
    # Multi-account evidence comes first, then device
    # severity, then ML return probability.
    # --------------------------------------------------------

    orders = (
        orders
        .sort_values(
            [
                "queue_multi_account",
                "queue_device_priority",
                "predicted_return_probability"
            ],
            ascending=[
                False,
                False,
                False
            ]
        )
        .head(limit)
        .copy()
    )


    # --------------------------------------------------------
    # Standard high-risk fields
    # --------------------------------------------------------

    columns = [
        "order_id",

        "predicted_return_probability",

        "recommended_action",

        "expected_loss",

        "expected_loss_no_action",

        # Economics
        "rto_risk",
        "return_cost",
        "rto_cost",

        "order_value",

        "product_category",

        "payment_method",

        "delivery_distance_km",

        # Device Intelligence
        "customer_account_id",
        "device_fingerprint_id",
        "device_account_count",
        "device_previous_returns",
        "device_previous_rtos",
        "device_multi_account_flag",
        "device_risk_signal"
    ]


    available_columns = [
        column
        for column in columns
        if column in orders.columns
    ]


    result = orders[
        available_columns
    ].copy()


    # --------------------------------------------------------
    # Round numeric values
    # --------------------------------------------------------

    numeric_columns = [
        "predicted_return_probability",
        "expected_loss",
        "expected_loss_no_action",
        "rto_risk",
        "return_cost",
        "rto_cost"
    ]


    for column in numeric_columns:

        if column in result.columns:

            result[column] = result[column].apply(
                lambda value: safe_round(
                    value,
                    4
                    if column in [
                        "predicted_return_probability",
                        "rto_risk"
                    ]
                    else 2
                )
            )


    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "orders":
            result.to_dict(
                orient="records"
            )
    }


# ============================================================
# HIGH-RISK ORDER DETAILS
# ============================================================
# ============================================================
# LIVE ORDER DETAILS
# ============================================================

@app.get("/orders/live/latest")
def get_latest_live_order():
    """
    Return the most recently processed MarginMart order
    and its complete MarginGuard analysis.
    """

    if latest_live_order_id is None:
        return {
            "available": False,
            "order": None,
        }

    analysis = live_order_store.get(
        latest_live_order_id
    )

    if analysis is None:
        return {
            "available": False,
            "order": None,
        }

    return {
        "available": True,
        "order": analysis,
    }


@app.get("/orders/live/{order_id}")
def get_live_order(order_id: str):
    """
    Return the complete MarginGuard analysis for one
    live storefront order.
    """

    analysis = live_order_store.get(
        str(order_id)
    )

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail=f"Live order {order_id} not found."
        )

    return analysis

# ============================================================
# HIGH-RISK ORDER DETAILS
# ============================================================

@app.get("/orders/high-risk/{order_id}")
def high_risk_order_details(order_id: str):

    global latest_analysis_df

    # --------------------------------------------------------
    # Make sure we have processed orders
    # --------------------------------------------------------

    if latest_analysis_df is None:
        raise HTTPException(
            status_code=400,
            detail="No processed orders are available yet."
        )

    if "order_id" not in latest_analysis_df.columns:
        raise HTTPException(
            status_code=400,
            detail="Processed order data does not contain order_id."
        )

    # --------------------------------------------------------
    # Find the exact requested order
    # --------------------------------------------------------

    matching_orders = latest_analysis_df[
        latest_analysis_df["order_id"].astype(str).str.strip()
        == str(order_id).strip()
    ]

    if matching_orders.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Order {order_id} not found."
        )

    # IMPORTANT:
    # Always assign row before using it.
    row = matching_orders.iloc[0]

    # Convert the pandas Series into a normal dictionary.
    order = row.to_dict()

    # --------------------------------------------------------
    # Get prediction
    # --------------------------------------------------------

    if "predicted_return_probability" not in row.index:
        raise HTTPException(
            status_code=500,
            detail=(
                "Processed order is missing "
                "predicted_return_probability."
            )
        )

    risk = float(
        row["predicted_return_probability"]
    )

    # --------------------------------------------------------
    # Economic intervention decision
    # --------------------------------------------------------

    decision = engine.recommend(
        order,
        risk
    )

    # --------------------------------------------------------
    # Model explanation
    # --------------------------------------------------------

    try:
        explanation = predictor.explain(
            order,
            top_n=8
        )
    except Exception:
        explanation = []

    # --------------------------------------------------------
    # Device Intelligence
    # --------------------------------------------------------

    try:
        device_info = device_intelligence.analyze_order(
            order,
            latest_analysis_df
        )
    except Exception:
        device_info = {}

    # --------------------------------------------------------
    # Risk factors
    # --------------------------------------------------------

    try:
        risk_factors = get_risk_factors(
            order,
            device_info
        )
    except Exception:
        risk_factors = []

    # --------------------------------------------------------
    # Seller Policy Decision
    # --------------------------------------------------------

    policy_decision = seller_policy.evaluate(
        order,
        risk
    )

    # --------------------------------------------------------
    # Loss economics
    # --------------------------------------------------------

    expected_loss_no_action = float(
        decision["expected_losses"]["NO_ACTION"]
    )

    expected_loss = float(
        decision["expected_loss"]
    )

    loss_avoided = (
        expected_loss_no_action -
        expected_loss
    )

    # --------------------------------------------------------
    # Clean order data
    # --------------------------------------------------------

    clean_order = clean_order_dict(
        order
    )

    # Add calculated economics directly to order
    # so the frontend can read them reliably.

    clean_order["rto_risk"] = safe_round(
        decision["rto_risk"],
        4
    )

    clean_order["return_cost"] = safe_round(
        decision["return_cost"],
        2
    )

    clean_order["rto_cost"] = safe_round(
        decision["rto_cost"],
        2
    )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "order": clean_order,

        "risk": {
            "probability": safe_round(
                risk,
                4
            ),
            "percentage": f"{risk:.2%}",
            "level": get_risk_level(risk)
        },

        "decision": {
            "recommended_action":
                decision["recommended_action"],

            "return_risk":
                safe_round(
                    risk,
                    4
                ),

            "return_risk_percentage":
                f"{risk:.2%}",

            "rto_risk":
                safe_round(
                    decision["rto_risk"],
                    4
                ),

            "rto_risk_percentage":
                f"{decision['rto_risk']:.2%}",

            "expected_loss":
                safe_round(
                    expected_loss,
                    2
                ),

            "expected_loss_no_action":
                safe_round(
                    expected_loss_no_action,
                    2
                ),

            "loss_avoided":
                safe_round(
                    loss_avoided,
                    2
                ),

            "expected_losses": {
                key: (
                    safe_round(value, 2)
                    if np.isfinite(value)
                    else None
                )
                for key, value
                in decision["expected_losses"].items()
            },

            "return_cost":
                safe_round(
                    decision["return_cost"],
                    2
                ),

            "rto_cost":
                safe_round(
                    decision["rto_cost"],
                    2
                )
        },

        "policy": policy_decision,

        "risk_factors": risk_factors,

        "device_intelligence": device_info,

        "explanation": explanation,

        "recommended_action":
            decision["recommended_action"],

        "expected_loss":
            safe_round(
                expected_loss,
                2
            ),

        "expected_loss_no_action":
            safe_round(
                expected_loss_no_action,
                2
            ),

        "loss_avoided":
            safe_round(
                loss_avoided,
                2
            )
    }


# ============================================================
# SELLER POLICY
# ============================================================

@app.get("/policy")
def get_seller_policy():
    """
    Return the merchant's current MarginGuard policy.
    """

    return {
        "policy":
            seller_policy.get_policy()
    }


@app.put("/policy")
def update_seller_policy(updates: dict):
    """
    Update merchant policy settings.
    """

    try:

        updated_policy = seller_policy.update_policy(
            updates
        )

        return {
            "status": "updated",
            "policy": updated_policy
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


@app.post("/policy/evaluate")
def evaluate_seller_policy(payload: dict):
    """
    Evaluate the current seller policy against
    a supplied order and ML risk score.
    """

    if "order" not in payload:

        raise HTTPException(
            status_code=400,
            detail="Missing 'order' in request."
        )


    if "risk" not in payload:

        raise HTTPException(
            status_code=400,
            detail="Missing 'risk' in request."
        )


    try:

        risk = float(
            payload["risk"]
        )

    except (
        TypeError,
        ValueError
    ):

        raise HTTPException(
            status_code=400,
            detail="Risk must be numeric."
        )


    return seller_policy.evaluate(
        payload["order"],
        risk
    )
# ============================================================
# ACTION EXECUTION LAYER
# ============================================================

@app.post("/orders/{order_id}/actions")
def execute_order_action(
    order_id: str,
    action_request: dict
):
    """
    Execute a merchant-approved operational action.

    Supported actions:
        SEND_CUSTOMER_VERIFICATION
        DISABLE_COD
        SEND_TO_MANUAL_REVIEW
        RELEASE_ORDER
    """

    global latest_analysis_df

    # --------------------------------------------------------
    # Validate analysis state
    # --------------------------------------------------------

    if latest_analysis_df is None:
        raise HTTPException(
            status_code=400,
            detail="Run batch prediction first."
        )

    if "order_id" not in latest_analysis_df.columns:
        raise HTTPException(
            status_code=400,
            detail="The uploaded dataset does not contain order_id."
        )

    # --------------------------------------------------------
    # Find order
    # --------------------------------------------------------

    matching_orders = latest_analysis_df[
        latest_analysis_df["order_id"].astype(str)
        == str(order_id)
    ]

    if matching_orders.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Order {order_id} not found."
        )

    row = matching_orders.iloc[0]
    order = row.to_dict()

    # --------------------------------------------------------
    # Requested action
    # --------------------------------------------------------

    action = str(
        action_request.get(
            "action",
            ""
        )
    ).upper().strip()

    if not action:
        raise HTTPException(
            status_code=400,
            detail="Action is required."
        )

    # --------------------------------------------------------
    # Get current risk
    # --------------------------------------------------------

    risk = float(
        row.get(
            "predicted_return_probability",
            predictor.predict_risk(order)
        )
    )

    # --------------------------------------------------------
    # Get economic recommendation
    # --------------------------------------------------------

    decision = engine.recommend(
        order,
        risk
    )

    recommended_action = decision[
        "recommended_action"
    ]

    # --------------------------------------------------------
    # Map economic recommendation to execution control
    # --------------------------------------------------------

    action_map = {
        "VERIFY":
            "SEND_CUSTOMER_VERIFICATION",

        "COD_CONFIRMATION":
            "DISABLE_COD",

        "MANUAL_REVIEW":
            "SEND_TO_MANUAL_REVIEW",

        "NO_ACTION":
            "RELEASE_ORDER",
    }

    recommended_execution = action_map.get(
        recommended_action,
        "RELEASE_ORDER"
    )

    # --------------------------------------------------------
    # Merchant override detection
    # --------------------------------------------------------

    is_override = (
        action != recommended_execution
    )

    # --------------------------------------------------------
    # Execute action
    # --------------------------------------------------------

    try:

        audit_record = action_executor.execute(
            order=order,
            action=action,
            risk=risk,
            final_control=recommended_action,
            source="MERCHANT_OVERRIDE"
            if is_override
            else "MERCHANT_APPROVAL"
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "success": True,

        "order_id":
            str(order_id),

        "executed_action":
            action,

        "executed_action_label":
            audit_record["action_label"],

        "recommended_action":
            recommended_action,

        "recommended_execution":
            recommended_execution,

        "merchant_override":
            is_override,

        "risk":
            round(
                risk,
                4
            ),

        "risk_percentage":
            f"{risk:.2%}",

        "status":
            audit_record["status"],

        "message":
            audit_record["result"]["message"],

        "action_id":
            audit_record["action_id"],

        "timestamp":
            audit_record["timestamp"],

        "order_state":
            audit_record["order_state"],

        "result":
            audit_record["result"],
    }


# ============================================================
# ORDER ACTION HISTORY
# ============================================================

@app.get("/orders/{order_id}/actions")
def get_order_actions(
    order_id: str
):
    """
    Return the complete action audit history
    for a specific order.
    """

    history = action_executor.get_order_history(
        order_id
    )

    return {
        "order_id":
            str(order_id),

        "actions":
            history,

        "count":
            len(history),
    }


# ============================================================
# GLOBAL ACTION HISTORY
# ============================================================

@app.get("/actions")
def get_actions(
    limit: int = 100
):
    """
    Return recent merchant action activity.
    """

    return {
        "actions":
            action_executor.get_history(
                limit
            )
    }


# ============================================================
# MANUAL REVIEW QUEUE
# ============================================================

@app.get("/actions/manual-review")
def get_manual_review_queue():
    """
    Return orders currently waiting for
    merchant manual review.
    """

    queue = (
        action_executor
        .get_manual_review_queue()
    )

    return {
        "queue":
            queue,

        "count":
            len(queue),
    }


# ============================================================
# CURRENT ORDER CONTROL STATE
# ============================================================

@app.get("/orders/{order_id}/state")
def get_order_state(
    order_id: str
):
    """
    Return the current operational state
    of an order.
    """

    return action_executor.get_order_state(
        order_id
    )
# ============================================================
# REAL-TIME ORDER WEBHOOK
# ============================================================

@app.post("/webhooks/order")
def receive_order_webhook(order: dict):

    global latest_analysis_df
    global live_order_store
    global latest_live_order_id

    # --------------------------------------------------------
    # SERVER-SIDE CUSTOMER ENRICHMENT
    # --------------------------------------------------------

    order = enrich_live_order(order)
    global latest_analysis_df
    # --------------------------------------------------------
    # Device Intelligence
    # --------------------------------------------------------

    device_info = device_intelligence.analyze_order(
        order,
        latest_analysis_df
    )
    risk_factors = get_risk_factors(
        order,
        device_info
    )

    # --------------------------------------------------------
    # INGEST ORDER
    # --------------------------------------------------------

    try:
        ingestion_result = order_ingestion.ingest(
            order
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    normalized_order = ingestion_result[
        "order"
    ]

    # --------------------------------------------------------
    # PREDICT RETURN RISK
    # --------------------------------------------------------

    try:

        risk = float(
            predictor.predict_risk(
                normalized_order
            )
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Risk prediction failed: {exc}"
            )
        )

    # --------------------------------------------------------
    # ECONOMIC INTERVENTION
    # --------------------------------------------------------

    try:

        decision = engine.recommend(
            normalized_order,
            risk
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Intervention evaluation failed: {exc}"
            )
        )

    # --------------------------------------------------------
    # MODEL EXPLANATION
    # --------------------------------------------------------

    try:

        explanation = predictor.explain(
            normalized_order,
            top_n=8
        )

    except Exception:

        explanation = []

    # --------------------------------------------------------
    # RISK LEVEL
    # --------------------------------------------------------

    risk_level = get_risk_level(
        risk
    )

    # --------------------------------------------------------
    # STORE REAL-TIME ORDER
    # --------------------------------------------------------

    order_record = dict(
        normalized_order
    )

    order_record[
        "predicted_return_probability"
    ] = risk

    order_record[
        "recommended_action"
    ] = decision[
        "recommended_action"
    ]

    order_record[
        "expected_loss"
    ] = decision[
        "expected_loss"
    ]

    order_record[
        "expected_loss_no_action"
    ] = decision[
        "expected_losses"
    ][
        "NO_ACTION"
    ]

    # --------------------------------------------------------
    # Additional live-order economics
    # --------------------------------------------------------

    order_record[
        "rto_risk"
    ] = decision[
        "rto_risk"
    ]

    order_record[
        "return_cost"
    ] = decision[
        "return_cost"
    ]

    order_record[
        "rto_cost"
    ] = decision[
        "rto_cost"
    ]

    order_record[
        "risk_level"
    ] = risk_level

    order_record[
        "is_risky"
    ] = risk >= 0.50
        # --------------------------------------------------------
    # COMPLETE LIVE ORDER ANALYSIS
    # --------------------------------------------------------

    expected_loss_no_action = float(
        decision["expected_losses"]["NO_ACTION"]
    )

    expected_loss = float(
        decision["expected_loss"]
    )

    loss_avoided = (
        expected_loss_no_action
        - expected_loss
    )
        # --------------------------------------------------------
    # SELLER POLICY DECISION
    # --------------------------------------------------------

    policy_decision = seller_policy.evaluate(
        normalized_order,
        risk
    )
    live_analysis = {
        "success": True,
        "event": "ORDER_RECEIVED",
        "source": "MARGINMART_WEBHOOK",

        "order_id": str(
            normalized_order["order_id"]
        ),

        "received_at": normalized_order[
            "ingested_at"
        ],

        "order": clean_order_dict(
            normalized_order
        ),

        "risk": {
            "probability": round(
                risk,
                4
            ),
            "percentage": f"{risk:.2%}",
            "level": risk_level,
        },

        "decision": {
            "recommended_action":
                decision["recommended_action"],

            "expected_loss":
                round(
                    expected_loss,
                    2
                ),

            "expected_loss_no_action":
                round(
                    expected_loss_no_action,
                    2
                ),

            "loss_avoided":
                round(
                    loss_avoided,
                    2
                ),

            "rto_risk":
                safe_round(
                    decision["rto_risk"],
                    4
                ),

            "rto_risk_percentage":
                f"{decision['rto_risk']:.2%}",

            "return_cost":
                safe_round(
                    decision["return_cost"],
                    2
                ),

            "rto_cost":
                safe_round(
                    decision["rto_cost"],
                    2
                ),

            "expected_losses":
                clean_expected_losses(
                    decision["expected_losses"]
                ),
        },

        "risk_factors":
            risk_factors,

        "device_intelligence":
            device_info,

        "policy":
            policy_decision,

        "explanation":
            explanation,

        "next_step":
            "Apply the recommended merchant control.",
    }

    # --------------------------------------------------------
    # Add to dedicated live-order queue
    # --------------------------------------------------------

    live_orders_df_new = pd.DataFrame(
        [order_record]
    )

    global live_orders_df

    if live_orders_df is None:
        live_orders_df = live_orders_df_new
    else:
        live_orders_df = pd.concat(
            [
                live_orders_df,
                live_orders_df_new
            ],
            ignore_index=True,
            sort=False
        )

    # Keep the in-memory demo queue bounded.
    if len(live_orders_df) > 500:
        live_orders_df = (
            live_orders_df
            .tail(500)
            .reset_index(drop=True)
        )

    # --------------------------------------------------------
    # SAVE AUTHORITATIVE LIVE ANALYSIS
    # --------------------------------------------------------

    live_order_id = str(
        normalized_order["order_id"]
    )

    live_order_store[
        live_order_id
    ] = live_analysis

    latest_live_order_id = live_order_id
    # --------------------------------------------------------
    # Add to current in-memory order dataset
    # --------------------------------------------------------

    new_order_df = pd.DataFrame(
        [order_record]
    )

    if latest_analysis_df is None:

        latest_analysis_df = new_order_df

    else:

        latest_analysis_df = pd.concat(
            [
                latest_analysis_df,
                new_order_df
            ],
            ignore_index=True,
            sort=False
        )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

        return {
        "success": True,
        "event": "ORDER_RECEIVED",
        "source": "MARGINMART_WEBHOOK",
        "order_id": live_order_id,
        "received_at": normalized_order[
            "ingested_at"
        ],
        "message": (
            "Order received and analyzed by MarginGuard."
        ),
    }