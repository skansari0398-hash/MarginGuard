from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd


class DeviceIntelligence:
    """
    Device-linked risk intelligence for MarginGuard.

    This module does NOT make a fraud determination.

    It identifies relationships between:
        device -> customer accounts -> historical outcomes

    The resulting information is used as risk evidence and can later
    be consumed by the seller policy engine.
    """

    DEVICE_COLUMN = "device_fingerprint_id"
    ACCOUNT_COLUMN = "customer_account_id"

    def analyze_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich an order dataframe with device-level intelligence.

        Required for device analysis:
            device_fingerprint_id
            customer_account_id

        Optional historical outcome columns:
            returned
            is_returned
            return_status
            rto
            is_rto
            rto_status

        If device/account columns are unavailable, the dataframe is
        returned unchanged with safe default values.
        """

        result = df.copy()

        # ---------------------------------------------------------
        # Safe defaults
        # ---------------------------------------------------------

        result["device_account_count"] = 0
        result["device_previous_returns"] = 0
        result["device_previous_rtos"] = 0

        result["device_multi_account_flag"] = False
        result["device_risk_signal"] = "NONE"

        # ---------------------------------------------------------
        # Device intelligence requires both identifiers
        # ---------------------------------------------------------

        if (
            self.DEVICE_COLUMN not in result.columns
            or self.ACCOUNT_COLUMN not in result.columns
        ):
            return result

        # Normalize identifiers
        result[self.DEVICE_COLUMN] = (
            result[self.DEVICE_COLUMN]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        result[self.ACCOUNT_COLUMN] = (
            result[self.ACCOUNT_COLUMN]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # ---------------------------------------------------------
        # Number of distinct accounts associated with each device
        # ---------------------------------------------------------

        valid_device = result[self.DEVICE_COLUMN] != ""

        account_counts = (
            result.loc[valid_device]
            .groupby(self.DEVICE_COLUMN)[self.ACCOUNT_COLUMN]
            .apply(
                lambda values: len(
                    {
                        value
                        for value in values
                        if str(value).strip()
                    }
                )
            )
        )

        result["device_account_count"] = (
            result[self.DEVICE_COLUMN]
            .map(account_counts)
            .fillna(0)
            .astype(int)
        )

        # ---------------------------------------------------------
        # Historical return count
        # ---------------------------------------------------------

        return_mask = self._build_return_mask(result)

        previous_returns = (
            result.loc[return_mask & valid_device]
            .groupby(self.DEVICE_COLUMN)
            .size()
        )

        result["device_previous_returns"] = (
            result[self.DEVICE_COLUMN]
            .map(previous_returns)
            .fillna(0)
            .astype(int)
        )

        # ---------------------------------------------------------
        # Historical RTO count
        # ---------------------------------------------------------

        rto_mask = self._build_rto_mask(result)

        previous_rtos = (
            result.loc[rto_mask & valid_device]
            .groupby(self.DEVICE_COLUMN)
            .size()
        )

        result["device_previous_rtos"] = (
            result[self.DEVICE_COLUMN]
            .map(previous_rtos)
            .fillna(0)
            .astype(int)
        )

        # ---------------------------------------------------------
        # Multi-account flag
        # ---------------------------------------------------------

        result["device_multi_account_flag"] = (
            result["device_account_count"] >= 3
        )

        # ---------------------------------------------------------
        # Risk signal
        # ---------------------------------------------------------

        result["device_risk_signal"] = result.apply(
            self._classify_device_signal,
            axis=1,
        )

        return result

    def analyze_order(
        self,
        order: Dict[str, Any],
        historical_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Analyze one order against historical device/account data.

        If historical_df is supplied, device relationships are calculated
        from that dataframe.
        """

        device_id = str(
            order.get(self.DEVICE_COLUMN, "")
        ).strip()

        account_id = str(
            order.get(self.ACCOUNT_COLUMN, "")
        ).strip()

        # No device information available
        if not device_id:
            return self._empty_result()

        if historical_df is None:
            return {
                "device_fingerprint_id": device_id,
                "device_account_count": 0,
                "device_previous_returns": 0,
                "device_previous_rtos": 0,
                "device_multi_account_flag": False,
                "device_risk_signal": "UNAVAILABLE",
            }

        enriched = self.analyze_dataset(historical_df)

        matching = enriched[
            enriched[self.DEVICE_COLUMN].astype(str).str.strip()
            == device_id
        ].copy()

        # Exclude the current account from the linked-account count
        accounts = {
            str(value).strip()
            for value in matching[self.ACCOUNT_COLUMN]
            if str(value).strip()
        }

        if account_id:
            accounts.add(account_id)

        return {
            "device_fingerprint_id": device_id,
            "device_account_count": len(accounts),
            "device_previous_returns": int(
                matching["device_previous_returns"].max()
                if not matching.empty
                else 0
            ),
            "device_previous_rtos": int(
                matching["device_previous_rtos"].max()
                if not matching.empty
                else 0
            ),
            "device_multi_account_flag": len(accounts) >= 3,
            "device_risk_signal": self._classify_counts(
                len(accounts),
                int(
                    matching["device_previous_returns"].max()
                    if not matching.empty
                    else 0
                ),
                int(
                    matching["device_previous_rtos"].max()
                    if not matching.empty
                    else 0
                ),
            ),
        }

    # =============================================================
    # OUTCOME DETECTION
    # =============================================================

    @staticmethod
    def _build_return_mask(df: pd.DataFrame) -> pd.Series:
        """
        Detect historical returns using whichever outcome column
        exists in the merchant dataset.
        """

        mask = pd.Series(False, index=df.index)

        candidates = [
            "returned",
            "is_returned",
            "return_status",
            "return_outcome",
            "returned_flag",
        ]

        for column in candidates:
            if column not in df.columns:
                continue

            values = df[column].astype(str).str.lower().str.strip()

            mask = mask | values.isin(
                {
                    "1",
                    "true",
                    "yes",
                    "returned",
                    "return",
                    "return_requested",
                    "completed_return",
                }
            )

        return mask

    @staticmethod
    def _build_rto_mask(df: pd.DataFrame) -> pd.Series:
        """
        Detect historical RTO outcomes using whichever outcome column
        exists in the merchant dataset.
        """

        mask = pd.Series(False, index=df.index)

        candidates = [
            "rto",
            "is_rto",
            "rto_status",
            "rto_outcome",
            "rto_flag",
        ]

        for column in candidates:
            if column not in df.columns:
                continue

            values = df[column].astype(str).str.lower().str.strip()

            mask = mask | values.isin(
                {
                    "1",
                    "true",
                    "yes",
                    "rto",
                    "returned_to_origin",
                }
            )

        return mask

    # =============================================================
    # RISK CLASSIFICATION
    # =============================================================

    @staticmethod
    def _classify_device_signal(row) -> str:
        return DeviceIntelligence._classify_counts(
            int(row.get("device_account_count", 0)),
            int(row.get("device_previous_returns", 0)),
            int(row.get("device_previous_rtos", 0)),
        )

    @staticmethod
    def _classify_counts(
        account_count: int,
        previous_returns: int,
        previous_rtos: int,
    ) -> str:

        # Strongest signal:
        # multiple accounts + historical adverse outcomes
        if (
            account_count >= 3
            and (previous_returns >= 2 or previous_rtos >= 1)
        ):
            return "ELEVATED"

        if account_count >= 3:
            return "MULTI_ACCOUNT"

        if previous_returns >= 2 or previous_rtos >= 1:
            return "HISTORICAL_ACTIVITY"

        if account_count == 2:
            return "SHARED_DEVICE"

        return "NONE"

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        return {
            "device_fingerprint_id": None,
            "device_account_count": 0,
            "device_previous_returns": 0,
            "device_previous_rtos": 0,
            "device_multi_account_flag": False,
            "device_risk_signal": "UNAVAILABLE",
        }