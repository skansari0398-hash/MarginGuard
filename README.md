# MarginGuard

## AI-Powered Merchant Loss Prevention

MarginGuard is an AI/ML-powered merchant loss-prevention system that predicts e-commerce return risk, explains why an order is risky, and recommends the most economically appropriate intervention.

Instead of only asking **"Is this order risky?"**, MarginGuard asks:

> **"What should the merchant do about this risk?"**

---

## Problem

E-commerce merchants lose money through:

- Product returns
- Return-to-Origin (RTO)
- Reverse logistics
- Shipping and handling costs
- Inventory loss
- COD-related losses

Checking every order manually is expensive, while ignoring risk can lead to avoidable losses.

MarginGuard provides targeted, cost-sensitive intervention.

---

## How It Works

```text
Order
  ↓
21-Feature ML Model
  ↓
Return Risk Prediction
  ↓
Risk Explanation
  ↓
Device Intelligence
  ↓
Expected Loss Calculation
  ↓
Intervention Selection
  ↓
Merchant Approval
```

Possible interventions:

- No Action
- Customer Verification
- COD Confirmation
- Manual Review

---

## Key Features

### Return Risk Prediction
Predicts the probability that an order will be returned.

### Explainable Risk
Shows the features that increase or decrease the model's prediction.

### Device Intelligence
Provides device-level context including linked accounts, previous returns,
previous RTOs, and multi-account signals.

### Cost-Sensitive Intervention
Compares the expected loss of different interventions and recommends the
lowest expected-loss option.

### Seller Policy Engine
Allows merchant policies to influence the final operational decision.

### Live Orders
Orders placed through the demo store appear in the MarginGuard live order
queue for investigation.

### Merchant Action Center
The merchant can review and approve actions rather than allowing the system
to silently perform sensitive actions.

---

## Machine Learning Features

MarginGuard uses 21 order-level features:

- Customer age
- Account age
- Previous purchase count
- Previous return rate
- Previous RTO rate
- Product category
- Product price
- Product rating
- Discount percentage
- Payment method
- Shipping method
- Device type
- New device
- First order
- Coupon usage
- Session length
- Product views
- Estimated delivery time
- Delivery distance
- Order value
- Gross margin

---

## Server-Side Customer History

Customer history is maintained server-side and used to enrich incoming
orders before prediction.

Historical risk attributes are therefore not trusted directly from the
client.

This provides a stronger architecture for a real merchant-risk system.

---

## Model Evaluation

MarginGuard was evaluated using a chronological 80/20 evaluation:

- Total orders: **200,000**
- Development set: **160,000**
- Hold-out set: **40,000**
- Classification threshold: **0.50**

### Results

| Metric | Result |
|---|---:|
| Precision | **70.76%** |
| Recall | **94.58%** |
| F1 Score | **80.96%** |
| Accuracy | **69.39%** |
| ROC-AUC | **65.55%** |

### Confusion Matrix

| | Predicted Clear | Predicted Risky |
|---|---:|---:|
| Actually Clear | 1,739 | 10,751 |
| Actually Returned | 1,491 | 26,019 |

The system prioritizes recall because missing genuinely risky orders can
result in merchant losses.

The high false-positive rate is intentionally disclosed rather than hidden.

---

## Economic Evaluation

On the same 40,000-order evaluation set:

| Metric | Result |
|---|---:|
| Orders flagged risky | **36,770** |
| Risky-order rate | **91.93%** |
| Orders receiving intervention | **32,521** |
| Intervention rate | **81.30%** |
| Expected loss without action | **₹97,13,535.25** |
| Expected loss with MarginGuard | **₹87,36,371.84** |
| Simulated expected loss avoided | **₹9,77,163.40** |
| Average simulated loss avoided/order | **₹24.43** |

This represents an approximately **10.06% simulated reduction in expected
loss under the configured intervention assumptions**.

### Important Evaluation Note

The ₹9.77 lakh figure is **simulated expected loss avoided**, not measured
real-world merchant savings.

Intervention costs and effectiveness are currently configurable demo-stage
assumptions. A production system should estimate these effects from
historical intervention outcomes or controlled experiments.

---

## False-Positive Cost

The evaluation produced:

- False positives: **10,751**
- False-positive intervention cost: **₹3,80,798.94**
- Average false-positive intervention cost: **₹35.42**

MarginGuard explicitly considers false-positive cost because unnecessary
intervention also creates merchant and customer friction.

---

## Project Structure

```text
MarginGuard/
├── app.py
├── evaluate_model.py
├── evaluate_economics.py
├── evaluation_results/
│   ├── model_evaluation.txt
│   └── economic_evaluation.txt
├── data/
│   └── marginguard_synthetic_orders.csv
├── models/
│   └── marginguard_logistic_v1.pkl
├── src/
│   ├── actions/
│   ├── calibration/
│   ├── data/
│   ├── explainability/
│   ├── features/
│   ├── ingestion/
│   ├── intelligence/
│   ├── models/
│   └── policy/
├── frontend/
├── tests/
├── test_predictor.py
└── requirements.txt
```

---

## Running the Project

### Backend

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start FastAPI:

```bash
uvicorn app:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Reproducing the Evaluation

Run model evaluation:

```bash
python evaluate_model.py
```

Run economic evaluation:

```bash
python evaluate_economics.py
```

Results are saved in:

```text
evaluation_results/
```

---

## Design Philosophy

MarginGuard follows:

```text
Predict → Explain → Act → Quantify
```

The ML model identifies risk.

The explanation layer provides evidence.

The intervention engine considers economic cost.

The merchant remains in control of the final action.

---

## Limitations

- The current dataset is synthetic/simulated.
- Intervention effectiveness uses configurable demo assumptions.
- RTO risk is currently an interpretable operational estimate rather than a
  separately trained ML model.
- The current model has a high false-positive rate at the 0.50 threshold.
- Economic results are simulated and should not be interpreted as measured
  production savings.

---

## Future Improvements

- Merchant-specific model calibration
- Separately trained RTO model
- Learning intervention effectiveness from historical outcomes
- Controlled intervention experiments
- Dynamic threshold optimization
- Model drift detection
- Production webhook integration
- Persistent intervention history
- Merchant-specific policies
- Online model monitoring

---

## Razorpay AI Buildathon

**Track:** AI Risk Manager

MarginGuard focuses on preventing merchant losses caused by returns and
RTO-related operational costs.

The project demonstrates a complete risk-management loop:

```text
Risk Detection
      ↓
Risk Explanation
      ↓
Economic Decision
      ↓
Merchant Intervention
      ↓
Expected Loss Quantification
```

---

## Safety

MarginGuard is designed as a defensive merchant-risk system.

Sensitive operational actions in the demo require merchant interaction and are
not silently executed against external payment systems.

---

## Summary

**MarginGuard transforms return-risk prediction into an economically informed
merchant control system.**

It does not simply predict risk.

It helps answer:

> **Which orders should we intervene on, what should we do, and what is the
> expected economic impact?**