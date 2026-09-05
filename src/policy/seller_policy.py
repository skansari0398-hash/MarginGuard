from copy import deepcopy


class SellerPolicy:
    """
    Merchant-configurable policy layer for MarginGuard.

    This layer does NOT change the ML model.
    It uses ML risk + device evidence to determine
    whether a merchant policy should require a
    particular intervention.

    Available interventions:
        - NO_ACTION
        - VERIFY
        - COD_CONFIRMATION
        - MANUAL_REVIEW
    """

    DEFAULT_POLICY = {
        # Risk thresholds
        "high_risk_threshold": 0.80,
        "critical_risk_threshold": 0.90,

        # Device evidence threshold
        "multi_account_threshold": 3,

        # Historical behavior threshold
        "high_return_history_threshold": 0.60,

        # Policy controls
        "high_risk_verification": True,
        "critical_risk_cod_confirmation": True,
        "multi_account_verification": True,
        "multi_account_cod_confirmation": True,
        "combined_signal_manual_review": True,
    }

    def __init__(self):
        self.policy = deepcopy(self.DEFAULT_POLICY)

    # ============================================================
    # POLICY CONFIGURATION
    # ============================================================

    def get_policy(self):
        """
        Return a copy of the active merchant policy.
        """
        return deepcopy(self.policy)

    def update_policy(self, updates):
        """
        Update only recognized policy fields.

        Example:
            {
                "high_risk_threshold": 0.85,
                "multi_account_threshold": 4,
                "combined_signal_manual_review": True
            }
        """

        for key, value in updates.items():

            if key not in self.DEFAULT_POLICY:
                raise ValueError(
                    f"Unknown policy field: {key}"
                )

            self._validate_value(key, value)

            self.policy[key] = value

        return self.get_policy()

    # ============================================================
    # POLICY EVALUATION
    # ============================================================

    def evaluate(self, order, risk):
        """
        Evaluate merchant policy against one order.

        Returns:
            {
                "policy_triggered": bool,
                "forced_action": str | None,
                "reason": str | None,
                "signals": [...]
            }
        """

        multi_account_count = self._safe_int(
            order.get(
                "device_account_count",
                0
            )
        )

        multi_account_flag = (
            order.get(
                "device_multi_account_flag",
                False
            )
        )

        past_return_rate = self._safe_float(
            order.get(
                "past_return_rate",
                0
            )
        )

        payment_method = str(
            order.get(
                "payment_method",
                ""
            )
        ).upper()

        is_multi_account = (
            multi_account_flag
            or
            multi_account_count
            >= self.policy[
                "multi_account_threshold"
            ]
        )

        is_high_risk = (
            risk >= self.policy[
                "high_risk_threshold"
            ]
        )

        is_critical_risk = (
            risk >= self.policy[
                "critical_risk_threshold"
            ]
        )

        has_high_return_history = (
            past_return_rate
            >= self.policy[
                "high_return_history_threshold"
            ]
        )

        signals = []

        # --------------------------------------------------------
        # Device signal
        # --------------------------------------------------------

        if is_multi_account:

            signals.append({
                "signal": "MULTI_ACCOUNT_DEVICE",
                "value": multi_account_count,
                "threshold":
                    self.policy[
                        "multi_account_threshold"
                    ],
                "severity": "HIGH"
            })

        # --------------------------------------------------------
        # Return-history signal
        # --------------------------------------------------------

        if has_high_return_history:

            signals.append({
                "signal": "HIGH_RETURN_HISTORY",
                "value":
                    round(
                        past_return_rate,
                        4
                    ),
                "threshold":
                    self.policy[
                        "high_return_history_threshold"
                    ],
                "severity": "HIGH"
            })

        # --------------------------------------------------------
        # Risk signal
        # --------------------------------------------------------

        if is_critical_risk:

            signals.append({
                "signal": "CRITICAL_RISK",
                "value": round(
                    risk,
                    4
                ),
                "threshold":
                    self.policy[
                        "critical_risk_threshold"
                    ],
                "severity": "CRITICAL"
            })

        elif is_high_risk:

            signals.append({
                "signal": "HIGH_RISK",
                "value": round(
                    risk,
                    4
                ),
                "threshold":
                    self.policy[
                        "high_risk_threshold"
                    ],
                "severity": "HIGH"
            })

        # ========================================================
        # POLICY PRIORITY
        # ========================================================

        # Priority 1:
        # High return history + multi-account device
        # is the strongest combined evidence.
        if (
            is_multi_account
            and has_high_return_history
            and self.policy[
                "combined_signal_manual_review"
            ]
        ):

            return {
                "policy_triggered": True,
                "forced_action": "MANUAL_REVIEW",
                "reason":
                    "Multi-account device combined with high historical return rate.",
                "signals": signals
            }

        # Priority 2:
        # Multi-account device + COD
        if (
            is_multi_account
            and payment_method == "COD"
            and self.policy[
                "multi_account_cod_confirmation"
            ]
        ):

            return {
                "policy_triggered": True,
                "forced_action": "COD_CONFIRMATION",
                "reason":
                    "COD order is associated with a multi-account device.",
                "signals": signals
            }

        # Priority 3:
        # Multi-account device
        if (
            is_multi_account
            and self.policy[
                "multi_account_verification"
            ]
        ):

            return {
                "policy_triggered": True,
                "forced_action": "VERIFY",
                "reason":
                    "Device is associated with multiple customer accounts.",
                "signals": signals
            }

        # Priority 4:
        # Critical COD order
        if (
            is_critical_risk
            and payment_method == "COD"
            and self.policy[
                "critical_risk_cod_confirmation"
            ]
        ):

            return {
                "policy_triggered": True,
                "forced_action": "COD_CONFIRMATION",
                "reason":
                    "Critical return risk on a COD order.",
                "signals": signals
            }

        # Priority 5:
        # General high-risk verification
        if (
            is_high_risk
            and self.policy[
                "high_risk_verification"
            ]
        ):

            return {
                "policy_triggered": True,
                "forced_action": "VERIFY",
                "reason":
                    "Return risk exceeds the merchant's high-risk threshold.",
                "signals": signals
            }

        # No policy override
        return {
            "policy_triggered": False,
            "forced_action": None,
            "reason": None,
            "signals": signals
        }

    # ============================================================
    # VALIDATION
    # ============================================================

    def _validate_value(self, key, value):

        threshold_fields = {
            "high_risk_threshold",
            "critical_risk_threshold",
            "high_return_history_threshold"
        }

        integer_fields = {
            "multi_account_threshold"
        }

        boolean_fields = {
            "high_risk_verification",
            "critical_risk_cod_confirmation",
            "multi_account_verification",
            "multi_account_cod_confirmation",
            "combined_signal_manual_review"
        }

        if key in threshold_fields:

            if not isinstance(
                value,
                (int, float)
            ):
                raise ValueError(
                    f"{key} must be numeric."
                )

            if not 0 <= float(value) <= 1:

                raise ValueError(
                    f"{key} must be between 0 and 1."
                )

        elif key in integer_fields:

            if not isinstance(
                value,
                int
            ):
                raise ValueError(
                    f"{key} must be an integer."
                )

            if value < 2:

                raise ValueError(
                    f"{key} must be at least 2."
                )

        elif key in boolean_fields:

            if not isinstance(
                value,
                bool
            ):
                raise ValueError(
                    f"{key} must be true or false."
                )

    # ============================================================
    # SAFE CONVERSION HELPERS
    # ============================================================

    @staticmethod
    def _safe_float(value):

        try:
            return float(value)

        except (
            TypeError,
            ValueError
        ):
            return 0.0

    @staticmethod
    def _safe_int(value):

        try:
            return int(value)

        except (
            TypeError,
            ValueError
        ):
            return 0