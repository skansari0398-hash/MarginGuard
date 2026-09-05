from datetime import datetime, timezone
from typing import Dict, Any


class OrderIngestionService:
    """
    Real-time order ingestion service for MarginGuard.

    Receives an incoming order from a merchant/store webhook
    and normalizes it into the structure expected by the
    existing MarginGuard risk pipeline.

    This service intentionally does not contain ML logic.
    It only handles:
        webhook payload
        -> validation
        -> normalization
        -> ingestion metadata
    """

    REQUIRED_FIELDS = [
        "order_id",
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

    def __init__(self):
        self.ingested_orders = {}

    # ============================================================
    # VALIDATION
    # ============================================================

    def validate_order(
        self,
        order: Dict[str, Any]
    ):
        missing = [
            field
            for field in self.REQUIRED_FIELDS
            if field not in order
        ]

        if missing:
            raise ValueError(
                f"Missing required order fields: {missing}"
            )

    # ============================================================
    # NORMALIZATION
    # ============================================================

    def normalize_order(
        self,
        order: Dict[str, Any]
    ) -> Dict[str, Any]:

        normalized = dict(order)

        # --------------------------------------------------------
        # Normalize order ID
        # --------------------------------------------------------

        normalized["order_id"] = str(
            normalized["order_id"]
        )

        # --------------------------------------------------------
        # Normalize numeric fields
        # --------------------------------------------------------

        numeric_fields = [
            "customer_age",
            "account_age_days",
            "past_purchase_count",
            "past_return_rate",
            "past_rto_rate",
            "product_price",
            "product_rating",
            "discount_percent",
            "session_length_minutes",
            "num_product_views",
            "estimated_delivery_days",
            "delivery_distance_km",
            "order_value",
            "gross_margin",
        ]

        for field in numeric_fields:

            if field in normalized:

                try:
                    normalized[field] = float(
                        normalized[field]
                    )

                except (
                    TypeError,
                    ValueError
                ):
                    raise ValueError(
                        f"Invalid numeric value for "
                        f"{field}: "
                        f"{normalized[field]}"
                    )

        # --------------------------------------------------------
        # Normalize boolean fields
        # --------------------------------------------------------

        boolean_fields = [
            "new_device",
            "is_first_order",
            "used_coupon",
        ]

        for field in boolean_fields:

            if field not in normalized:
                continue

            value = normalized[field]

            if isinstance(value, bool):
                continue

            if isinstance(value, str):

                normalized[field] = (
                    value.strip().lower()
                    in {
                        "true",
                        "1",
                        "yes",
                        "y",
                    }
                )

            else:

                normalized[field] = bool(
                    value
                )

        # --------------------------------------------------------
        # Normalize text fields
        # --------------------------------------------------------

        text_fields = [
            "product_category",
            "payment_method",
            "shipping_method",
            "device_type",
        ]

        for field in text_fields:

            if field in normalized:

                normalized[field] = str(
                    normalized[field]
                )

        # --------------------------------------------------------
        # Ingestion metadata
        # --------------------------------------------------------

        normalized[
            "ingestion_source"
        ] = "WEBHOOK"

        normalized[
            "ingested_at"
        ] = datetime.now(
            timezone.utc
        ).isoformat()

        # --------------------------------------------------------
        # Store latest version
        # --------------------------------------------------------

        self.ingested_orders[
            normalized["order_id"]
        ] = normalized

        return normalized

    # ============================================================
    # INGEST
    # ============================================================

    def ingest(
        self,
        order: Dict[str, Any]
    ) -> Dict[str, Any]:

        if not isinstance(order, dict):
            raise ValueError(
                "Order payload must be a JSON object."
            )

        self.validate_order(order)

        normalized = self.normalize_order(
            order
        )

        return {
            "success": True,
            "order_id": normalized["order_id"],
            "source": "WEBHOOK",
            "received_at": normalized[
                "ingested_at"
            ],
            "order": normalized,
        }

    # ============================================================
    # GET INGESTED ORDER
    # ============================================================

    def get_order(
        self,
        order_id: str
    ):

        return self.ingested_orders.get(
            str(order_id)
        )

    # ============================================================
    # GET RECENT ORDERS
    # ============================================================

    def get_recent_orders(
        self,
        limit: int = 50
    ):

        limit = min(
            max(int(limit), 1),
            200
        )

        orders = list(
            self.ingested_orders.values()
        )

        return orders[-limit:][::-1]