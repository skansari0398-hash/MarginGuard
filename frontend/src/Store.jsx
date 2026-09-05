import { useMemo, useState } from "react";

const API_URL = "http://127.0.0.1:8000";

const PRODUCTS = [
  {
    id: "PROD-1001",
    name: "Wireless Headphones",
    category: "Electronics",
    price: 2499,
    rating: 4.4,
    margin: 700,
    image: "🎧",
  },
  {
    id: "PROD-1002",
    name: "Running Sneakers",
    category: "Sports",
    price: 3199,
    rating: 4.2,
    margin: 950,
    image: "👟",
  },
  {
    id: "PROD-1003",
    name: "Premium Hoodie",
    category: "Fashion",
    price: 1899,
    rating: 4.1,
    margin: 620,
    image: "🧥",
  },
  {
    id: "PROD-1004",
    name: "Smart Home Speaker",
    category: "Electronics",
    price: 3499,
    rating: 4.5,
    margin: 1050,
    image: "🔊",
  },
  {
    id: "PROD-1005",
    name: "Everyday Backpack",
    category: "Fashion",
    price: 1499,
    rating: 4.3,
    margin: 520,
    image: "🎒",
  },
  {
    id: "PROD-1006",
    name: "Fitness Smartwatch",
    category: "Electronics",
    price: 4299,
    rating: 4.6,
    margin: 1250,
    image: "⌚",
  },
];

const CUSTOMER_PROFILES = [
  {
    id: "35037",
    name: "Aarav Sharma",
    
    deviceId: "DEV0103487",
    deviceType: "Android",
    newDevice: true,
  },
  {
    id: "32155",
    name: "Priya Mehta",
    
    deviceId: "DEV0204812",
    deviceType: "iOS",
    newDevice: false,
  },
  {
    id: "47037",
    name: "Rahul Verma",
    
    deviceId: "DEV0318821",
    deviceType: "Web",
    newDevice: false,
  },
];

