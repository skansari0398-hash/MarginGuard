import joblib
import pandas as pd
import numpy as np


class RiskPredictor:
    """
    Loads the trained MarginGuard model and
    predicts return probability for new orders.
    """

    def __init__(self, model_path):
        self.model = joblib.load(model_path)

    # ============================================================
    # SINGLE PREDICTION
    # ============================================================

    def predict_risk(self, order):
        """
        Predict return probability for one order.
        """

        order_df = pd.DataFrame([order])

        probability = self.model.predict_proba(
            order_df
        )[0, 1]

        return float(probability)

    # ============================================================
    # BATCH PREDICTION
    # ============================================================

    def predict_batch(self, df):
        """
        Predict return probability for a batch of orders.
        """

        probabilities = self.model.predict_proba(
            df
        )[:, 1]

        return probabilities

    # ============================================================
    # MODEL EXPLANATION
    # ============================================================

    def explain(self, order, top_n=8):
        """
        Explain an individual Logistic Regression prediction.

        The model uses transformed features internally, but the
        returned 'value' is converted back to the original
        human-readable order value wherever possible.
        """

        order_df = pd.DataFrame([order])

        model = self.model

        # --------------------------------------------------------
        # Validate Pipeline
        # --------------------------------------------------------

        if not hasattr(model, "named_steps"):

            raise ValueError(
                "The loaded model is not an sklearn Pipeline. "
                "Cannot calculate feature contributions automatically."
            )

        steps = list(
            model.named_steps.items()
        )

        if len(steps) < 2:

            raise ValueError(
                "The model pipeline does not contain a "
                "preprocessor and estimator."
            )

        # --------------------------------------------------------
        # Final estimator
        # --------------------------------------------------------

        estimator_name, estimator = steps[-1]

        if not hasattr(estimator, "coef_"):

            raise ValueError(
                "The final model does not expose Logistic Regression "
                "coefficients."
            )

        # --------------------------------------------------------
        # Preprocessing pipeline
        # --------------------------------------------------------

        preprocessor = model[:-1]

        transformed = preprocessor.transform(
            order_df
        )

        if hasattr(transformed, "toarray"):

            transformed = transformed.toarray()

        transformed = np.asarray(
            transformed
        )

        # --------------------------------------------------------
        # Feature names after preprocessing
        # --------------------------------------------------------

        try:

            feature_names = (
                preprocessor.get_feature_names_out()
            )

        except Exception:

            feature_names = [
                f"feature_{i}"
                for i in range(
                    transformed.shape[1]
                )
            ]

        # --------------------------------------------------------
        # Logistic Regression coefficients
        # --------------------------------------------------------

        coefficients = np.asarray(
            estimator.coef_[0]
        )

        values = transformed[0]

        if len(values) != len(coefficients):

            raise ValueError(
                "Number of transformed features does not match "
                "the number of model coefficients."
            )

        # --------------------------------------------------------
        # Contribution = transformed value × coefficient
        # --------------------------------------------------------

        contributions = (
            values *
            coefficients
        )

        explanation = []

        # --------------------------------------------------------
        # Build explanations
        # --------------------------------------------------------

        for (
            feature,
            transformed_value,
            coefficient,
            contribution
        ) in zip(
            feature_names,
            values,
            coefficients,
            contributions
        ):

            contribution = float(
                contribution
            )

            # ----------------------------------------------------
            # Direction
            # ----------------------------------------------------

            if contribution > 0:

                direction = "INCREASES_RISK"

            elif contribution < 0:

                direction = "DECREASES_RISK"

            else:

                direction = "NEUTRAL"

            # ----------------------------------------------------
            # Clean sklearn feature name
            # ----------------------------------------------------

            clean_name = str(
                feature
            )

            if "__" in clean_name:

                clean_name = clean_name.split(
                    "__",
                    1
                )[1]

            clean_name = clean_name.replace(
                "_",
                " "
            )

            # ----------------------------------------------------
            # Human-readable value
            # ----------------------------------------------------

            display_value = self._get_display_value(
                feature,
                order
            )

            # ----------------------------------------------------
            # Explanation object
            # ----------------------------------------------------

            explanation.append(
                {
                    "feature": clean_name,

                    # Human-readable ORIGINAL value
                    "value": display_value,

                    # Internal transformed value
                    "transformed_value":
                        self._safe_float(
                            transformed_value
                        ),

                    "coefficient":
                        round(
                            float(coefficient),
                            4
                        ),

                    "contribution":
                        round(
                            contribution,
                            4
                        ),

                    "direction":
                        direction
                }
            )

        # --------------------------------------------------------
        # Most influential features first
        # --------------------------------------------------------

        explanation.sort(
            key=lambda item: abs(
                item["contribution"]
            ),
            reverse=True
        )

        return explanation[:top_n]

    # ============================================================
    # HUMAN-READABLE FEATURE VALUES
    # ============================================================

    @staticmethod
    def _get_display_value(
        feature,
        order
    ):
        """
        Return the original human-readable value from the order.

        The Logistic Regression model may receive standardized
        numeric values such as 2.73 or 4.16. Those values are useful
        internally, but the UI should display the original business
        value such as 81.9% or 43.4%.
        """

        feature_name = str(
            feature
        )

        # Remove sklearn transformer prefix.
        if "__" in feature_name:

            feature_name = feature_name.split(
                "__",
                1
            )[1]

        # --------------------------------------------------------
        # Numeric features
        # --------------------------------------------------------

        numeric_features = {

            "customer_age":
                "customer_age",

            "account_age_days":
                "account_age_days",

            "past_purchase_count":
                "past_purchase_count",

            "past_return_rate":
                "past_return_rate",

            "past_rto_rate":
                "past_rto_rate",

            "product_price":
                "product_price",

            "product_rating":
                "product_rating",

            "discount_percent":
                "discount_percent",

            "session_length_minutes":
                "session_length_minutes",

            "num_product_views":
                "num_product_views",

            "estimated_delivery_days":
                "estimated_delivery_days",

            "delivery_distance_km":
                "delivery_distance_km",

            "order_value":
                "order_value",

            "gross_margin":
                "gross_margin",

            "new_device":
                "new_device",

            "is_first_order":
                "is_first_order",

            "used_coupon":
                "used_coupon"
        }

        if feature_name in numeric_features:

            original_key = (
                numeric_features[
                    feature_name
                ]
            )

            if original_key not in order:

                return None

            value = order[
                original_key
            ]

            # -----------------------------------------------
            # Percentage features
            # -----------------------------------------------

            if feature_name in [
                "past_return_rate",
                "past_rto_rate"
            ]:

                try:

                    return (
                        f"{float(value) * 100:.1f}%"
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    return str(value)

            # -----------------------------------------------
            # Discount
            # -----------------------------------------------

            if feature_name == "discount_percent":

                try:

                    return (
                        f"{float(value):.2f}%"
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    return str(value)

            # -----------------------------------------------
            # Distance
            # -----------------------------------------------

            if feature_name == "delivery_distance_km":

                try:

                    return (
                        f"{float(value):.1f} km"
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    return str(value)

            # -----------------------------------------------
            # Account age
            # -----------------------------------------------

            if feature_name == "account_age_days":

                try:

                    return (
                        f"{float(value):.0f} days"
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    return str(value)

            # -----------------------------------------------
            # Delivery days
            # -----------------------------------------------

            if feature_name == "estimated_delivery_days":

                try:

                    return (
                        f"{float(value):.1f} days"
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    return str(value)

            # -----------------------------------------------
            # Currency features
            # -----------------------------------------------

            if feature_name in [
                "product_price",
                "order_value",
                "gross_margin"
            ]:

                try:

                    return (
                        f"₹{float(value):,.2f}"
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    return str(value)

            # -----------------------------------------------
            # Product rating
            # -----------------------------------------------

            if feature_name == "product_rating":

                try:

                    return f"{float(value):.2f}"

                except (
                    TypeError,
                    ValueError
                ):

                    return str(value)

            # -----------------------------------------------
            # Normal numeric values
            # -----------------------------------------------

            return RiskPredictor._safe_float(
                value
            )

        # --------------------------------------------------------
        # One-hot encoded categorical features
        # --------------------------------------------------------

        categorical_features = [
            "product_category",
            "payment_method",
            "shipping_method",
            "device_type"
        ]

        for categorical in categorical_features:

            prefix = (
                categorical +
                "_"
            )

            if feature_name.startswith(
                prefix
            ):

                category = feature_name[
                    len(prefix):
                ]

                return category

        # --------------------------------------------------------
        # Fallback
        # --------------------------------------------------------

        return RiskPredictor._safe_float(
            order.get(
                feature_name,
                "N/A"
            )
        )

    # ============================================================
    # SAFE FLOAT
    # ============================================================

    @staticmethod
    def _safe_float(value):

        try:

            return round(
                float(value),
                4
            )

        except (
            TypeError,
            ValueError
        ):

            return str(value)