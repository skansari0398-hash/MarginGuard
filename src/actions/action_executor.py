from datetime import datetime, timezone
from uuid import uuid4
from typing import Dict, List, Any


class ActionExecutor:
    """
    MarginGuard Action Execution Layer.

    This is a demo-safe execution layer.

    It does NOT silently modify external merchant systems.
    Instead, it records and simulates the operational action so
    the complete workflow can be demonstrated:

        Risk -> Policy -> Action -> Result -> Audit

    External integrations such as SMS, WhatsApp, Shopify, or
    payment-provider controls can later be implemented behind
    connector classes.
    """

    ALLOWED_ACTIONS = {
        "SEND_CUSTOMER_VERIFICATION",
        "DISABLE_COD",
        "SEND_TO_MANUAL_REVIEW",
        "RELEASE_ORDER",
    }

    ACTION_LABELS = {
        "SEND_CUSTOMER_VERIFICATION": "Customer Verification",
        "DISABLE_COD": "Disable COD",
        "SEND_TO_MANUAL_REVIEW": "Manual Review",
        "RELEASE_ORDER": "Release Order",
    }

    def __init__(self):
        # Demo state.
        # In production this should live in a database.
        self.action_history: List[Dict[str, Any]] = []

        # Current operational state of each order.
        self.order_states: Dict[str, Dict[str, Any]] = {}

        # Internal manual-review queue.
        self.manual_review_queue: List[str] = []

    # ============================================================
    # ORDER STATE
    # ============================================================

    def _get_order_state(self, order: Dict[str, Any]) -> Dict[str, Any]:
        order_id = str(order.get("order_id", "UNKNOWN"))

        if order_id not in self.order_states:

            payment_method = str(
                order.get("payment_method", "")
            ).upper()

            self.order_states[order_id] = {
                "order_id": order_id,
                "status": "PENDING",
                "cod_enabled": payment_method == "COD",
                "customer_verification": "NOT_REQUESTED",
                "manual_review": False,
            }

        return self.order_states[order_id]

    # ============================================================
    # ACTION EXECUTION
    # ============================================================

    def execute(
        self,
        order: Dict[str, Any],
        action: str,
        risk: float = 0.0,
        final_control: str = "NO_ACTION",
        source: str = "MERCHANT",
    ) -> Dict[str, Any]:

        action = str(action).upper().strip()

        if action not in self.ALLOWED_ACTIONS:
            raise ValueError(
                f"Unsupported action: {action}"
            )

        order_id = str(
            order.get(
                "order_id",
                "UNKNOWN"
            )
        )

        state = self._get_order_state(order)

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        action_id = (
            f"ACT-{uuid4().hex[:10].upper()}"
        )

        # --------------------------------------------------------
        # CUSTOMER VERIFICATION
        # --------------------------------------------------------

        if action == "SEND_CUSTOMER_VERIFICATION":

            state["customer_verification"] = (
                "REQUESTED"
            )

            state["status"] = "AWAITING_VERIFICATION"

            result = {
                "status": "SIMULATED_SENT",
                "message": (
                    "Customer verification request "
                    "created successfully."
                ),
                "channel": "SIMULATED_COMMUNICATION",
                "message_preview": (
                    "MarginGuard verification: "
                    "Please confirm your order before "
                    "we process your shipment."
                ),
            }

        # --------------------------------------------------------
        # DISABLE COD
        # --------------------------------------------------------

        elif action == "DISABLE_COD":

            payment_method = str(
                order.get(
                    "payment_method",
                    ""
                )
            ).upper()

            if payment_method != "COD":
                raise ValueError(
                    "COD cannot be disabled because "
                    "this order is not a COD order."
                )

            state["cod_enabled"] = False
            state["status"] = "COD_DISABLED"

            result = {
                "status": "APPLIED",
                "message": (
                    "COD control applied to this order."
                ),
                "external_sync": "SIMULATED",
            }

        # --------------------------------------------------------
        # MANUAL REVIEW
        # --------------------------------------------------------

        elif action == "SEND_TO_MANUAL_REVIEW":

            state["manual_review"] = True
            state["status"] = "MANUAL_REVIEW"

            if order_id not in self.manual_review_queue:
                self.manual_review_queue.append(
                    order_id
                )

            result = {
                "status": "QUEUED",
                "message": (
                    "Order added to the merchant "
                    "manual-review queue."
                ),
                "queue_position": (
                    self.manual_review_queue.index(
                        order_id
                    ) + 1
                ),
            }

        # --------------------------------------------------------
        # RELEASE ORDER
        # --------------------------------------------------------

        elif action == "RELEASE_ORDER":

            state["status"] = "RELEASED"

            # If the order was previously in review,
            # remove it from the queue.
            if order_id in self.manual_review_queue:
                self.manual_review_queue.remove(
                    order_id
                )

            result = {
                "status": "RELEASED",
                "message": (
                    "Order released for normal fulfillment."
                ),
            }

        else:
            raise ValueError(
                f"Unsupported action: {action}"
            )

        # ========================================================
        # AUDIT RECORD
        # ========================================================

        audit_record = {
            "action_id": action_id,
            "order_id": order_id,
            "action": action,
            "action_label": self.ACTION_LABELS[action],
            "source": source,
            "risk": round(
                float(risk),
                4
            ),
            "risk_percentage": (
                f"{float(risk):.2%}"
            ),
            "final_control": final_control,
            "status": result["status"],
            "timestamp": timestamp,
            "result": result,
            "order_state": dict(state),
        }

        self.action_history.append(
            audit_record
        )

        return audit_record

    # ============================================================
    # ACTION HISTORY
    # ============================================================

    def get_order_history(
        self,
        order_id: str
    ) -> List[Dict[str, Any]]:

        order_id = str(order_id)

        return [
            record
            for record in self.action_history
            if record["order_id"] == order_id
        ]

    # ============================================================
    # ALL ACTIONS
    # ============================================================

    def get_history(
        self,
        limit: int = 100
    ) -> List[Dict[str, Any]]:

        limit = min(
            max(int(limit), 1),
            500
        )

        return self.action_history[-limit:][::-1]

    # ============================================================
    # CURRENT ORDER STATE
    # ============================================================

    def get_order_state(
        self,
        order_id: str
    ) -> Dict[str, Any]:

        order_id = str(order_id)

        if order_id not in self.order_states:
            return {
                "order_id": order_id,
                "status": "PENDING",
                "cod_enabled": None,
                "customer_verification": "NOT_REQUESTED",
                "manual_review": False,
            }

        return dict(
            self.order_states[order_id]
        )

    # ============================================================
    # MANUAL REVIEW QUEUE
    # ============================================================

    def get_manual_review_queue(
        self
    ) -> List[str]:

        return list(
            self.manual_review_queue
        )