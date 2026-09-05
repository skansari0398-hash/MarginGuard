class InterventionEngine:
    """
    Cost-sensitive intervention engine for MarginGuard.

    Important design principle:
    - ML return risk represents post-delivery customer return risk.
    - RTO risk is estimated separately because COD confirmation
      primarily affects pre-dispatch non-acceptance / RTO risk.
    - Interventions do not magically make a risky customer safe.
      They change the expected economic outcome by screening or
      controlling the order before avoidable fulfillment costs occur.
    """

    # ============================================================
    # COST ESTIMATION
    # ============================================================

    def estimate_return_cost(self, order):
        """
        Estimated merchant loss when a delivered order is returned.

        Components:
        - Forward / logistics handling
        - Reverse shipping
        - Restocking
        - Inventory / margin leakage
        """

        order_value = float(order.get("order_value", 0))

        shipping_cost = 70 + (0.0008 * order_value)
        restocking_cost = 25 + (0.015 * order_value)
        inventory_loss = 0.10 * order_value

        return (
            shipping_cost
            + restocking_cost
            + inventory_loss
        )

    def estimate_rto_cost(self, order):
        """
        Estimated merchant loss when a COD order fails delivery
        because the customer does not accept / receive it.

        This is intentionally separate from post-delivery return cost.
        """

        order_value = float(order.get("order_value", 0))

        forward_shipping = 55 + (0.0005 * order_value)
        reverse_shipping = 60 + (0.0007 * order_value)
        handling_cost = 20

        return (
            forward_shipping
            + reverse_shipping
            + handling_cost
        )

    # ============================================================
    # RTO RISK ESTIMATION
    # ============================================================

    def estimate_rto_risk(self, order):
        """
        Estimate pre-dispatch RTO / non-acceptance risk.

        This is deliberately NOT presented as another ML prediction.
        It is an interpretable operational risk estimate based on
        observable order history and COD characteristics.

        In production, this component can later be replaced by a
        separately trained RTO model using historical RTO outcomes.
        """

        past_rto_rate = float(
            order.get("past_rto_rate", 0)
        )

        delivery_distance = float(
            order.get("delivery_distance_km", 0)
        )

        new_device = int(
            order.get("new_device", 0)
        )

        payment_method = str(
            order.get("payment_method", "")
        ).upper()

        is_cod = payment_method == "COD"

        # Normalize distance contribution.
        # 300 km is treated as a high-distance reference point.
        distance_factor = min(
            max(delivery_distance / 300.0, 0.0),
            1.0
        )

        # Interpretable operational estimate.
        rto_risk = (
            0.55 * past_rto_rate
            + 0.25 * float(is_cod)
            + 0.15 * distance_factor
            + 0.05 * float(new_device)
        )

        return min(
            max(rto_risk, 0.01),
            0.95
        )

    # ============================================================
    # INTERVENTION EFFECTIVENESS
    # ============================================================

    def get_intervention_effectiveness(self, order):
        """
        Demo-stage intervention effectiveness assumptions.

        These are NOT claimed to be measured historical treatment
        effects. They represent configurable assumptions for the
        cost-sensitive decision simulation.

        Production version:
        estimate these from historical intervention outcomes or
        controlled / quasi-experimental evaluation.
        """

        past_return_rate = float(
            order.get("past_return_rate", 0)
        )

        past_rto_rate = float(
            order.get("past_rto_rate", 0)
        )

        new_device = int(
            order.get("new_device", 0)
        )

        payment_method = str(
            order.get("payment_method", "")
        ).upper()

        is_cod = payment_method == "COD"

        # --------------------------------------------------------
        # Customer verification
        # Primarily addresses return / order-intent risk.
        # --------------------------------------------------------

        verification_effectiveness = min(
            max(
                0.15
                + 0.15 * past_return_rate
                + 0.10 * new_device,
                0.05
            ),
            0.45
        )

        # --------------------------------------------------------
        # COD confirmation
        # Primarily addresses RTO / non-acceptance risk.
        # --------------------------------------------------------

        cod_confirmation_effectiveness = min(
            max(
                0.20
                + 0.20 * past_rto_rate
                + 0.10 * float(is_cod),
                0.05
            ),
            0.50
        )

        # --------------------------------------------------------
        # Manual review
        # Broadest control for high-risk cases.
        # --------------------------------------------------------

        manual_review_effectiveness = min(
            max(
                0.30
                + 0.20 * past_return_rate
                + 0.15 * past_rto_rate,
                0.10
            ),
            0.65
        )

        return {
            "VERIFY": verification_effectiveness,
            "COD_CONFIRMATION": cod_confirmation_effectiveness,
            "MANUAL_REVIEW": manual_review_effectiveness
        }

    # ============================================================
    # EXPECTED LOSS CALCULATION
    # ============================================================

    def calculate_expected_losses(self, order, return_risk):
        """
        Calculate expected merchant loss under each intervention.

        The calculation separates:

        1. Post-delivery return loss
        2. Pre-dispatch RTO loss

        COD confirmation only reduces the RTO component.

        This prevents the incorrect assumption that a phone
        confirmation magically reduces the probability of a
        product being returned after delivery.
        """

        order_value = float(
            order.get("order_value", 0)
        )

        gross_margin = float(
            order.get("gross_margin", 0)
        )

        payment_method = str(
            order.get("payment_method", "")
        ).upper()

        is_cod = payment_method == "COD"

        return_cost = self.estimate_return_cost(order)
        rto_cost = self.estimate_rto_cost(order)

        rto_risk = self.estimate_rto_risk(order)

        effectiveness = self.get_intervention_effectiveness(
            order
        )

        # ========================================================
        # INTERVENTION COSTS
        # ========================================================

        verification_cost = 18
        cod_confirmation_cost = 7
        manual_review_cost = 65

        # Small abandonment / friction cost.
        verification_abandonment = 0.025
        manual_review_abandonment = 0.050

        # ========================================================
        # BASELINE
        # ========================================================

        # Post-delivery return exposure.
        expected_return_loss = (
            return_risk * return_cost
        )

        # RTO exposure exists primarily for COD orders.
        expected_rto_loss = (
            rto_risk * rto_cost
            if is_cod
            else 0
        )

        no_action = (
            expected_return_loss
            + expected_rto_loss
        )

        # ========================================================
        # VERIFY
        # ========================================================

        verify_return_loss = (
            return_risk
            * (
                1
                - effectiveness["VERIFY"]
            )
            * return_cost
        )

        verify_rto_loss = expected_rto_loss

        verify = (
            verification_cost
            + verify_return_loss
            + verify_rto_loss
            + (
                verification_abandonment
                * gross_margin
            )
        )

        # ========================================================
        # COD CONFIRMATION
        # ========================================================

        if is_cod:

            # IMPORTANT:
            # COD confirmation affects RTO risk,
            # NOT post-delivery return risk.

            remaining_rto_risk = (
                rto_risk
                * (
                    1
                    - effectiveness[
                        "COD_CONFIRMATION"
                    ]
                )
            )

            cod_confirmation = (
                cod_confirmation_cost
                + expected_return_loss
                + (
                    remaining_rto_risk
                    * rto_cost
                )
            )

        else:
            # COD confirmation is not applicable to prepaid orders.
            cod_confirmation = float("inf")

        # ========================================================
        # MANUAL REVIEW
        # ========================================================

        manual_return_loss = (
            return_risk
            * (
                1
                - effectiveness["MANUAL_REVIEW"]
            )
            * return_cost
        )

        manual_rto_loss = (
            rto_risk
            * (
                1
                - effectiveness["MANUAL_REVIEW"]
            )
            * rto_cost
            if is_cod
            else 0
        )

        manual_review = (
            manual_review_cost
            + manual_return_loss
            + manual_rto_loss
            + (
                manual_review_abandonment
                * gross_margin
            )
        )

        return {
            "NO_ACTION": no_action,
            "VERIFY": verify,
            "COD_CONFIRMATION": cod_confirmation,
            "MANUAL_REVIEW": manual_review
        }

    # ============================================================
    # RECOMMENDATION
    # ============================================================

    def recommend(self, order, risk):
        """
        Select the intervention with the lowest expected loss.
        """

        losses = self.calculate_expected_losses(
            order,
            risk
        )

        recommended_action = min(
            losses,
            key=losses.get
        )

        return {
            "risk": risk,

            "rto_risk": self.estimate_rto_risk(
                order
            ),

            "recommended_action":
                recommended_action,

            "expected_losses":
                losses,

            "expected_loss":
                losses[recommended_action],

            "return_cost":
                self.estimate_return_cost(
                    order
                ),

            "rto_cost":
                self.estimate_rto_cost(
                    order
                )
        }