function Store({ onBackToDashboard, onOrderProcessed }) {
  const [cart, setCart] = useState([]);
  const [customer, setCustomer] = useState(
    CUSTOMER_PROFILES[0]
  );

  const [paymentMethod, setPaymentMethod] =
    useState("COD");

  const [shippingMethod, setShippingMethod] =
    useState("Standard");

  

  const [discountPercent, setDiscountPercent] = 
    useState(10);

  const [couponUsed, setCouponUsed] = 
    useState(false);

  // Demo transaction profile.
  // Customer history is still resolved server-side.
  // These represent the current checkout context.
  const applyCustomerScenario = (customerId) => {
    if (customerId === "35037") {
      // Higher-risk scenario
      setPaymentMethod("COD");
      setShippingMethod("Standard");
      setDiscountPercent(20);
      setCouponUsed(true);
      return;
    }

    if (customerId === "32155") {
      // Moderate / cleaner scenario
      setPaymentMethod("Prepaid");
      setShippingMethod("Standard");
      setDiscountPercent(5);
      setCouponUsed(false);
      return;
    }

    if (customerId === "47037") {
      // Clean / low-risk scenario
      setPaymentMethod("Prepaid");
      setShippingMethod("Express");
      setDiscountPercent(5);
      setCouponUsed(false);
    }
  };
  const [checkoutOpen, setCheckoutOpen] =
    useState(false);

  const [placingOrder, setPlacingOrder] =
    useState(false);

  const [orderResult, setOrderResult] =
    useState(null);

  const [category, setCategory] =
    useState("All");

  const filteredProducts = useMemo(() => {
    if (category === "All") {
      return PRODUCTS;
    }

    return PRODUCTS.filter(
      (product) =>
        product.category === category
    );
  }, [category]);

  const categories = [
    "All",
    "Electronics",
    "Fashion",
    "Sports",
  ];

  const cartTotal = cart.reduce(
    (total, item) =>
      total + item.price * item.quantity,
    0
  );

  const discountAmount =
    cartTotal * (discountPercent / 100);

  const finalTotal =
    cartTotal - discountAmount;

  const totalMargin = cart.reduce(
    (total, item) =>
      total +
      item.margin * item.quantity,
    0
  );

  const addToCart = (product) => {
    setCart((current) => {
      const existing = current.find(
        (item) => item.id === product.id
      );

      if (existing) {
        return current.map((item) =>
          item.id === product.id
            ? {
                ...item,
                quantity:
                  item.quantity + 1,
              }
            : item
        );
      }

      return [
        ...current,
        {
          ...product,
          quantity: 1,
        },
      ];
    });
  };

  const removeFromCart = (productId) => {
    setCart((current) =>
      current
        .map((item) =>
          item.id === productId
            ? {
                ...item,
                quantity:
                  item.quantity - 1,
              }
            : item
        )
        .filter(
          (item) => item.quantity > 0
        )
    );
  };

  const openCheckout = () => {
    if (cart.length === 0) {
      alert(
        "Add at least one product to the cart."
      );
      return;
    }

    setOrderResult(null);
    setCheckoutOpen(true);
  };
  // Delivery distance is system-derived, not customer-controlled.
  const deliveryDistance =
    customer.id === "35037"
      ? 80
      : customer.id === "32155"
        ? 35
        : 35;
  const placeOrder = async () => {
    if (cart.length === 0) {
        return;
    }

    setPlacingOrder(true);
    setOrderResult(null);

    const primaryProduct = cart[0];

    const orderId = `LIVE-${Date.now()}`;

    // Current-session / transaction signals.
    // Historical customer behavior is resolved server-side
    // by MarginGuard.
    const sessionLength =
      customer.id === "35037"
        ? 120
        : customer.id === "47037"
          ? 8
          : 12;

    const productViews =
      customer.id === "35037"
        ? 8
        : customer.id === "47037"
          ? 3
          : 5;

    const order = {
        order_id: orderId,

        // Customer identity / device context
        customer_id: customer.id,
        customer_account_id: customer.id,
        device_fingerprint_id: customer.deviceId,

        // Current transaction
        product_id: primaryProduct.id,
        product_category: primaryProduct.category,
        product_price: primaryProduct.price,
        product_rating: primaryProduct.rating,

        discount_percent: discountPercent,

        payment_method: paymentMethod,
        shipping_method: shippingMethod,

        // Current device/session signals
        device_type: customer.deviceType,
        new_device: customer.newDevice,

        is_first_order: false,
        used_coupon: couponUsed,

        session_length_minutes: sessionLength,
        num_product_views: productViews,

        estimated_delivery_days:
        shippingMethod === "Express"
            ? 3
            : 6,

        delivery_distance_km:
        Number(deliveryDistance),

        order_value:
        Number(finalTotal.toFixed(2)),

        gross_margin:
        Number(
            Math.max(
            totalMargin - discountAmount,
            0
            ).toFixed(2)
        ),
    };

    try {
        const response = await fetch(
        `${API_URL}/webhooks/order`,
        {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            },
            body: JSON.stringify(order),
        }
        );

        const data = await response
        .json()
        .catch(() => null);

        if (!response.ok) {
        throw new Error(
            data?.detail ||
            "MarginGuard could not process the order."
        );
        }

        // Customer receives only an acknowledgement.
        // MarginGuard's internal risk analysis stays
        // on the merchant side.
        const processedOrderId = data?.order_id || orderId;

        setOrderResult({
        success: true,
        order,
        orderId: processedOrderId,
        });

        setCart([]);
        setCheckoutOpen(false);

        if (typeof onOrderProcessed === "function") {
        onOrderProcessed(processedOrderId);
        }
    } catch (error) {
        setOrderResult({
        success: false,
        message: error.message,
        });
    } finally {
        setPlacingOrder(false);
    }
    };

  return (
    <div
      style={{
        minHeight: "100vh",
        background:
          "#f5f8fc",
        color: "#12345b",
        fontFamily:
          "Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
      }}
    >
      {/* ======================================================
          STORE HEADER
          ====================================================== */}

      <header
        style={{
          background: "#ffffff",
          borderBottom:
            "1px solid #dce5ef",
          padding:
            "18px 6vw",
          display: "flex",
          alignItems: "center",
          justifyContent:
            "space-between",
          gap: "20px",
          position: "sticky",
          top: 0,
          zIndex: 20,
        }}
      >
        <div>
          <div
            style={{
              fontSize: "12px",
              letterSpacing:
                "3px",
              fontWeight: "800",
              color: "#1464c0",
            }}
          >
            MARGINMART
          </div>

          <div
            style={{
              fontSize: "12px",
              color: "#6680a0",
              marginTop: "4px",
            }}
          >
            Demo Merchant Store
          </div>
        </div>

        <button
          onClick={onBackToDashboard}
          style={{
            border:
              "1px solid #cbd8e6",
            background:
              "#ffffff",
            color: "#12345b",
            borderRadius:
              "9px",
            padding:
              "10px 16px",
            cursor: "pointer",
            fontWeight: "700",
          }}
        >
          ← MarginGuard Dashboard
        </button>
      </header>

      <main
        style={{
          maxWidth:
            "1250px",
          margin:
            "0 auto",
          padding:
            "45px 24px 80px",
        }}
      >
        {/* ====================================================
            HERO
            ==================================================== */}

        <section
          style={{
            background:
              "linear-gradient(135deg, #ffffff, #eef5fd)",
            border:
              "1px solid #dce6f0",
            borderRadius:
              "22px",
            padding:
              "42px",
            marginBottom:
              "28px",
          }}
        >
          <div
            style={{
              display:
                "inline-flex",
              alignItems:
                "center",
              gap: "8px",
              background:
                "#eaf3ff",
              border:
                "1px solid #c8def8",
              color:
                "#1464c0",
              padding:
                "7px 11px",
              borderRadius:
                "999px",
              fontSize:
                "11px",
              fontWeight:
                "800",
              letterSpacing:
                "1.2px",
            }}
          >
            DEMO STOREFRONT
          </div>

          <h1
            style={{
              fontSize:
                "44px",
              margin:
                "18px 0 10px",
              letterSpacing:
                "-1.5px",
            }}
          >
            Shop normally.
            <br />
            MarginGuard works
            behind the scenes.
          </h1>

          <p
            style={{
              maxWidth:
                "760px",
              color:
                "#536b88",
              fontSize:
                "17px",
              lineHeight:
                1.65,
              margin: 0,
            }}
          >
            Place a real demo order from
            this storefront. The checkout
            sends the order event directly
            to MarginGuard for real-time
            risk scoring and loss
            prevention.
          </p>
        </section>

        {/* ====================================================
            CUSTOMER CONTEXT
            ==================================================== */}

        <section
          style={{
            background:
              "#ffffff",
            border:
              "1px solid #dce6f0",
            borderRadius:
              "18px",
            padding:
              "24px",
            marginBottom:
              "28px",
          }}
        >
          <div
            style={{
              display:
                "flex",
              justifyContent:
                "space-between",
              alignItems:
                "center",
              gap: "20px",
              flexWrap:
                "wrap",
            }}
          >
            <div>
              <div
                style={{
                  fontSize:
                    "11px",
                  letterSpacing:
                    "1.5px",
                  color:
                    "#6680a0",
                  marginBottom:
                    "6px",
                }}
              >
                DEMO CUSTOMER
              </div>

              <strong
                style={{
                  fontSize:
                    "19px",
                }}
              >
                {customer.name}
              </strong>

              <div
                style={{
                  color:
                    "#6680a0",
                  marginTop:
                    "4px",
                  fontSize:
                    "13px",
                }}
              >
                Account:{" "}
                {customer.id}
                {" • "}
                Device:{" "}
                {customer.deviceId}
              </div>
            </div>

            <select
              value={customer.id}
              onChange={(event) => {
                const selected =
                  CUSTOMER_PROFILES.find(
                    (profile) =>
                      profile.id ===
                      event.target.value
                  );

                if (selected) {
                  setCustomer(selected);
                  applyCustomerScenario(selected.id);
                }
              }}
              style={{
                minWidth:
                  "240px",
                padding:
                  "11px 13px",
                border:
                  "1px solid #ccd9e7",
                borderRadius:
                  "9px",
                background:
                  "#ffffff",
                color:
                  "#12345b",
              }}
            >
              {CUSTOMER_PROFILES.map(
                (profile) => (
                  <option
                    key={profile.id}
                    value={profile.id}
                  >
                    {profile.name}
                  </option>
                )
              )}
            </select>
          </div>
        </section>

        {/* ====================================================
            CATEGORY FILTER
            ==================================================== */}

        <div
          style={{
            display:
              "flex",
            gap: "8px",
            marginBottom:
              "22px",
            flexWrap:
              "wrap",
          }}
        >
          {categories.map(
            (item) => (
              <button
                key={item}
                onClick={() =>
                  setCategory(item)
                }
                style={{
                  padding:
                    "9px 15px",
                  borderRadius:
                    "999px",
                  border:
                    category ===
                    item
                      ? "1px solid #1464c0"
                      : "1px solid #d3deea",
                  background:
                    category ===
                    item
                      ? "#eaf3ff"
                      : "#ffffff",
                  color:
                    category ===
                    item
                      ? "#1464c0"
                      : "#536b88",
                  fontWeight:
                    "700",
                  cursor:
                    "pointer",
                }}
              >
                {item}
              </button>
            )
          )}
        </div>

        {/* ====================================================
            PRODUCTS + CART
            ==================================================== */}

        <div
          style={{
            display:
              "grid",
            gridTemplateColumns:
              "minmax(0, 1fr) 340px",
            gap: "24px",
            alignItems:
              "start",
          }}
        >
          <section
            style={{
              display:
                "grid",
              gridTemplateColumns:
                "repeat(auto-fit, minmax(220px, 1fr))",
              gap: "16px",
            }}
          >
            {filteredProducts.map(
              (product) => (
                <article
                  key={product.id}
                  style={{
                    background:
                      "#ffffff",
                    border:
                      "1px solid #dce6f0",
                    borderRadius:
                      "16px",
                    padding:
                      "20px",
                  }}
                >
                  <div
                    style={{
                      height:
                        "130px",
                      display:
                        "flex",
                      alignItems:
                        "center",
                      justifyContent:
                        "center",
                      background:
                        "#f4f8fc",
                      borderRadius:
                        "12px",
                      fontSize:
                        "58px",
                      marginBottom:
                        "17px",
                    }}
                  >
                    {product.image}
                  </div>

                  <div
                    style={{
                      fontSize:
                        "11px",
                      color:
                        "#6680a0",
                      letterSpacing:
                        "1px",
                      textTransform:
                        "uppercase",
                    }}
                  >
                    {
                      product.category
                    }
                  </div>

                  <h3
                    style={{
                      margin:
                        "7px 0 5px",
                      fontSize:
                        "17px",
                    }}
                  >
                    {product.name}
                  </h3>

                  <div
                    style={{
                      color:
                        "#536b88",
                      fontSize:
                        "13px",
                    }}
                  >
                    ★{" "}
                    {product.rating}
                  </div>

                  <div
                    style={{
                      display:
                        "flex",
                      justifyContent:
                        "space-between",
                      alignItems:
                        "center",
                      marginTop:
                        "17px",
                      gap: "10px",
                    }}
                  >
                    <strong
                      style={{
                        fontSize:
                          "20px",
                      }}
                    >
                      ₹
                      {product.price.toLocaleString(
                        "en-IN"
                      )}
                    </strong>

                    <button
                      onClick={() =>
                        addToCart(
                          product
                        )
                      }
                      style={{
                        background:
                          "#12345b",
                        color:
                          "#ffffff",
                        border:
                          "none",
                        borderRadius:
                          "8px",
                        padding:
                          "9px 13px",
                        cursor:
                          "pointer",
                        fontWeight:
                          "700",
                      }}
                    >
                      Add
                    </button>
                  </div>
                </article>
              )
            )}
          </section>

          {/* ==================================================
              CART
              ================================================== */}

          <aside
            style={{
              background:
                "#ffffff",
              border:
                "1px solid #dce6f0",
              borderRadius:
                "18px",
              padding:
                "22px",
              position:
                "sticky",
              top: "100px",
            }}
          >
            <div
              style={{
                display:
                  "flex",
                justifyContent:
                  "space-between",
                alignItems:
                  "center",
              }}
            >
              <h2
                style={{
                  margin: 0,
                  fontSize:
                    "20px",
                }}
              >
                Your Cart
              </h2>

              <span
                style={{
                  background:
                    "#eaf3ff",
                  color:
                    "#1464c0",
                  borderRadius:
                    "999px",
                  padding:
                    "5px 9px",
                  fontSize:
                    "11px",
                  fontWeight:
                    "800",
                }}
              >
                {cart.reduce(
                  (total, item) =>
                    total +
                    item.quantity,
                  0
                )}
              </span>
            </div>

            {cart.length === 0 ? (
              <p
                style={{
                  color:
                    "#6680a0",
                  lineHeight:
                    1.5,
                  marginTop:
                    "22px",
                }}
              >
                Your cart is empty.
                Add a product to begin
                checkout.
              </p>
            ) : (
              <>
                <div
                  style={{
                    marginTop:
                      "20px",
                    display:
                      "flex",
                    flexDirection:
                      "column",
                    gap: "12px",
                  }}
                >
                  {cart.map(
                    (item) => (
                      <div
                        key={item.id}
                        style={{
                          display:
                            "flex",
                          justifyContent:
                            "space-between",
                          gap: "12px",
                          borderBottom:
                            "1px solid #edf1f5",
                          paddingBottom:
                            "12px",
                        }}
                      >
                        <div>
                          <strong
                            style={{
                              display:
                                "block",
                              fontSize:
                                "13px",
                            }}
                          >
                            {item.name}
                          </strong>

                          <span
                            style={{
                              color:
                                "#6680a0",
                              fontSize:
                                "12px",
                            }}
                          >
                            ₹
                            {item.price.toLocaleString(
                              "en-IN"
                            )}
                          </span>
                        </div>

                        <div
                          style={{
                            display:
                              "flex",
                            alignItems:
                              "center",
                            gap: "7px",
                          }}
                        >
                          <button
                            onClick={() =>
                              removeFromCart(
                                item.id
                              )
                            }
                            style={{
                              width:
                                "26px",
                              height:
                                "26px",
                              border:
                                "1px solid #d4dfeb",
                              background:
                                "#ffffff",
                              borderRadius:
                                "6px",
                              cursor:
                                "pointer",
                            }}
                          >
                            −
                          </button>

                          <strong>
                            {
                              item.quantity
                            }
                          </strong>

                          <button
                            onClick={() =>
                              addToCart(
                                item
                              )
                            }
                            style={{
                              width:
                                "26px",
                              height:
                                "26px",
                              border:
                                "1px solid #d4dfeb",
                              background:
                                "#ffffff",
                              borderRadius:
                                "6px",
                              cursor:
                                "pointer",
                            }}
                          >
                            +
                          </button>
                        </div>
                      </div>
                    )
                  )}
                </div>

                <div
                  style={{
                    marginTop:
                      "18px",
                    borderTop:
                      "1px solid #e1e8f0",
                    paddingTop:
                      "15px",
                  }}
                >
                  <div
                    style={{
                      display:
                        "flex",
                      justifyContent:
                        "space-between",
                      color:
                        "#6680a0",
                      fontSize:
                        "13px",
                    }}
                  >
                    <span>
                      Subtotal
                    </span>

                    <span>
                      ₹
                      {cartTotal.toLocaleString(
                        "en-IN",
                        {
                          minimumFractionDigits:
                            2,
                        }
                      )}
                    </span>
                  </div>

                  <div
                    style={{
                      display:
                        "flex",
                      justifyContent:
                        "space-between",
                      color:
                        "#6680a0",
                      fontSize:
                        "13px",
                      marginTop:
                        "8px",
                    }}
                  >
                    <span>
                      Discount
                    </span>

                    <span>
                      −₹
                      {discountAmount.toLocaleString(
                        "en-IN",
                        {
                          minimumFractionDigits:
                            2,
                          maximumFractionDigits:
                            2,
                        }
                      )}
                    </span>
                  </div>

                  <div
                    style={{
                      display:
                        "flex",
                      justifyContent:
                        "space-between",
                      marginTop:
                        "13px",
                      fontSize:
                        "19px",
                    }}
                  >
                    <strong>
                      Total
                    </strong>

                    <strong>
                      ₹
                      {finalTotal.toLocaleString(
                        "en-IN",
                        {
                          minimumFractionDigits:
                            2,
                          maximumFractionDigits:
                            2,
                        }
                      )}
                    </strong>
                  </div>
                </div>

                <button
                  onClick={
                    openCheckout
                  }
                  style={{
                    width:
                      "100%",
                    marginTop:
                      "18px",
                    padding:
                      "13px",
                    border:
                      "none",
                    borderRadius:
                      "9px",
                    background:
                      "#1464c0",
                    color:
                      "#ffffff",
                    fontWeight:
                      "800",
                    cursor:
                      "pointer",
                  }}
                >
                  Proceed to Checkout →
                </button>
              </>
            )}
          </aside>
        </div>

        {/* ====================================================
            ORDER RESULT
            ==================================================== */}

        {orderResult && (
        <section
            style={{
            marginTop: "28px",
            background:
                orderResult.success
                ? "#f4fbf6"
                : "#fff6f6",
            border:
                orderResult.success
                ? "1px solid #cce4d2"
                : "1px solid #eccaca",
            borderRadius: "18px",
            padding: "30px",
            }}
        >
            {orderResult.success ? (
            <>
                <div
                style={{
                    color: "#21613a",
                    fontWeight: "800",
                    fontSize: "12px",
                    letterSpacing: "1.5px",
                }}
                >
                ORDER PLACED
                </div>

                <h2
                style={{
                    margin: "8px 0 10px",
                }}
                >
                Order received successfully
                </h2>

                <p
                style={{
                    color: "#536b88",
                    lineHeight: 1.6,
                    margin: 0,
                }}
                >
                Thank you for your order. Your order has
                been received successfully.
                </p>

                <div
                style={{
                    marginTop: "22px",
                    background: "#ffffff",
                    border: "1px solid #dce6f0",
                    borderRadius: "12px",
                    padding: "18px",
                }}
                >
                <span
                    style={{
                    display: "block",
                    fontSize: "11px",
                    color: "#6680a0",
                    letterSpacing: "1px",
                    marginBottom: "7px",
                    }}
                >
                    ORDER ID
                </span>

                <strong
                    style={{
                    fontSize: "18px",
                    color: "#12345b",
                    }}
                >
                    {orderResult.orderId}
                </strong>
                </div>

                <p
                style={{
                    marginTop: "18px",
                    marginBottom: 0,
                    color: "#6680a0",
                    fontSize: "13px",
                }}
                >
                Your order has been submitted for fulfillment.
                </p>
            </>
            ) : (
            <>
                <strong
                style={{
                    color: "#9a2f2f",
                }}
                >
                ORDER FAILED
                </strong>

                <p>
                {orderResult.message}
                </p>
            </>
            )}
        </section>
        )}
      </main>

      {/* ======================================================
          CHECKOUT MODAL
          ====================================================== */}

      {checkoutOpen && (
        <div
          onClick={() =>
            setCheckoutOpen(false)
          }
          style={{
            position:
              "fixed",
            inset: 0,
            background:
              "rgba(10, 28, 50, 0.48)",
            display:
              "flex",
            alignItems:
              "center",
            justifyContent:
              "center",
            padding:
              "20px",
            zIndex: 50,
          }}
        >
          <div
            onClick={(event) =>
              event.stopPropagation()
            }
            style={{
              width:
                "min(720px, 100%)",
              maxHeight:
                "90vh",
              overflow:
                "auto",
              background:
                "#ffffff",
              borderRadius:
                "20px",
              padding:
                "30px",
              boxShadow:
                "0 25px 70px rgba(0,0,0,0.2)",
            }}
          >
            <div
              style={{
                display:
                  "flex",
                justifyContent:
                  "space-between",
                alignItems:
                  "center",
              }}
            >
              <div>
                <div
                  style={{
                    fontSize:
                      "11px",
                    letterSpacing:
                      "1.5px",
                    color:
                      "#6680a0",
                  }}
                >
                  CHECKOUT
                </div>

                <h2
                  style={{
                    margin:
                      "6px 0 0",
                  }}
                >
                  Complete your order
                </h2>
              </div>

              <button
                onClick={() =>
                  setCheckoutOpen(false)
                }
                style={{
                  border:
                    "none",
                  background:
                    "#f1f5f9",
                  borderRadius:
                    "50%",
                  width:
                    "36px",
                  height:
                    "36px",
                  cursor:
                    "pointer",
                  fontSize:
                    "20px",
                }}
              >
                ×
              </button>
            </div>

            {/* CUSTOMER */}

            <div
              style={{
                marginTop:
                  "24px",
                background:
                  "#f7faff",
                border:
                  "1px solid #dce6f0",
                borderRadius:
                  "13px",
                padding:
                  "17px",
              }}
            >
              <strong>
                {customer.name}
              </strong>

              <div
                style={{
                  marginTop:
                    "5px",
                  color:
                    "#6680a0",
                  fontSize:
                    "13px",
                }}
              >
                Account{" "}
                {customer.id}
                {" • "}
                Device{" "}
                {customer.deviceId}
              </div>
            </div>

            {/* PAYMENT */}

            <div
              style={{
                marginTop:
                  "22px",
              }}
            >
              <label
                style={{
                  display:
                    "block",
                  fontSize:
                    "12px",
                  fontWeight:
                    "800",
                  letterSpacing:
                    "1px",
                  color:
                    "#6680a0",
                  marginBottom:
                    "9px",
                }}
              >
                PAYMENT METHOD
              </label>

              <div
                style={{
                  display:
                    "grid",
                  gridTemplateColumns:
                    "repeat(2, 1fr)",
                  gap: "10px",
                }}
              >
                {[
                  "COD",
                  "Prepaid",
                ].map(
                  (method) => (
                    <button
                      key={method}
                      onClick={() =>
                        setPaymentMethod(
                          method
                        )
                      }
                      style={{
                        padding:
                          "13px",
                        border:
                          paymentMethod ===
                          method
                            ? "2px solid #1464c0"
                            : "1px solid #d5e0eb",
                        background:
                          paymentMethod ===
                          method
                            ? "#f0f7ff"
                            : "#ffffff",
                        borderRadius:
                          "10px",
                        cursor:
                          "pointer",
                        textAlign:
                          "left",
                        fontWeight:
                          "700",
                        color:
                          "#12345b",
                      }}
                    >
                      {method}
                    </button>
                  )
                )}
              </div>
            </div>

            {/* SHIPPING */}

            <div
              style={{
                marginTop:
                  "20px",
              }}
            >
              <label
                style={{
                  display:
                    "block",
                  fontSize:
                    "12px",
                  fontWeight:
                    "800",
                  letterSpacing:
                    "1px",
                  color:
                    "#6680a0",
                  marginBottom:
                    "9px",
                }}
              >
                SHIPPING
              </label>

              <div
                style={{
                  display:
                    "grid",
                  gridTemplateColumns:
                    "repeat(2, 1fr)",
                  gap: "10px",
                }}
              >
                {[
                  "Standard",
                  "Express",
                ].map(
                  (method) => (
                    <button
                      key={method}
                      onClick={() =>
                        setShippingMethod(
                          method
                        )
                      }
                      style={{
                        padding:
                          "13px",
                        border:
                          shippingMethod ===
                          method
                            ? "2px solid #1464c0"
                            : "1px solid #d5e0eb",
                        background:
                          shippingMethod ===
                          method
                            ? "#f0f7ff"
                            : "#ffffff",
                        borderRadius:
                          "10px",
                        cursor:
                          "pointer",
                        textAlign:
                          "left",
                        fontWeight:
                          "700",
                        color:
                          "#12345b",
                      }}
                    >
                      {method}
                    </button>
                  )
                )}
              </div>
            </div>

            

            {/* TOTAL */}

            <div
              style={{
                marginTop:
                  "24px",
                background:
                  "#f7faff",
                border:
                  "1px solid #dce6f0",
                borderRadius:
                  "12px",
                padding:
                  "18px",
              }}
            >
              <div
                style={{
                  display:
                    "flex",
                  justifyContent:
                    "space-between",
                  color:
                    "#6680a0",
                  fontSize:
                    "13px",
                }}
              >
                <span>
                  Order total
                </span>

                <strong
                  style={{
                    color:
                      "#12345b",
                    fontSize:
                      "20px",
                  }}
                >
                  ₹
                  {finalTotal.toLocaleString(
                    "en-IN",
                    {
                      minimumFractionDigits:
                        2,
                    }
                  )}
                </strong>
              </div>
            </div>

            {/* PLACE ORDER */}

            <button
              onClick={
                placeOrder
              }
              disabled={
                placingOrder
              }
              style={{
                width:
                  "100%",
                marginTop:
                  "20px",
                padding:
                  "15px",
                border:
                  "none",
                borderRadius:
                  "10px",
                background:
                  placingOrder
                    ? "#8da8c5"
                    : "#1464c0",
                color:
                  "#ffffff",
                fontWeight:
                  "800",
                fontSize:
                  "15px",
                cursor:
                  placingOrder
                    ? "wait"
                    : "pointer",
              }}
            >
              {placingOrder
                ? "Sending to MarginGuard..."
                : "PLACE ORDER →"}
            </button>

            <p
              style={{
                textAlign:
                  "center",
                color:
                  "#7a8da5",
                fontSize:
                  "11px",
                lineHeight:
                  1.5,
                margin:
                  "12px 0 0",
              }}
            >
              Demo checkout. No real payment
              is processed.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default Store;