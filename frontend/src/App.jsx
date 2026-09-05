import { useEffect, useState } from "react";import "./App.css";
import Store from "./Store";
const API_URL = "http://127.0.0.1:8000";

function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [highRiskOrders, setHighRiskOrders] = useState([]);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [loading, setLoading] = useState(false);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionResult, setActionResult] = useState(null);
  const [actionHistory, setActionHistory] = useState([]);
  const [webhookLoading, setWebhookLoading] = useState(false);
  const [webhookResult, setWebhookResult] = useState(null);
  const [showStore, setShowStore] = useState(false);
  const [liveOrders, setLiveOrders] = useState([]);
  const [liveOrderStats, setLiveOrderStats] = useState({
    total: 0,
    risky: 0,
    clear: 0,
  });
  const [liveOrdersLoading, setLiveOrdersLoading] = useState(false);


    // ============================================================
  // LIVE ORDER QUEUE
  // ============================================================

  const fetchLiveOrders = async (
    showLoading = false
  ) => {
    if (showLoading) {
      setLiveOrdersLoading(true);
    }

    try {
      // Load active live orders.
      const ordersResponse = await fetch(
        `${API_URL}/orders/live?limit=100`
      );

      if (!ordersResponse.ok) {
        throw new Error(
          "Could not load live orders."
        );
      }

      const ordersData =
        await ordersResponse.json();

      const orders =
        ordersData.orders || [];

      // Load merchant action history.
      // Orders that already received a merchant
      // control are considered resolved and should
      // no longer appear in the active queue.
      let resolvedOrderIds = new Set();

      try {
        const actionsResponse = await fetch(
          `${API_URL}/actions?limit=500`
        );

        if (actionsResponse.ok) {
          const actionsData =
            await actionsResponse.json();

          const actions =
            actionsData.actions || [];

          resolvedOrderIds = new Set(
            actions
              .map((action) =>
                String(
                  action.order_id || ""
                ).trim()
              )
              .filter(Boolean)
          );
        }
      } catch (error) {
        console.warn(
          "Could not load action history:",
          error
        );
      }

      // Keep only unresolved live orders.
      const activeOrders =
        orders.filter(
          (order) =>
            !resolvedOrderIds.has(
              String(
                order.order_id || ""
              ).trim()
            )
        );

      // Recalculate queue statistics from
      // the currently active orders.
      const riskyOrders =
        activeOrders.filter((order) => {
          const risk = Number(
            order.predicted_return_probability || 0
          );

          return risk >= 0.50;
        });

      const clearOrders =
        activeOrders.filter((order) => {
          const risk = Number(
            order.predicted_return_probability || 0
          );

          return risk < 0.50;
        });

      setLiveOrders(activeOrders);

      setLiveOrderStats({
        total: activeOrders.length,
        risky: riskyOrders.length,
        clear: clearOrders.length,
      });
    } catch (error) {
      console.error(
        "Live orders refresh failed:",
        error
      );
    } finally {
      if (showLoading) {
        setLiveOrdersLoading(false);
      }
    }
  };

    useEffect(() => {

    fetchLiveOrders(true);

    const interval = setInterval(() => {
      fetchLiveOrders(false);
    }, 3000);

    return () => {
      clearInterval(interval);
    };

  }, []);

  
  // ============================================================
  // BATCH ANALYSIS
  // ============================================================

  const analyzeBatch = async () => {
    if (!file) {
      alert("Please select a CSV file.");
      return;
    }

    setLoading(true);
    setResult(null);
    setHighRiskOrders([]);
    setSelectedOrder(null);
    setActionResult(null);
    setActionHistory([]);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_URL}/batch-predict`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);

        throw new Error(
          errorData?.detail || "Batch analysis failed."
        );
      }

      const data = await response.json();

      setResult(data);

      const highRiskResponse = await fetch(
        `${API_URL}/orders/high-risk?limit=20`
      );

      if (!highRiskResponse.ok) {
        const errorData = await highRiskResponse
          .json()
          .catch(() => null);

        throw new Error(
          errorData?.detail ||
            "Could not load high-risk orders."
        );
      }

      const highRiskData = await highRiskResponse.json();

      setHighRiskOrders(highRiskData.orders || []);
    } catch (error) {
      alert(error.message);
    } finally {
      setLoading(false);
    }
  };
    // ============================================================
    // LIVE WEBHOOK / ORDER INGESTION
    // ============================================================

    const simulateWebhookOrder = async () => {
      setWebhookLoading(true);
      setWebhookResult(null);

      const demoOrder = {
        order_id: `LIVE-${Date.now()}`,

        customer_id: "35037",
        customer_account_id: "35037",
        device_fingerprint_id: "DEV0103487",

        product_id: "PROD-1003",
        product_category: "Fashion",
        product_price: 1899,
        product_rating: 4.1,

        discount_percent: 36.0,

        payment_method: "COD",
        shipping_method: "Standard",

        device_type: "Android",
        new_device: true,

        is_first_order: false,
        used_coupon: true,

        session_length_minutes: 120,
        num_product_views: 8,

        estimated_delivery_days: 6,
        delivery_distance_km: 245,

        order_value: 1899,
        gross_margin: 620,
      };

      try {
        const response = await fetch(
          `${API_URL}/webhooks/order`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(demoOrder),
          }
        );

        const data = await response.json().catch(() => null);

        if (!response.ok) {
          throw new Error(
            data?.detail ||
              "Webhook order processing failed."
          );
        }

        setWebhookResult(data);
      } catch (error) {
        setWebhookResult({
          success: false,
          status: "FAILED",
          message: error.message,
        });
      } finally {
        setWebhookLoading(false);
      }
    };
  

    
  // ============================================================
  // ORDER DETAILS
  // ============================================================
  const loadActionHistory = async (orderId) => {
    try {
      const response = await fetch(
        `${API_URL}/orders/${encodeURIComponent(orderId)}/actions`
      );

      if (!response.ok) return;

      const data = await response.json();

      setActionHistory(data.actions || []);
    } catch {}
  };

  const openOrderDetails = async (orderId) => {
    setDetailsLoading(true);
    setSelectedOrder(null);
    setActionResult(null);
    setActionHistory([]);

    try {
      const response = await fetch(
        `${API_URL}/orders/high-risk/${encodeURIComponent(
          orderId
        )}`
      );

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => null);

        throw new Error(
          errorData?.detail ||
            "Could not load order details."
        );
      }

      const data = await response.json();

      setSelectedOrder(data);
      await loadActionHistory(orderId);
    } catch (error) {
      alert(error.message);
    } finally {
      setDetailsLoading(false);
    }
  };

  const executeOrderAction = async (action) => {
  if (!selectedOrder?.order?.order_id) return;

  const orderId = selectedOrder.order.order_id;

  if (action === "RELEASE_ORDER") {
    const confirmed = window.confirm(
      "Release this order and bypass the current risk control?"
    );

    if (!confirmed) return;
  }

  setActionLoading(true);
  setActionResult(null);

  try {
    const response = await fetch(
      `${API_URL}/orders/${encodeURIComponent(orderId)}/actions`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          action,
          merchant_approved: true,
        }),
      }
    );

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(
        data?.detail || "Could not execute merchant action."
      );
    }

    setActionResult(data);

    await loadActionHistory(orderId);
  } catch (error) {
    setActionResult({
      success: false,
      status: "FAILED",
      message: error.message,
    });
  } finally {
    setActionLoading(false);
  }
};

const closeOrderDetails = () => {
  setSelectedOrder(null);
  setActionResult(null);
  setActionHistory([]);
};

  // ============================================================
  // FORMATTERS
  // ============================================================

  function formatCurrency(value) {
    const number = Number(value);

    if (!Number.isFinite(number)) {
      return "₹0";
    }

    return `₹${number.toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

    function formatPercentage(value, decimals = 2) {
      const number = Number(value);

    if (!Number.isFinite(number)) {
      return "0%";
    }

    return `${(number * 100).toFixed(decimals)}%`;
    };

    const safeValue = (value, fallback) => {
      if (
        value === undefined ||
        value === null ||
        value === "" ||
        (typeof value === "number" && Number.isNaN(value))
      ) {
        return fallback;
      }

      return value;
    };

    // ============================================================
    // ACTION HELPERS
    // ============================================================

  // ============================================================
  // ACTION HELPERS
  // ============================================================

  function getActionTitle(action) {
  switch (action) {
    case "COD_CONFIRMATION":
      return "COD Confirmation Required";

    case "VERIFY":
      return "Customer Verification";

    case "MANUAL_REVIEW":
      return "Manual Review";

    case "NO_ACTION":
      return "No Intervention";

    case "SEND_TO_MANUAL_REVIEW":
      return "Manual Review";

    case "SEND_CUSTOMER_VERIFICATION":
      return "Customer Verification Sent";

    case "DISABLE_COD":
      return "COD Disabled";

    case "RELEASE_ORDER":
      return "Order Released";

    default:
      return action || "No Action";
  }
};

  const getActionDescription = (action) => {
    switch (action) {
      case "COD_CONFIRMATION":
        return "Confirm customer intent before fulfillment. Do not dispatch until confirmed.";

      case "VERIFY":
        return "Verify the customer before dispatch.";

      case "MANUAL_REVIEW":
        return "Route this order for human risk review.";

      case "NO_ACTION":
        return "No additional intervention is economically justified.";
      
      case "SEND_TO_MANUAL_REVIEW":
        return "Route this order to the merchant risk review queue.";

      case "SEND_CUSTOMER_VERIFICATION":
        return "Send a customer verification request before dispatch.";

      case "DISABLE_COD":
        return "Disable cash-on-delivery for this order.";

      case "RELEASE_ORDER":
        return "Release the order and bypass the current risk control.";

      default:
        return "Apply the recommended risk control.";
    }
  };

  const getActionIcon = (action) => {
    switch (action) {
      case "COD_CONFIRMATION":
        return "✓";

      case "VERIFY":
        return "◆";

      case "MANUAL_REVIEW":
        return "!";

      case "NO_ACTION":
        return "—";

      case "SEND_TO_MANUAL_REVIEW":
        return "!";

      case "SEND_CUSTOMER_VERIFICATION":
        return "◆";

      case "DISABLE_COD":
        return "×";

      case "RELEASE_ORDER":
        return "✓";

  
      default:
        return "•";
    }
  };

  const getNextStep = (action) => {
    switch (action) {
      case "COD_CONFIRMATION":
        return "Contact customer and confirm COD order before dispatch.";

      case "VERIFY":
        return "Request customer verification before dispatch.";

      case "MANUAL_REVIEW":
        return "Send order to the merchant risk queue.";

      case "NO_ACTION":
        return "Proceed with normal fulfillment.";

      case "SEND_TO_MANUAL_REVIEW":
        return "Send order to the merchant risk queue.";

      case "SEND_CUSTOMER_VERIFICATION":
        return "Request customer verification before dispatch.";

      case "DISABLE_COD":
        return "Apply the COD restriction before fulfillment.";

      case "RELEASE_ORDER":
        return "Proceed with normal fulfillment after merchant approval.";

      default:
        return "Review recommended control.";
    }
  };

  // ============================================================
  // MODEL EXPLANATION
  // ============================================================

  const getExplanationClass = (direction) => {
    if (direction === "INCREASES_RISK") {
      return "impact high";
    }

    if (direction === "DECREASES_RISK") {
      return "impact low";
    }

    return "impact";
  };

  // ============================================================
  // DEVICE INTELLIGENCE
  // ============================================================

  const getDeviceIntelligence = (orderData) => {
    const order = orderData?.order || {};
    const device = orderData?.device_intelligence || {};

    const cleanValue = (value, fallback = null) => {
      if (
        value === undefined ||
        value === null ||
        value === "" ||
        String(value).trim().toLowerCase() === "nan" ||
        String(value).trim().toLowerCase() === "none" ||
        String(value).trim().toLowerCase() === "null"
      ) {
        return fallback;
      }

      return value;
    };

    const deviceId = cleanValue(
      device.device_fingerprint_id,
      cleanValue(order.device_fingerprint_id, "UNAVAILABLE")
    );

    const linkedAccountsRaw = cleanValue(
      device.device_account_count,
      cleanValue(order.device_account_count, 0)
    );

    const previousReturnsRaw = cleanValue(
      device.device_previous_returns,
      cleanValue(order.device_previous_returns, 0)
    );

    const previousRtosRaw = cleanValue(
      device.device_previous_rtos,
      cleanValue(order.device_previous_rtos, 0)
    );

    const multiAccountRaw = cleanValue(
      device.device_multi_account_flag,
      cleanValue(order.device_multi_account_flag, false)
    );

    const signal = cleanValue(
      device.device_risk_signal,
      cleanValue(order.device_risk_signal, "UNAVAILABLE")
    );

    const linkedAccounts = Number(linkedAccountsRaw);
    const previousReturns = Number(previousReturnsRaw);
    const previousRtos = Number(previousRtosRaw);

    const multiAccount =
      multiAccountRaw === true ||
      multiAccountRaw === 1 ||
      String(multiAccountRaw).toLowerCase() === "true" ||
      String(multiAccountRaw).toLowerCase() === "yes";

    return {
      deviceId,
      linkedAccounts: Number.isFinite(linkedAccounts)
        ? linkedAccounts
        : 0,

      previousReturns: Number.isFinite(previousReturns)
        ? previousReturns
        : 0,

      previousRtos: Number.isFinite(previousRtos)
        ? previousRtos
        : 0,

      multiAccount,

      signal,
    };
  };

  // ============================================================
  // SELLER POLICY ENGINE
  // ============================================================

  const getSellerPolicy = (orderData) => {
    if (!orderData) {
      return null;
    }

    const order = orderData.order || {};

    const risk = Number(
      orderData.risk?.probability ??
        orderData.return_risk ??
        order.predicted_return_probability ??
        0
    );

    const device = getDeviceIntelligence(orderData);

    const returnRate = Number(
      order.past_return_rate || 0
    );

    const rtoRate = Number(
      order.past_rto_rate || 0
    );

    const isCOD =
      String(order.payment_method || "")
        .toUpperCase() === "COD";

    const rules = [];

    // ----------------------------------------------------------
    // RULE 1 — MULTI ACCOUNT DEVICE
    // ----------------------------------------------------------

    if (device.linkedAccounts >= 3) {
      rules.push({
        name: "MULTI_ACCOUNT_DEVICE",
        severity: "HIGH",
        description: `Device linked to ${device.linkedAccounts} customer accounts.`,
        action: "MANUAL_REVIEW",
      });
    }

    // ----------------------------------------------------------
    // RULE 2 — HIGH RETURN HISTORY
    // ----------------------------------------------------------

    if (returnRate >= 0.50) {
      rules.push({
        name: "HIGH_RETURN_HISTORY",
        severity: "HIGH",
        description: `Historical return rate is ${(
          returnRate * 100
        ).toFixed(1)}%.`,
        action: "VERIFY",
      });
    }

    // ----------------------------------------------------------
    // RULE 3 — HIGH RTO HISTORY
    // ----------------------------------------------------------

    if (rtoRate >= 0.20) {
      rules.push({
        name: "HIGH_RTO_HISTORY",
        severity: "MEDIUM",
        description: `Historical RTO rate is ${(
          rtoRate * 100
        ).toFixed(1)}%.`,
        action: isCOD
          ? "COD_CONFIRMATION"
          : "VERIFY",
      });
    }

    // ----------------------------------------------------------
    // RULE 4 — CRITICAL COD RISK
    // ----------------------------------------------------------

    if (risk >= 0.90 && isCOD) {
      rules.push({
        name: "CRITICAL_COD_RISK",
        severity: "CRITICAL",
        description:
          "Critical return probability combined with COD payment.",
        action: "COD_CONFIRMATION",
      });
    }

    // ----------------------------------------------------------
    // RULE 5 — HIGH MODEL RISK
    // ----------------------------------------------------------

    if (risk >= 0.80 && rules.length === 0) {
      rules.push({
        name: "HIGH_MODEL_RISK",
        severity: "HIGH",
        description: `Predicted return probability is ${(
          risk * 100
        ).toFixed(1)}%.`,
        action: isCOD
          ? "COD_CONFIRMATION"
          : "VERIFY",
      });
    }

    // ----------------------------------------------------------
    // NO POLICY TRIGGER
    // ----------------------------------------------------------

    if (rules.length === 0) {
      return {
        triggered: false,
        status: "CLEAR",
        finalAction: "NO_ACTION",
        rules: [],
        explanation:
          "No configured seller policy threshold was triggered.",
      };
    }

    // ----------------------------------------------------------
    // PRIORITY
    // ----------------------------------------------------------

    const priority = {
      MANUAL_REVIEW: 4,
      COD_CONFIRMATION: 3,
      VERIFY: 2,
      NO_ACTION: 1,
    };

    const sortedRules = [...rules].sort(
      (a, b) =>
        (priority[b.action] || 0) -
        (priority[a.action] || 0)
    );

    const finalAction =
      sortedRules[0].action;

    return {
      triggered: true,
      status: "TRIGGERED",
      finalAction,
      rules: sortedRules,
      explanation:
        "One or more seller-defined risk controls were triggered.",
    };
  };

  // ============================================================
  // POLICY SEVERITY CLASS
  // ============================================================

  const getPolicySeverityClass = (severity) => {
    if (severity === "CRITICAL") {
      return "impact high";
    }

    if (severity === "HIGH") {
      return "impact high";
    }

    if (severity === "MEDIUM") {
      return "impact";
    }

    return "impact low";
  };

  const getExecutableAction = (action) => {
  switch (action) {
    case "MANUAL_REVIEW":
      return "SEND_TO_MANUAL_REVIEW";

    case "VERIFY":
      return "SEND_CUSTOMER_VERIFICATION";

    case "COD_CONFIRMATION":
      return "SEND_CUSTOMER_VERIFICATION";

    case "NO_ACTION":
      return "RELEASE_ORDER";

    default:
      return action;
  }
};

const getActionHistoryTitle = (action) => {
  switch (action) {
    case "SEND_TO_MANUAL_REVIEW":
      return "Manual Review";

    case "SEND_CUSTOMER_VERIFICATION":
      return "Customer Verification";

    case "DISABLE_COD":
      return "COD Disabled";

    case "RELEASE_ORDER":
      return "Order Released";

    default:
      return getActionTitle(action);
  }
};

const getActionStatusClass = (status) => {
  const normalized = String(status || "").toUpperCase();

  if (
    normalized.includes("FAIL") ||
    normalized.includes("ERROR")
  ) {
    return "impact high";
  }

  if (
    normalized.includes("QUEUED") ||
    normalized.includes("REQUESTED")
  ) {
    return "impact";
  }

  return "impact low";
};

  // ============================================================
  // RENDER
  // ============================================================

  if (showStore) {
  return (
    <Store
      onBackToDashboard={() =>
        setShowStore(false)
      }
      onOrderProcessed={() => {
        setShowStore(false);
        fetchLiveOrders(false);
      }}
    />
  );
}

  return (
    <div className="app">

      {/* ======================================================
          HEADER
          ====================================================== */}

      <header>
        <p className="eyebrow">
          MARGIN GUARD
        </p>

        <h1>
          Merchant Loss Prevention
        </h1>

        <p className="subtitle">
          AI-powered return risk detection and
          cost-sensitive intervention.
        </p>
      </header>

      <main>

              {/* ====================================================
            LIVE ORDER INTAKE
            ==================================================== */}

        <section
          className="upload-card"
          style={{
            marginBottom: "24px",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              gap: "20px",
              flexWrap: "wrap",
            }}
          >
            <div>
              <p className="eyebrow">
                REAL-TIME ORDER INGESTION
              </p>

              <h2>
                Live Order Intake
              </h2>

              <p>
                MarginGuard can receive an order event through
                a webhook, score it immediately, apply seller
                policy, and return the recommended merchant
                control.
              </p>
            </div>

            <span
              style={{
                padding: "8px 12px",
                borderRadius: "999px",
                background: "#eef6ff",
                border: "1px solid #cfe0f5",
                color: "#0b4ea2",
                fontSize: "11px",
                fontWeight: "700",
                letterSpacing: "1px",
              }}
            >
              WEBHOOK READY
            </span>
          </div>

          <div
            style={{
              marginTop: "18px",
              padding: "16px 18px",
              borderRadius: "12px",
              background: "#f7faff",
              border: "1px solid #dce7f2",
            }}
          >
            <span
              style={{
                display: "block",
                fontSize: "11px",
                letterSpacing: "1.4px",
                color: "#6680a0",
                marginBottom: "7px",
              }}
            >
              EVENT PIPELINE
            </span>

            <strong
              style={{
                color: "#12345b",
                lineHeight: 1.6,
              }}
            >
              Order Event → ML Risk → Device Intelligence →
              Expected Loss → Seller Policy → Final Control
            </strong>
          </div>

          <div
            style={{
              marginTop: "18px",
              display: "flex",
              alignItems: "center",
              gap: "14px",
              flexWrap: "wrap",
            }}
          >
            <button
              onClick={() => setShowStore(true)}
              style={{
                background: "#12345b",
                color: "#ffffff",
                border: "1px solid #12345b",
                fontWeight: "700",
              }}
            >
              Open MarginMart Store →
            </button>

            <button
              onClick={simulateWebhookOrder}
              disabled={webhookLoading}
              style={{
                background: "#ffffff",
                color: "#12345b",
                border: "1px solid #c9d7e6",
              }}
            >
              {webhookLoading
                ? "Processing Order..."
                : "Developer Test Order →"}
            </button>

            <span
              style={{
                fontSize: "12px",
                color: "#71839a",
              }}
            >
              Demo mode: sends a realistic high-risk order
              to the webhook endpoint.
            </span>
          </div>

          {webhookResult && (
            <div
              style={{
                marginTop: "20px",
                padding: "20px",
                borderRadius: "14px",
                border: "1px solid #dce7f2",
                background: "#ffffff",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: "15px",
                  flexWrap: "wrap",
                }}
              >
                <div>
                  <span
                    style={{
                      display: "block",
                      fontSize: "11px",
                      letterSpacing: "1.4px",
                      color: "#6680a0",
                      marginBottom: "7px",
                    }}
                  >
                    WEBHOOK EVENT
                  </span>

                  <strong
                    style={{
                      fontSize: "20px",
                      color: "#12345b",
                    }}
                  >
                    {webhookResult.event ||
                      webhookResult.status ||
                      "ORDER PROCESSED"}
                  </strong>
                </div>

                {webhookResult.success && (
                  <span
                    className="impact low"
                  >
                    RECEIVED
                  </span>
                )}
              </div>

              {webhookResult.success ? (
                <div
                  className="detail-grid"
                  style={{
                    marginTop: "18px",
                  }}
                >
                  <div>
                    <span>
                      ORDER ID
                    </span>

                    <strong>
                      {webhookResult.order_id}
                    </strong>
                  </div>

                  <div>
                    <span>
                      RISK
                    </span>

                    <strong>
                      {webhookResult.risk
                        ?.percentage ||
                        `${Number(
                          webhookResult.risk
                            ?.probability || 0
                        ) * 100}%`}
                    </strong>
                  </div>

                  <div>
                    <span>
                      RISK LEVEL
                    </span>

                    <strong>
                      {webhookResult.risk?.level ||
                        "N/A"}
                    </strong>
                  </div>

                  <div>
                    <span>
                      RECOMMENDED CONTROL
                    </span>

                    <strong>
                      {getActionTitle(
                        webhookResult.decision
                          ?.recommended_action
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>
                      EXPECTED LOSS
                    </span>

                    <strong>
                      {formatCurrency(
                        webhookResult.decision
                          ?.expected_loss
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>
                      LOSS AVOIDED
                    </span>

                    <strong>
                      {formatCurrency(
                        webhookResult.decision
                          ?.loss_avoided
                      )}
                    </strong>
                  </div>
                </div>
              ) : (
                <p
                  style={{
                    marginTop: "12px",
                    color: "#b42318",
                  }}
                >
                  {webhookResult.message ||
                    "Webhook processing failed."}
                </p>
              )}

              {webhookResult.success && (
                <div
                  style={{
                    marginTop: "18px",
                    padding: "14px 16px",
                    borderRadius: "10px",
                    background: "#f7faff",
                    border: "1px solid #dce7f2",
                  }}
                >
                  <span
                    style={{
                      display: "block",
                      fontSize: "11px",
                      letterSpacing: "1.3px",
                      color: "#6680a0",
                      marginBottom: "6px",
                    }}
                  >
                    NEXT STEP
                  </span>

                  <strong
                    style={{
                      color: "#12345b",
                    }}
                  >
                    {webhookResult.next_step ||
                      "Apply recommended merchant control."}
                  </strong>
                  <button
                    onClick={() =>
                      openOrderDetails(webhookResult.order_id)
                    }
                    style={{
                      marginTop: "14px",
                      padding: "11px 16px",
                      borderRadius: "10px",
                      border: "1px solid #1464c0",
                      background: "#1464c0",
                      color: "#ffffff",
                      fontWeight: "700",
                      cursor: "pointer",
                    }}
                  >
                    Open Full Risk Analysis →
                  </button>
                </div>
              )}
            </div>
          )}
        </section>
                {/* ====================================================
            LIVE ORDERS QUEUE
            ==================================================== */}

        <section
          className="high-risk"
          style={{
            marginTop: "24px",
          }}
        >
          <div
            className="section-heading"
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              gap: "20px",
              flexWrap: "wrap",
            }}
          >
            <div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <h2>Live Orders</h2>

                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "6px 10px",
                    borderRadius: "999px",
                    background: "#eef9f1",
                    border: "1px solid #c9e5d0",
                    color: "#21613a",
                    fontSize: "10px",
                    fontWeight: "800",
                    letterSpacing: "1px",
                  }}
                >
                  <span
                    style={{
                      width: "7px",
                      height: "7px",
                      borderRadius: "50%",
                      background: "#2e8b57",
                    }}
                  />
                  LIVE
                </span>
              </div>

              <p>
                Orders received through the real-time merchant webhook.
                Click an order to investigate its risk.
              </p>
            </div>

            <button
              onClick={() => fetchLiveOrders(true)}
              disabled={liveOrdersLoading}
              style={{
                padding: "9px 14px",
                borderRadius: "9px",
                border: "1px solid #c9d7e6",
                background: "#ffffff",
                color: "#12345b",
                fontWeight: "700",
                cursor: liveOrdersLoading ? "wait" : "pointer",
              }}
            >
              {liveOrdersLoading ? "Refreshing..." : "Refresh"}
            </button>
          </div>

          {/* LIVE ORDER STATS */}

          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fit, minmax(160px, 1fr))",
              gap: "12px",
              marginBottom: "18px",
            }}
          >
            <div
              style={{
                padding: "16px",
                borderRadius: "12px",
                background: "#f7faff",
                border: "1px solid #dce7f2",
              }}
            >
              <span
                style={{
                  display: "block",
                  fontSize: "10px",
                  letterSpacing: "1.2px",
                  color: "#6680a0",
                  marginBottom: "6px",
                }}
              >
                INCOMING ORDERS
              </span>

              <strong
                style={{
                  fontSize: "24px",
                  color: "#12345b",
                }}
              >
                {liveOrderStats.total}
              </strong>
            </div>

            <div
              style={{
                padding: "16px",
                borderRadius: "12px",
                background: "#fff7f5",
                border: "1px solid #eed7d1",
              }}
            >
              <span
                style={{
                  display: "block",
                  fontSize: "10px",
                  letterSpacing: "1.2px",
                  color: "#9b5d50",
                  marginBottom: "6px",
                }}
              >
                RISKY ORDERS
              </span>

              <strong
                style={{
                  fontSize: "24px",
                  color: "#9b3021",
                }}
              >
                {liveOrderStats.risky}
              </strong>
            </div>

            <div
              style={{
                padding: "16px",
                borderRadius: "12px",
                background: "#f4fbf6",
                border: "1px solid #cce4d2",
              }}
            >
              <span
                style={{
                  display: "block",
                  fontSize: "10px",
                  letterSpacing: "1.2px",
                  color: "#668d72",
                  marginBottom: "6px",
                }}
              >
                CLEAR ORDERS
              </span>

              <strong
                style={{
                  fontSize: "24px",
                  color: "#21613a",
                }}
              >
                {liveOrderStats.clear}
              </strong>
            </div>
          </div>

          {/* LIVE ORDER TABLE */}

          {liveOrders.length > 0 ? (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>ORDER</th>
                    <th>CUSTOMER</th>
                    <th>RETURN RISK</th>
                    <th>STATUS</th>
                    <th>CONTROL</th>
                    <th>EXPECTED LOSS</th>
                    <th>VALUE</th>
                  </tr>
                </thead>

                <tbody>
                  {liveOrders.map((order) => {
                    const risk = Number(
                      order.predicted_return_probability || 0
                    );

                    const riskLevel =
                      order.risk_level || "LOW";

                    return (
                      <tr
                        key={order.order_id}
                        onClick={() =>
                          openOrderDetails(order.order_id)
                        }
                        className="order-row"
                        style={{
                          cursor: "pointer",
                        }}
                      >
                        <td>
                          <strong>
                            {order.order_id}
                          </strong>
                        </td>

                        <td>
                          {order.customer_id || "N/A"}
                        </td>

                        <td>
                          <span className="risk-value">
                            {formatPercentage(risk)}
                          </span>
                        </td>

                        <td>
                          <span
                            style={{
                              display: "inline-block",
                              padding: "6px 9px",
                              borderRadius: "999px",
                              fontSize: "10px",
                              fontWeight: "800",
                              letterSpacing: "0.8px",
                              background:
                                riskLevel === "CRITICAL"
                                  ? "#fff0ee"
                                  : riskLevel === "HIGH"
                                  ? "#fff5ed"
                                  : riskLevel === "MEDIUM"
                                  ? "#fff9e8"
                                  : "#eef9f1",
                              color:
                                riskLevel === "CRITICAL"
                                  ? "#a52a1d"
                                  : riskLevel === "HIGH"
                                  ? "#a85b17"
                                  : riskLevel === "MEDIUM"
                                  ? "#8a6a00"
                                  : "#21613a",
                            }}
                          >
                            {riskLevel}
                          </span>
                        </td>

                        <td>
                          <span className="action-badge">
                            {getActionTitle(
                              order.recommended_action
                            )}
                          </span>
                        </td>

                        <td>
                          {formatCurrency(
                            order.expected_loss
                          )}
                        </td>

                        <td>
                          {formatCurrency(
                            order.order_value
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div
              style={{
                padding: "36px 20px",
                textAlign: "center",
                border: "1px dashed #cbd9e7",
                borderRadius: "12px",
                background: "#f9fbfd",
              }}
            >
              <strong
                style={{
                  display: "block",
                  color: "#12345b",
                  marginBottom: "7px",
                }}
              >
                Waiting for incoming orders
              </strong>

              <span
                style={{
                  color: "#71839a",
                  fontSize: "13px",
                }}
              >
                Place an order in MarginMart and it will
                appear here automatically.
              </span>
            </div>
          )}
        </section>
        {/* ====================================================
            BATCH UPLOAD
            ==================================================== */}

        <section className="upload-card">

          <h2>
            Batch Analysis
          </h2>

          <p>
            Upload your merchant order data to
            identify return risk and minimize
            expected losses.
          </p>

          <div className="upload-box">

            <input
              type="file"
              accept=".csv"
              onChange={(e) => {
                setFile(e.target.files[0]);
                setResult(null);
                setHighRiskOrders([]);
                setSelectedOrder(null);
              }}
            />

            {file && (
              <p className="filename">
                Selected:{" "}
                <strong>
                  {file.name}
                </strong>
              </p>
            )}

            <button
              onClick={analyzeBatch}
              disabled={loading}
            >
              {loading
                ? "Analyzing..."
                : "Analyze Orders →"}
            </button>

          </div>

        </section>

        {/* ====================================================
            RESULTS
            ==================================================== */}

        {result && (
          <>

            {/* ==================================================
                SUMMARY METRICS
                ================================================== */}

            <section className="metrics">

              <div className="metric">
                <span>
                  ORDERS ANALYZED
                </span>

                <strong>
                  {result.orders_analyzed.toLocaleString(
                    "en-IN"
                  )}
                </strong>
              </div>

              <div className="metric">
                <span>
                  BASELINE LOSS
                </span>

                <strong>
                  {formatCurrency(
                    result.baseline_expected_loss
                  )}
                </strong>
              </div>

              <div className="metric">
                <span>
                  OPTIMIZED LOSS
                </span>

                <strong>
                  {formatCurrency(
                    result.optimized_expected_loss
                  )}
                </strong>
              </div>

              <div className="metric highlight">
                <span>
                  EXPECTED SAVINGS
                </span>

                <strong>
                  {formatCurrency(
                    result.expected_savings
                  )}
                </strong>

                <small>
                  {result.savings_percentage}%
                  reduction
                </small>
              </div>

            </section>

            {/* ==================================================
                DEVICE INTELLIGENCE SUMMARY
                ================================================== */}

            {result.device_intelligence && (
              <section className="distribution">

                <h2>
                  Device Intelligence
                </h2>

                <p
                  style={{
                    marginTop: "-10px",
                    marginBottom: "20px",
                    color: "#5f6f86",
                  }}
                >
                  Additional device-level evidence
                  used alongside the ML prediction.
                </p>

                <div className="detail-grid">

                  <div>
                    <span>
                      ELEVATED DEVICE RISK
                    </span>

                    <strong>
                      {Number(
                        result.device_intelligence
                          .elevated_device_risk_orders ||
                          0
                      ).toLocaleString("en-IN")}
                    </strong>
                  </div>

                  <div>
                    <span>
                      MULTI-ACCOUNT ORDERS
                    </span>

                    <strong>
                      {Number(
                        result.device_intelligence
                          .multi_account_device_orders ||
                          0
                      ).toLocaleString("en-IN")}
                    </strong>
                  </div>

                  <div>
                    <span>
                      MAX LINKED ACCOUNTS
                    </span>

                    <strong>
                      {Number(
                        result.device_intelligence
                          .max_linked_accounts ||
                          0
                      )}
                    </strong>
                  </div>

                </div>

              </section>
            )}

            {/* ==================================================
                INTERVENTION DISTRIBUTION
                ================================================== */}

            <section className="distribution">

              <h2>
                Intervention Distribution
              </h2>

              {Object.entries(
                result.action_distribution || {}
              ).map(([action, count]) => {

                const percentage =
                  result.orders_analyzed > 0
                    ? (count /
                        result.orders_analyzed) *
                      100
                    : 0;

                return (
                  <div
                    className="action-row"
                    key={action}
                  >

                    <div className="action-info">

                      <span>
                        {getActionTitle(action)}
                      </span>

                      <strong>
                        {count.toLocaleString(
                          "en-IN"
                        )}{" "}
                        (
                        {percentage.toFixed(1)}
                        %)
                      </strong>

                    </div>

                    <div className="bar">

                      <div
                        className="bar-fill"
                        style={{
                          width: `${percentage}%`,
                        }}
                      />

                    </div>

                  </div>
                );
              })}

            </section>

            {/* ==================================================
                HIGH-RISK ORDERS
                ================================================== */}

            <section className="high-risk">

              <div className="section-heading">

                <h2>
                  High-Risk Orders
                </h2>

                <p>
                  Orders with the highest predicted
                  probability of return.
                </p>

              </div>

              {highRiskOrders.length > 0 ? (

                <div className="table-wrapper">

                  <table>

                    <thead>

                      <tr>
                        <th>
                          ORDER ID
                        </th>

                        <th>
                          RETURN RISK
                        </th>

                        <th>
                          ACTION
                        </th>

                        <th>
                          EXPECTED LOSS
                        </th>

                        <th>
                          ORDER VALUE
                        </th>

                        <th>
                          PAYMENT
                        </th>
                      </tr>

                    </thead>

                    <tbody>

                      {highRiskOrders.map(
                        (order) => (

                          <tr
                            key={order.order_id}
                            onClick={() =>
                              openOrderDetails(
                                order.order_id
                              )
                            }
                            className="order-row"
                          >

                            <td>
                              {order.order_id}
                            </td>

                            <td className="risk-value">
                              {formatPercentage(
                                order.predicted_return_probability
                              )}
                            </td>

                            <td>

                              <span className="action-badge">
                                {getActionTitle(
                                  order.recommended_action
                                )}
                              </span>

                            </td>

                            <td>
                              {formatCurrency(
                                order.expected_loss
                              )}
                            </td>

                            <td>
                              {formatCurrency(
                                order.order_value
                              )}
                            </td>

                            <td>
                              {order.payment_method}
                            </td>

                          </tr>

                        )
                      )}

                    </tbody>

                  </table>

                </div>

              ) : (

                <p>
                  No high-risk orders available.
                </p>

              )}

            </section>

          </>
        )}

      </main>

      {/* ======================================================
          ORDER DETAILS LOADING
          ====================================================== */}

      {detailsLoading && (

        <div className="modal-overlay">

          <div className="order-modal">

            <div className="modal-header">

              <p className="eyebrow">
                ORDER RISK ANALYSIS
              </p>

              <h2>
                Loading...
              </h2>

              <p>
                Loading detailed risk assessment.
              </p>

            </div>

          </div>

        </div>

      )}

      {/* ======================================================
          ORDER DETAILS MODAL
          ====================================================== */}

      {selectedOrder && (

        <div
          className="modal-overlay"
          onClick={closeOrderDetails}
        >

          <div
            className="order-modal"
            onClick={(event) =>
              event.stopPropagation()
            }
          >

            {/* ==================================================
                CLOSE BUTTON
                ================================================== */}

            <button
              className="close-button"
              onClick={closeOrderDetails}
            >
              ×
            </button>

            {/* ==================================================
                MODAL HEADER
                ================================================== */}

            <div className="modal-header">

              <p className="eyebrow">
                ORDER RISK ANALYSIS
              </p>

              <h2>
                {selectedOrder.order.order_id}
              </h2>

              <p>
                Detailed risk assessment and
                intervention recommendation.
              </p>

            </div>

            {/* ==================================================
                RISK SUMMARY
                ================================================== */}

            <section className="detail-section">

              <h3>
                Risk Summary
              </h3>

              <div className="risk-summary">

                <div>
                  <span>
                    RETURN RISK
                  </span>

                  <strong>
                    {selectedOrder.risk?.percentage ||
                      formatPercentage(
                        selectedOrder.return_risk
                      )}
                  </strong>

                  <small>
                    Post-delivery return probability
                  </small>
                </div>

                <div>
                  <span>
                    RTO RISK
                  </span>

                  <strong>
                    {selectedOrder.decision
                      ?.rto_risk_percentage
                      ? selectedOrder.decision
                          .rto_risk_percentage
                      : formatPercentage(
                          selectedOrder.decision
                            ?.rto_risk
                        )}
                  </strong>

                  <small>
                    COD non-acceptance /
                    delivery failure risk
                  </small>
                </div>

                <div>
                  <span>
                    RISK LEVEL
                  </span>

                  <strong>
                    {selectedOrder.risk?.level ||
                      "N/A"}
                  </strong>
                </div>

                <div>
                  <span>
                    ML RECOMMENDATION
                  </span>

                  <strong>
                    {getActionTitle(
                      selectedOrder.decision
                        ?.recommended_action
                    )}
                  </strong>
                </div>

              </div>

            </section>

            {/* ==================================================
                LOSS ECONOMICS
                ================================================== */}

            <section className="detail-section">

              <h3>
                Loss Economics
              </h3>

              <div className="detail-grid">

                <div>
                  <span>
                    EXPECTED LOSS
                  </span>

                  <strong>
                    {formatCurrency(
                      selectedOrder.decision
                        ?.expected_loss
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    LOSS WITHOUT ACTION
                  </span>

                  <strong>
                    {formatCurrency(
                      selectedOrder.decision
                        ?.expected_loss_no_action ??
                        selectedOrder.order
                          ?.expected_loss_no_action
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    LOSS AVOIDED
                  </span>

                  <strong>
                    {formatCurrency(
                      selectedOrder.decision
                        ?.loss_avoided
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    RETURN COST
                  </span>

                  <strong>
                    {formatCurrency(
                      selectedOrder.decision
                        ?.return_cost
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    RTO COST
                  </span>

                  <strong>
                    {formatCurrency(
                      selectedOrder.decision
                        ?.rto_cost
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    ORDER VALUE
                  </span>

                  <strong>
                    {formatCurrency(
                      selectedOrder.order.order_value
                    )}
                  </strong>
                </div>

              </div>

              <div
                style={{
                  marginTop: "18px",
                  padding: "16px 18px",
                  borderRadius: "12px",
                  background: "#f7faff",
                  border: "1px solid #dce7f2"
                }}
              >

                <span
                  style={{
                    display: "block",
                    fontSize: "11px",
                    letterSpacing: "1.4px",
                    color: "#6680a0",
                    marginBottom: "10px"
                  }}
                >
                  INTERVENTION COST COMPARISON
                </span>

                <div className="detail-grid">

                  {Object.entries(
                    selectedOrder.decision
                      ?.expected_losses || {}
                  ).map(([action, loss]) => (

                    <div key={action}>

                      <span>
                        {getActionTitle(action)}
                      </span>

                      <strong>
                        {formatCurrency(loss)}
                      </strong>

                    </div>

                  ))}

                </div>

              </div>

            </section>

            {/* ==================================================
                SELLER POLICY DECISION
                ================================================== */}

            {(() => {

              const policy =
                getSellerPolicy(selectedOrder);

              if (!policy) {
                return null;
              }

              return (

                <section className="detail-section">

                  <h3>
                    Seller Policy Decision
                  </h3>

                  <div
                    style={{
                      border:
                        "1px solid #dbe5f0",
                      borderRadius: "16px",
                      padding: "22px",
                      background:
                        policy.triggered
                          ? "#f8fbff"
                          : "#fafcff",
                      marginBottom: "18px",
                    }}
                  >

                    <div
                      style={{
                        display: "flex",
                        justifyContent:
                          "space-between",
                        alignItems: "center",
                        gap: "20px",
                        flexWrap: "wrap",
                      }}
                    >

                      <div>

                        <span
                          style={{
                            display: "block",
                            fontSize: "12px",
                            letterSpacing:
                              "1.5px",
                            color: "#6680a0",
                            marginBottom:
                              "8px",
                          }}
                        >
                          POLICY STATUS
                        </span>

                        <strong
                          style={{
                            fontSize: "24px",
                            color:
                              policy.triggered
                                ? "#0b4ea2"
                                : "#12345b",
                          }}
                        >
                          {policy.status}
                        </strong>

                      </div>

                      <div>

                        <span
                          style={{
                            display: "block",
                            fontSize: "12px",
                            letterSpacing:
                              "1.5px",
                            color: "#6680a0",
                            marginBottom:
                              "8px",
                          }}
                        >
                          FINAL CONTROL
                        </span>

                        <strong
                          style={{
                            fontSize: "20px",
                            color: "#12345b",
                          }}
                        >
                          {getActionTitle(
                            policy.finalAction
                          )}
                        </strong>

                      </div>

                    </div>

                    <p
                      style={{
                        margin:
                          "18px 0 0",
                        color: "#536b88",
                        lineHeight: 1.6,
                      }}
                    >
                      {policy.explanation}
                    </p>

                  </div>

                  {policy.rules.length > 0 && (

                    <div
                      className="risk-factors"
                    >

                      {policy.rules.map(
                        (rule, index) => (

                          <div
                            className="risk-factor"
                            key={`${rule.name}-${index}`}
                          >

                            <div>

                              <strong>
                                {rule.name
                                  .replaceAll(
                                    "_",
                                    " "
                                  )}
                              </strong>

                              <span>
                                {rule.description}
                              </span>

                            </div>

                            <span
                              className={getPolicySeverityClass(
                                rule.severity
                              )}
                            >
                              {rule.severity}
                            </span>

                          </div>

                        )
                      )}

                    </div>

                  )}

                  <div
                    style={{
                      marginTop: "18px",
                      padding: "16px 18px",
                      borderRadius: "12px",
                      background:
                        "#f4f8fc",
                      border:
                        "1px solid #dce7f2",
                    }}
                  >

                    <span
                      style={{
                        display: "block",
                        fontSize: "11px",
                        letterSpacing:
                          "1.4px",
                        color: "#6680a0",
                        marginBottom:
                          "6px",
                      }}
                    >
                      SELLER NEXT STEP
                    </span>

                    <strong
                      style={{
                        color: "#12345b",
                      }}
                    >
                      {getNextStep(
                        policy.finalAction
                      )}
                    </strong>

                  </div>

                </section>

              );

            })()}

            {/* ==================================================
                DECISION FLOW
                ================================================== */}

            {(() => {

              const policy =
                getSellerPolicy(selectedOrder);

              const mlAction =
                selectedOrder.decision
                  ?.recommended_action ||
                "NO_ACTION";

              const finalAction =
                policy?.triggered
                  ? policy.finalAction
                  : mlAction;

              const overridden =
                policy?.triggered &&
                finalAction !== mlAction;

              return (

                <section className="detail-section">

                  <h3>
                    Decision Flow
                  </h3>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fit, minmax(180px, 1fr))",
                      gap: "12px",
                    }}
                  >

                    <div
                      style={{
                        padding: "18px",
                        borderRadius: "12px",
                        background: "#f7faff",
                        border: "1px solid #dce7f2",
                      }}
                    >

                      <span
                        style={{
                          display: "block",
                          fontSize: "11px",
                          letterSpacing: "1.3px",
                          color: "#6680a0",
                          marginBottom: "7px",
                        }}
                      >
                        ML DECISION
                      </span>

                      <strong
                        style={{
                          color: "#12345b",
                        }}
                      >
                        {getActionTitle(
                          mlAction
                        )}
                      </strong>

                    </div>

                    <div
                      style={{
                        padding: "18px",
                        borderRadius: "12px",
                        background: "#f7faff",
                        border: "1px solid #dce7f2",
                      }}
                    >

                      <span
                        style={{
                          display: "block",
                          fontSize: "11px",
                          letterSpacing: "1.3px",
                          color: "#6680a0",
                          marginBottom: "7px",
                        }}
                      >
                        SELLER POLICY
                      </span>

                      <strong
                        style={{
                          color: "#12345b",
                        }}
                      >
                        {policy?.triggered
                          ? getActionTitle(
                              policy.finalAction
                            )
                          : "No policy override"}
                      </strong>

                    </div>

                    <div
                      style={{
                        padding: "18px",
                        borderRadius: "12px",
                        background: "#f7faff",
                        border: "1px solid #dce7f2",
                      }}
                    >

                      <span
                        style={{
                          display: "block",
                          fontSize: "11px",
                          letterSpacing: "1.3px",
                          color: "#6680a0",
                          marginBottom: "7px",
                        }}
                      >
                        FINAL CONTROL
                      </span>

                      <strong
                        style={{
                          color: "#0b4ea2",
                        }}
                      >
                        {getActionTitle(
                          finalAction
                        )}
                      </strong>

                    </div>

                  </div>

                  <div
                    style={{
                      marginTop: "14px",
                      padding: "14px 16px",
                      borderRadius: "12px",
                      background:
                        overridden
                          ? "#fff8ed"
                          : "#f4f8fc",
                      border:
                        overridden
                          ? "1px solid #f0d7ad"
                          : "1px solid #dce7f2",
                    }}
                  >

                    <strong
                      style={{
                        color: "#12345b",
                      }}
                    >
                      {overridden
                        ? "Policy override applied"
                        : "No policy override"}
                    </strong>

                    <span
                      style={{
                        display: "block",
                        marginTop: "5px",
                        color: "#536b88",
                        lineHeight: 1.5,
                      }}
                    >
                      {overridden
                        ? "The merchant policy takes precedence over the cost-sensitive ML recommendation."
                        : "The economic recommendation remains the final control."}
                    </span>

                  </div>

                </section>

              );

            })()}

            {/* ==================================================
                RISK FACTORS
                ================================================== */}

            {selectedOrder.risk_factors &&
              selectedOrder.risk_factors.length >
                0 && (

                <section className="detail-section">

                  <h3>
                    Risk Factors
                  </h3>

                  <div className="risk-factors">

                    {selectedOrder.risk_factors.map(
                      (factor, index) => (

                        <div
                          className="risk-factor"
                          key={`${factor.factor}-${index}`}
                        >

                          <div>

                            <strong>
                              {factor.factor}
                            </strong>

                            <span>
                              {factor.value}
                            </span>

                          </div>

                          <span
                            className={
                              factor.impact ===
                              "HIGH"
                                ? "impact high"
                                : factor.impact ===
                                  "MEDIUM"
                                ? "impact"
                                : "impact low"
                            }
                          >
                            {factor.impact}
                          </span>

                        </div>

                      )
                    )}

                  </div>

                </section>

              )}

            {/* ==================================================
                DEVICE INTELLIGENCE
                ================================================== */}

            {(() => {

              const device =
                getDeviceIntelligence(
                  selectedOrder
                );

              return (

                <section className="detail-section">

                  <h3>
                    Device Intelligence
                  </h3>

                  <p
                    className="explanation-subtitle"
                  >
                    Device-level evidence is used
                    as a supporting risk signal,
                    not as a standalone fraud verdict.
                  </p>

                  <div className="detail-grid">

                    <div>

                      <span>
                        DEVICE
                      </span>

                      <strong>
                        {device.deviceId}
                      </strong>

                    </div>

                    <div>

                      <span>
                        LINKED ACCOUNTS
                      </span>

                      <strong>
                        {device.linkedAccounts}
                      </strong>

                    </div>

                    <div>

                      <span>
                        PREVIOUS RETURNS
                      </span>

                      <strong>
                        {device.previousReturns}
                      </strong>

                    </div>

                    <div>

                      <span>
                        PREVIOUS RTOS
                      </span>

                      <strong>
                        {device.previousRtos}
                      </strong>

                    </div>

                    <div>

                      <span>
                        MULTI-ACCOUNT
                      </span>

                      <strong>
                        {device.multiAccount
                          ? "YES"
                          : "NO"}
                      </strong>

                    </div>

                    <div>

                      <span>
                        DEVICE SIGNAL
                      </span>

                      <strong
                        style={{
                          fontSize: "15px",
                        }}
                      >
                        {device.signal}
                      </strong>

                    </div>

                  </div>

                  {device.linkedAccounts >=
                    3 && (

                    <div
                      style={{
                        marginTop: "18px",
                        padding:
                          "16px 18px",
                        borderRadius: "12px",
                        border:
                          "1px solid #dce7f2",
                        background:
                          "#f7faff",
                      }}
                    >

                      <strong
                        style={{
                          display:
                            "block",
                          color:
                            "#12345b",
                          marginBottom:
                            "6px",
                        }}
                      >
                        Shared device
                        signal detected
                      </strong>

                      <span
                        style={{
                          color:
                            "#536b88",
                          lineHeight:
                            1.5,
                        }}
                      >
                        This device is
                        associated with{" "}
                        {
                          device.linkedAccounts
                        }{" "}
                        customer accounts.
                        The signal should
                        be evaluated together
                        with return history
                        and transaction risk.
                      </span>

                    </div>

                  )}

                </section>

              );

            })()}

            {/* ==================================================
                MODEL EXPLANATION
                ================================================== */}

            <section className="detail-section">

              <h3>
                Why Is This Order Risky?
              </h3>

              <p
                className="explanation-subtitle"
              >
                Top features influencing the
                Logistic Regression prediction
                for this order.
              </p>

              {selectedOrder.explanation &&
              selectedOrder.explanation.length >
                0 ? (

                <div className="risk-factors">

                  {selectedOrder.explanation.map(
                    (factor, index) => (

                      <div
                        className="risk-factor"
                        key={`${factor.feature}-${index}`}
                      >

                        <div>

                          <strong>
                            {factor.feature}
                          </strong>

                          <span>
                            Value:{" "}
                            {factor.value}
                          </span>

                          {factor.transformed_value !==
                            undefined && (

                            <span>
                              Model value:{" "}
                              {Number(
                                factor.transformed_value
                              ).toFixed(4)}
                            </span>

                          )}

                          <span>
                            Contribution:{" "}
                            {Number(
                              factor.contribution
                            ).toFixed(4)}
                          </span>

                        </div>

                        <span
                          className={getExplanationClass(
                            factor.direction
                          )}
                        >
                          {factor.direction ===
                          "INCREASES_RISK"
                            ? "INCREASES RISK"
                            : factor.direction ===
                              "DECREASES_RISK"
                            ? "DECREASES RISK"
                            : "NEUTRAL"}
                        </span>

                      </div>

                    )
                  )}

                </div>

              ) : (

                <p>
                  No model explanation is
                  available for this order.
                </p>

              )}

            </section>

            {/* ==================================================
                RECOMMENDED INTERVENTION
                ================================================== */}

            <section className="detail-section">

              <h3>
                Recommended Intervention
              </h3>

              <div
                style={{
                  padding: "22px",
                  borderRadius: "16px",
                  border:
                    "1px solid #dbe5f0",
                  background:
                    "#f8fbff",
                }}
              >

                <div
                  style={{
                    display: "flex",
                    alignItems:
                      "center",
                    gap: "16px",
                  }}
                >

                  <div
                    style={{
                      width: "46px",
                      height: "46px",
                      borderRadius:
                        "50%",
                      display: "flex",
                      alignItems:
                        "center",
                      justifyContent:
                        "center",
                      background:
                        "#eaf3ff",
                      color:
                        "#1464c0",
                      fontSize:
                        "20px",
                      fontWeight:
                        "700",
                    }}
                  >
                    {getActionIcon(
                      selectedOrder.decision
                        ?.recommended_action
                    )}
                  </div>

                  <div>

                    <strong
                      style={{
                        display:
                          "block",
                        fontSize:
                          "20px",
                        color:
                          "#12345b",
                      }}
                    >
                      {getActionTitle(
                        selectedOrder.decision
                          ?.recommended_action
                      )}
                    </strong>

                    <span
                      style={{
                        color:
                          "#5f6f86",
                        display:
                          "block",
                        marginTop:
                          "5px",
                      }}
                    >
                      {getActionDescription(
                        selectedOrder.decision
                          ?.recommended_action
                      )}
                    </span>

                  </div>

                </div>

                <div
                  style={{
                    marginTop: "18px",
                    paddingTop: "16px",
                    borderTop:
                      "1px solid #dce7f2",
                  }}
                >

                  <span
                    style={{
                      fontSize:
                        "11px",
                      letterSpacing:
                        "1.4px",
                      color:
                        "#6680a0",
                    }}
                  >
                    NEXT STEP
                  </span>

                  <p
                    style={{
                      margin:
                        "7px 0 0",
                      color:
                        "#12345b",
                      fontWeight:
                        "600",
                    }}
                  >
                    {getNextStep(
                      selectedOrder.decision
                        ?.recommended_action
                    )}
                  </p>

                </div>

              </div>

            </section>

            {/* ==================================================
                ACTION CENTER
                ================================================== */}
            {(() => {
              const mlAction =
                selectedOrder.decision?.recommended_action ||
                "NO_ACTION";

              const policy =
                getSellerPolicy(selectedOrder);

              const finalAction =
                policy?.triggered
                  ? policy.finalAction
                  : mlAction;

              const recommendedExecutable =
                getExecutableAction(finalAction);

              const actions = [
                {
                  action: "SEND_TO_MANUAL_REVIEW",
                  label: "Send to Manual Review",
                  description:
                    "Route the order to the merchant risk review queue.",
                },
                {
                  action: "SEND_CUSTOMER_VERIFICATION",
                  label: "Send Customer Verification",
                  description:
                    "Request customer confirmation before dispatch.",
                },
                {
                  action: "DISABLE_COD",
                  label: "Disable COD",
                  description:
                    "Apply a cash-on-delivery restriction to this order.",
                },
                {
                  action: "RELEASE_ORDER",
                  label: "Release Order",
                  description:
                    "Release the order after merchant approval.",
                },
              ];

              return (
                <section className="detail-section">
                  <h3>Action Center</h3>

                  <div
                    style={{
                      padding: "22px",
                      borderRadius: "16px",
                      border: "1px solid #dbe5f0",
                      background: "#f8fbff",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "flex-start",
                        gap: "20px",
                        flexWrap: "wrap",
                        marginBottom: "20px",
                      }}
                    >
                      <div>
                        <span
                          style={{
                            display: "block",
                            fontSize: "11px",
                            letterSpacing: "1.4px",
                            color: "#6680a0",
                            marginBottom: "7px",
                          }}
                        >
                          FINAL CONTROL
                        </span>

                        <strong
                          style={{
                            display: "block",
                            fontSize: "22px",
                            color: "#12345b",
                          }}
                        >
                          {getActionTitle(finalAction)}
                        </strong>

                        <span
                          style={{
                            display: "block",
                            marginTop: "6px",
                            color: "#5f6f86",
                          }}
                        >
                          ML: {getActionTitle(mlAction)}
                          {policy?.triggered
                            ? ` · Policy: ${getActionTitle(
                                policy.finalAction
                              )}`
                            : ""}
                        </span>
                      </div>

                      <span
                        style={{
                          padding: "8px 12px",
                          borderRadius: "999px",
                          background: "#eef5ff",
                          border: "1px solid #cfe0f5",
                          color: "#0b4ea2",
                          fontSize: "11px",
                          fontWeight: "700",
                          letterSpacing: "1px",
                        }}
                      >
                        MERCHANT APPROVAL REQUIRED
                      </span>
                    </div>

                    <p
                      style={{
                        margin: "0 0 18px",
                        color: "#536b88",
                        lineHeight: 1.6,
                      }}
                    >
                      MarginGuard converts the risk decision into a
                      merchant-controlled action. Controls are executed
                      only after approval and are simulated/internal
                      demo actions rather than silent external changes.
                    </p>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "repeat(auto-fit, minmax(210px, 1fr))",
                        gap: "12px",
                      }}
                    >
                      {actions.map((item) => {
                        const recommended =
                          item.action ===
                          recommendedExecutable;

                        return (
                          <button
                            key={item.action}
                            onClick={() =>
                              executeOrderAction(item.action)
                            }
                            disabled={actionLoading}
                            style={{
                              position: "relative",
                              textAlign: "left",
                              padding: "18px",
                              borderRadius: "14px",
                              border: recommended
                                ? "2px solid #1464c0"
                                : "1px solid #dbe5f0",
                              background: recommended
                                ? "#eef6ff"
                                : "#ffffff",
                              cursor: actionLoading
                                ? "wait"
                                : "pointer",
                              opacity: actionLoading
                                ? 0.65
                                : 1,
                            }}
                          >
                            {recommended && (
                              <span
                                style={{
                                  display: "inline-block",
                                  marginBottom: "9px",
                                  padding: "4px 7px",
                                  borderRadius: "6px",
                                  background: "#1464c0",
                                  color: "#ffffff",
                                  fontSize: "9px",
                                  fontWeight: "700",
                                  letterSpacing: "1px",
                                }}
                              >
                                RECOMMENDED
                              </span>
                            )}

                            <strong
                              style={{
                                display: "block",
                                color: "#12345b",
                                marginBottom: "7px",
                              }}
                            >
                              {item.label}
                            </strong>

                            <span
                              style={{
                                display: "block",
                                color: "#667b95",
                                fontSize: "13px",
                                lineHeight: 1.5,
                              }}
                            >
                              {item.description}
                            </span>
                          </button>
                        );
                      })}
                    </div>

                    {actionResult && (
                      <div
                        style={{
                          marginTop: "18px",
                          padding: "16px 18px",
                          borderRadius: "12px",
                          border: "1px solid #dce7f2",
                          background: "#ffffff",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            gap: "15px",
                            alignItems: "center",
                            flexWrap: "wrap",
                          }}
                        >
                          <strong
                            style={{
                              color: "#12345b",
                            }}
                          >
                            Action Result
                          </strong>

                          <span
                            className={getActionStatusClass(
                              actionResult.status
                            )}
                          >
                            {actionResult.status ||
                              (actionResult.success
                                ? "SUCCESS"
                                : "FAILED")}
                          </span>
                        </div>

                        <p
                          style={{
                            margin: "10px 0 5px",
                            color: "#536b88",
                            lineHeight: 1.5,
                          }}
                        >
                          {actionResult.message ||
                            "Merchant action processed."}
                        </p>

                        {actionResult.action_id && (
                          <span
                            style={{
                              fontSize: "12px",
                              color: "#6680a0",
                            }}
                          >
                            Action ID:{" "}
                            {actionResult.action_id}
                          </span>
                        )}

                        {actionResult.executed_action && (
                          <span
                            style={{
                              display: "block",
                              marginTop: "5px",
                              fontSize: "12px",
                              color: "#6680a0",
                            }}
                          >
                            Executed:{" "}
                            {getActionTitle(
                              actionResult.executed_action
                            )}
                          </span>
                        )}
                      </div>
                    )}

                    <div
                      style={{
                        marginTop: "22px",
                        paddingTop: "18px",
                        borderTop: "1px solid #dce7f2",
                      }}
                    >
                      <span
                        style={{
                          display: "block",
                          fontSize: "11px",
                          letterSpacing: "1.4px",
                          color: "#6680a0",
                          marginBottom: "12px",
                        }}
                      >
                        ACTION HISTORY / AUDIT LOG
                      </span>

                      {actionHistory.length > 0 ? (
                        <div
                          style={{
                            display: "grid",
                            gap: "9px",
                          }}
                        >
                          {actionHistory
                            .slice()
                            .reverse()
                            .map((entry, index) => (
                              <div
                                key={
                                  entry.action_id ||
                                  `${entry.action}-${index}`
                                }
                                style={{
                                  display: "flex",
                                  justifyContent:
                                    "space-between",
                                  alignItems: "center",
                                  gap: "15px",
                                  padding: "12px 14px",
                                  borderRadius: "10px",
                                  background: "#f7faff",
                                  border:
                                    "1px solid #e1eaf3",
                                  flexWrap: "wrap",
                                }}
                              >
                                <div>
                                  <strong
                                    style={{
                                      display: "block",
                                      color: "#12345b",
                                    }}
                                  >
                                    {getActionHistoryTitle(
                                      entry.action ||
                                        entry.executed_action
                                    )}
                                  </strong>

                                  {entry.action_id && (
                                    <span
                                      style={{
                                        display: "block",
                                        marginTop: "3px",
                                        fontSize: "11px",
                                        color: "#71839a",
                                      }}
                                    >
                                      {entry.action_id}
                                    </span>
                                  )}
                                </div>

                                <span
                                  className={getActionStatusClass(
                                    entry.status
                                  )}
                                >
                                  {entry.status ||
                                    "EXECUTED"}
                                </span>
                              </div>
                            ))}
                        </div>
                      ) : (
                        <p
                          style={{
                            margin: 0,
                            color: "#71839a",
                            fontSize: "13px",
                          }}
                        >
                          No merchant actions executed for this
                          order yet.
                        </p>
                      )}
                    </div>
                  </div>
                </section>
              );
            })()}

            {/* ==================================================
                ORDER INFORMATION
                ================================================== */}

            <section className="detail-section">

              <h3>
                Order Information
              </h3>

              <div className="detail-grid">

                <div>
                  <span>
                    PRODUCT CATEGORY
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .product_category
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    PAYMENT METHOD
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .payment_method
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    SHIPPING METHOD
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .shipping_method
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    PRODUCT PRICE
                  </span>

                  <strong>
                    {formatCurrency(
                      selectedOrder.order
                        .product_price
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    DELIVERY DISTANCE
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .delivery_distance_km
                    }{" "}
                    km
                  </strong>
                </div>

                <div>
                  <span>
                    ESTIMATED DELIVERY
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .estimated_delivery_days
                    }{" "}
                    days
                  </strong>
                </div>

                <div>
                  <span>
                    PRODUCT RATING
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .product_rating
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    DISCOUNT
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .discount_percent
                    }%
                  </strong>
                </div>

              </div>

            </section>

            {/* ==================================================
                CUSTOMER INFORMATION
                ================================================== */}

            <section className="detail-section">

              <h3>
                Customer Information
              </h3>

              <div className="detail-grid">

                <div>
                  <span>
                    CUSTOMER ID
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .customer_id ??
                      "N/A"
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    CUSTOMER AGE
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .customer_age
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    ACCOUNT AGE
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .account_age_days
                    }{" "}
                    days
                  </strong>
                </div>

                <div>
                  <span>
                    PAST PURCHASES
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .past_purchase_count
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    PAST RETURN RATE
                  </span>

                  <strong>
                    {formatPercentage(
                      selectedOrder.order
                        .past_return_rate,
                      1
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    PAST RTO RATE
                  </span>

                  <strong>
                    {formatPercentage(
                      selectedOrder.order
                        .past_rto_rate,
                      1
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    DEVICE TYPE
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .device_type
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    NEW DEVICE
                  </span>

                  <strong>
                    {
                      selectedOrder.order
                        .new_device
                        ? "YES"
                        : "NO"
                    }
                  </strong>
                </div>

              </div>

            </section>

            {/* ==================================================
                CLOSE
                ================================================== */}

            <button
              className="modal-close-action"
              onClick={closeOrderDetails}
            >
              Close
            </button>

          </div>

        </div>

      )}

    </div>
  );
}

export default App;