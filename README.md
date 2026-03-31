# 💊 Rx Analytics — Pharmacy Intelligence Dashboard

A full local web app with a Python/Flask API backend and interactive dashboard.
Access it from **any device** on your network — PC, phone, tablet.

---

## 🚀 Quick Start

### 1. Install Python dependencies
```bash
pip install flask pandas numpy openpyxl
```

### 2. Generate sample data (for demo/testing)

> ⚠️ The real `sales.xlsx` file is not included in this repo (private business data).
> Run this to generate a realistic sample dataset with ~12,000 rows:

```bash
python generate_sample_data.py
```

This creates a `sales.xlsx` file with 20 products, 4 staff members, and 2 years of simulated transactions.

### 3. Make sure your data file is in the same folder
```
pharma_app/
├── app.py
├── sales.xlsx        ← your data file
├── requirements.txt
├── README.md
└── templates/
    └── index.html
```

### 3. Run the app
```bash
python app.py
```

### 4. Open in browser
- **This PC:**   http://localhost:5000
- **Phone/Tablet on same WiFi:**  http://YOUR-PC-IP:5000
  (The app prints your IP when it starts)

---

## ✨ Features

| Page | What it does |
|------|-------------|
| 📊 Overview | KPI cards, monthly revenue, top products, staff comparison |
| 🔍 Product Search | Search any product, filter by date range, see full profile + forecast |
| 🔮 Forecast | Pick product + date range + frequency (daily/weekly/monthly) + periods ahead |
| ⚖️ Compare | Add up to 6 products, compare side-by-side history + forecast |
| 💰 Revenue | Weekly timeline, top 15 by revenue, revenue vs volume scatter |
| ⏰ Patterns | Hourly sales, day-of-week, monthly seasonality |
| 🔄 Returns | Return rate, most returned products |
| ⚠️ Expiry Risk | Products expiring soon, color-coded urgency |

---

## 🔌 API Endpoints

You can also call the API directly from any app or script:

```
GET /api/summary                          → Overall KPIs
GET /api/search?q=BRUFEN                  → Search products
GET /api/product/{name}                   → Full product profile
GET /api/forecast?product=X&date_from=Y&date_to=Z&freq=W&n_ahead=12
GET /api/compare?products=A,B,C&date_from=Y&date_to=Z
GET /api/top?by=revenue&limit=20          → Top products
GET /api/trends                           → Time trends
GET /api/returns                          → Returns analysis
GET /api/expiry                           → Expiry risk
GET /api/products/all                     → All product names
```

---

## 📊 Model

Uses **Holt's Double Exponential Smoothing** with auto-tuned α and β parameters per product.
- Handles both level and trend
- Works well with weekly/daily/monthly pharmacy sales
- Provides confidence intervals (±1.5σ)

---

## 🛠 Tech Stack
- **Backend:** Python 3, Flask
- **Data:** Pandas, NumPy
- **Frontend:** Vanilla JS, Chart.js 4
- **Fonts:** Syne, JetBrains Mono, Outfit

---

*Built for a local pharmacy in Damanhur, Egypt — Feb 2025 → Jan 2026 data*
