import numpy as np
import pandas as pd


class RiskExplainer:
    def __init__(self, predictor):
        self.predictor = predictor

    def explain(self, order, top_n=8):
        """
        Explain an individual Logistic Regression prediction.

        Returns the transformed features that contributed most strongly
        to increasing or decreasing predicted return risk.
        """

        model = self.predictor.model

        # Convert order to one-row DataFrame
        input_df = pd.DataFrame([order])

        # --------------------------------------------------
        # Case 1:
        # Saved model is an sklearn Pipeline
        # --------------------------------------------------
        if hasattr(model, "named_steps"):

            steps = list(model.named_steps.items())

            if len(steps) < 2:
                raise ValueError(
                    "The saved pipeline does not contain enough steps "
                    "to calculate feature contributions."
                )

            # Final estimator should be LogisticRegression
            estimator_name, estimator = steps[-1]

            # Everything before the estimator performs preprocessing
            preprocessor = model[:-1]

            transformed = preprocessor.transform(input_df)

            # Get transformed feature names
            try:
                feature_names = preprocessor.get_feature_names_out()
            except Exception:
                feature_names = [
                    f"feature_{i}"
                    for i in range(transformed.shape[1])
                ]

        # --------------------------------------------------
        # Case 2:
        # Predictor stores preprocessing separately
        # --------------------------------------------------
        elif hasattr(self.predictor, "preprocessor"):

            preprocessor = self.predictor.preprocessor
            estimator = model

            transformed = preprocessor.transform(input_df)

            try:
                feature_names = preprocessor.get_feature_names_out()
            except Exception:
                feature_names = [
                    f"feature_{i}"
                    for i in range(transformed.shape[1])
                ]

        else:
            raise ValueError(
                "Could not locate the preprocessing pipeline."
            )

        # Convert sparse matrix if necessary
        if hasattr(transformed, "toarray"):
            transformed = transformed.toarray()

        transformed = np.asarray(transformed)

        # Logistic Regression coefficients
        coefficients = np.asarray(estimator.coef_[0])

        values = transformed[0]

        if len(values) != len(coefficients):
            raise ValueError(
                "Feature count does not match Logistic Regression "
                "coefficient count."
            )

        # Contribution to the model's log-odds
        contributions = values * coefficients

        explanation = []

        for feature, value, coefficient, contribution in zip(
            feature_names,
            values,
            coefficients,
            contributions
        ):
            explanation.append(
                {
                    "feature": self._clean_feature_name(str(feature)),
                    "value": self._safe_float(value),
                    "coefficient": round(float(coefficient), 4),
                    "contribution": round(float(contribution), 4),
                    "direction": (
                        "INCREASES_RISK"
                        if contribution > 0
                        else "DECREASES_RISK"
                        if contribution < 0
                        else "NEUTRAL"
                    ),
                }
            )

        # Most influential features first
        explanation.sort(
            key=lambda item: abs(item["contribution"]),
            reverse=True
        )

        return explanation[:top_n]

    @staticmethod
    def _safe_float(value):
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _clean_feature_name(name):
        """
        Make sklearn-generated feature names easier to read.

        Examples:
        num__past_return_rate -> past return rate
        cat__payment_method_COD -> payment method COD
        """

        if "__" in name:
            name = name.split("__", 1)[1]

        return name.replace("_", " ")