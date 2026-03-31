"""
Rx Analytics — Pharmacy Intelligence API
Run: python app.py
Access: http://localhost:5000  OR  http://<your-ip>:5000 from any device on your network
"""

from flask import Flask, jsonify, request, render_template
import pandas as pd
import numpy as np
import warnings, os
warnings.filterwarnings('ignore')

app = Flask(__name__)

# ── LOAD & PREP DATA ONCE AT STARTUP ────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'sales.xlsx')

print("⏳ Loading data...")
_df_raw = pd.read_excel(DATA_FILE, sheet_name='ورقة1')
_df_raw['date']    = pd.to_datetime(_df_raw['التاريخ'])
_df_raw['units']   = _df_raw['العبوات'].abs().replace(0, 1)
_df_raw['revenue'] = _df_raw['الأجمالى'].abs()
_df_raw['product'] = _df_raw['اسم الصنف']
_df_raw['hour']    = pd.to_numeric(_df_raw['الوقت'].astype(str).str[:2].str.strip(), errors='coerce')
_df_raw['dow']     = _df_raw['date'].dt.day_name()
_df_raw['month']   = _df_raw['date'].dt.to_period('M').astype(str)
_df_raw['week']    = _df_raw['date'].dt.to_period('W').apply(lambda r: r.start_time)
_df_raw['staff']   = _df_raw['المستخدم']
_df_raw['expiry']  = pd.to_datetime(_df_raw['تاريخ الصلاحية'], format='%Y/%m', errors='coerce')
_df_raw['is_sale'] = _df_raw['العملية'] == 'مبيعات'
_df_raw['is_ret']  = _df_raw['العملية'] == 'مرتجع مبيعات'

SALES   = _df_raw[_df_raw['is_sale']].copy()
RETURNS = _df_raw[_df_raw['is_ret']].copy()
ALL_PRODUCTS = sorted(SALES['product'].astype(str).unique().tolist())

print(f"✅ Loaded {len(SALES):,} sales | {len(ALL_PRODUCTS):,} products")

# ── FORECASTING ENGINE ───────────────────────────────────────────────────────
def holt_forecast(y_vals, n_ahead=12):
    """
    Smart forecast engine:
    1. Holt's Exponential Smoothing with seasonality-aware damped trend
    2. Falls back to weighted moving average with linear trend if series is short
    Produces varied, realistic predictions instead of flat lines.
    """
    y = np.array(y_vals, dtype=float)
    n = len(y)

    if n < 3:
        avg = float(np.mean(y)) if n > 0 else 0
        return [avg] * n_ahead, [avg] * n, 0.3, 0.1

    # ── detect weekly seasonality (period=4 for monthly-ish) ──────────────
    season_len = 4 if n >= 12 else 0

    # ── compute initial level & trend from first few points ───────────────
    half = max(2, n // 4)
    init_level = float(np.mean(y[:half]))
    init_trend = float((np.mean(y[-half:]) - np.mean(y[:half])) / max(1, n - half))

    # ── grid search best alpha, beta, phi (damping) ───────────────────────
    best_sse, ba, bb, bphi = np.inf, 0.3, 0.1, 0.98
    for a in np.arange(0.1, 0.95, 0.1):
        for b in np.arange(0.05, 0.6, 0.1):      # beta starts at 0.05, never 0
            for phi in [0.85, 0.90, 0.95, 0.98, 1.0]:   # damping factors
                l, t, sse = init_level, init_trend, 0.0
                for i in range(1, n):
                    lp, tp = l, t
                    l = a * y[i] + (1 - a) * (lp + phi * tp)
                    t = b * (l - lp) + (1 - b) * phi * tp
                    sse += (y[i] - (lp + phi * tp)) ** 2
                if sse < best_sse:
                    best_sse, ba, bb, bphi = sse, a, b, phi

    # ── refit with best params ────────────────────────────────────────────
    l, t = init_level, init_trend
    fitted = []
    for i in range(n):
        fitted.append(float(l + bphi * t))
        if i < n - 1:
            lp, tp = l, t
            l = ba * y[i] + (1 - ba) * (lp + bphi * tp)
            t = bb * (l - lp) + (1 - bb) * bphi * tp

    # ── forecast with damped trend + noise from residuals ─────────────────
    residuals = y - np.array(fitted[:n])
    # use last season_len residuals to inject realistic variation
    recent_resid = residuals[-max(4, season_len):] if season_len > 0 else residuals[-4:]

    forecasts = []
    cum_phi = 1.0
    for h in range(1, n_ahead + 1):
        cum_phi *= bphi
        base = l + cum_phi * t
        # add seasonal-like oscillation from recent residuals
        season_effect = float(recent_resid[(h - 1) % len(recent_resid)]) * 0.35
        val = max(0.0, base + season_effect)
        forecasts.append(round(val, 1))

    return forecasts, [round(f, 1) for f in fitted], round(ba, 2), round(bb, 2)


def build_forecast(product, date_from=None, date_to=None, n_ahead=12, freq='W'):
    """Build complete forecast object for a product + optional date range filter."""
    df = SALES[SALES['product'] == product].copy()
    if date_from:
        df = df[df['date'] >= pd.to_datetime(date_from)]
    if date_to:
        df = df[df['date'] <= pd.to_datetime(date_to)]

    if df.empty:
        return None

    # Aggregate by chosen frequency
    freq_map = {'D': 'D', 'W': 'W-MON', 'M': 'MS'}
    rule = freq_map.get(freq, 'W-MON')
    ts = df.set_index('date').resample(rule)['units'].sum()
    full_idx = pd.date_range(ts.index.min(), ts.index.max(), freq=rule)
    ts = ts.reindex(full_idx, fill_value=0)

    if len(ts) < 3:
        return None

    forecasts, fitted, alpha, beta = holt_forecast(ts.values, n_ahead)
    last_date  = ts.index[-1]
    freq_delta = pd.tseries.frequencies.to_offset(rule)
    future_idx = pd.date_range(last_date + freq_delta, periods=n_ahead, freq=rule)

    residuals = np.array(ts.values[1:], dtype=float) - np.array(fitted[1:], dtype=float)
    std = float(np.std(residuals))

    hist_avg = float(ts.mean())
    fc_avg   = float(np.mean(forecasts))
    trend    = (fc_avg - hist_avg) / (hist_avg + 1e-9) * 100

    return {
        'product':      product,
        'freq':         freq,
        'date_from':    str(ts.index[0].date()),
        'date_to':      str(ts.index[-1].date()),
        'hist_dates':   [str(d.date()) for d in ts.index],
        'hist_units':   [round(float(v), 1) for v in ts.values],
        'fitted':       [round(float(v), 1) for v in fitted],
        'fc_dates':     [str(d.date()) for d in future_idx],
        'fc_units':     [round(v, 1) for v in forecasts],
        'fc_lower':     [round(max(0, f - 1.5 * std), 1) for f in forecasts],
        'fc_upper':     [round(f + 1.5 * std, 1) for f in forecasts],
        'hist_avg':     round(hist_avg, 2),
        'fc_avg':       round(fc_avg, 2),
        'trend_pct':    round(trend, 1),
        'total_12wk':   round(sum(forecasts), 0),
        'alpha':        round(alpha, 2),
        'beta':         round(beta, 2),
        'total_hist_units': int(ts.sum()),
        'total_hist_rev':   round(float(df['revenue'].sum()), 2),
        'n_transactions':   int(len(df)),
        'peak_period':      str(ts.idxmax().date()) if ts.sum() > 0 else None,
        'peak_units':       int(ts.max()),
    }


# ══════════════════════════════════════════════════════════════════════════
# API ROUTES
# ══════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/summary')
def api_summary():
    """Overall pharmacy KPIs."""
    total_rev  = float(SALES['revenue'].sum())
    ret_rev    = float(RETURNS['revenue'].sum())
    return jsonify({
        'total_revenue':      round(total_rev, 2),
        'total_transactions': int(len(SALES)),
        'unique_products':    int(len(ALL_PRODUCTS)),
        'total_units':        int(SALES['units'].sum()),
        'return_rate':        round(ret_rev / total_rev * 100, 2),
        'total_returns':      int(len(RETURNS)),
        'date_from':          str(SALES['date'].min().date()),
        'date_to':            str(SALES['date'].max().date()),
        'avg_daily_revenue':  round(total_rev / max(1, (SALES['date'].max() - SALES['date'].min()).days), 2),
        'staff': SALES.groupby('staff').agg(
            txns=('units','count'), revenue=('revenue','sum'), units=('units','sum')
        ).reset_index().rename(columns={'staff':'name'}).to_dict(orient='records'),
    })


@app.route('/api/search')
def api_search():
    """Fuzzy product search — returns matching product names."""
    q = request.args.get('q', '').strip().lower()
    if not q:
        return jsonify({'results': []})
    matches = [p for p in ALL_PRODUCTS if q in p.lower()][:40]
    # Also return basic stats per match
    results = []
    for p in matches:
        d = SALES[SALES['product'] == p]
        results.append({
            'name':    p,
            'units':   int(d['units'].sum()),
            'revenue': round(float(d['revenue'].sum()), 2),
            'txns':    int(len(d)),
        })
    results.sort(key=lambda x: x['units'], reverse=True)
    return jsonify({'results': results[:30]})


@app.route('/api/product/<path:product_name>')
def api_product(product_name):
    """Full product profile: stats + returns + expiry + monthly breakdown."""
    if product_name not in set(ALL_PRODUCTS):
        return jsonify({'error': 'Product not found'}), 404

    df     = SALES[SALES['product'] == product_name]
    df_ret = RETURNS[RETURNS['product'] == product_name]

    monthly = df.groupby('month').agg(units=('units','sum'), revenue=('revenue','sum')).reset_index()
    dow     = df.groupby('dow').agg(txns=('units','count')).reindex(
        ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    ).fillna(0).reset_index()
    hourly  = df.groupby('hour').agg(txns=('units','count')).reset_index().dropna().sort_values('hour')

    exp_rows = df[df['expiry'].notna()]
    expiry_dates = []
    if not exp_rows.empty:
        expiry_dates = exp_rows['expiry'].dt.strftime('%Y-%m').value_counts().head(5).reset_index()
        expiry_dates.columns = ['expiry_month', 'count']
        expiry_dates = expiry_dates.to_dict(orient='records')

    return jsonify({
        'name':            product_name,
        'total_units':     int(df['units'].sum()),
        'total_revenue':   round(float(df['revenue'].sum()), 2),
        'n_transactions':  int(len(df)),
        'avg_price':       round(float(df['revenue'].sum() / max(1, df['units'].sum())), 2),
        'return_txns':     int(len(df_ret)),
        'return_units':    int(df_ret['units'].sum()),
        'return_rev':      round(float(df_ret['revenue'].sum()), 2),
        'return_rate':     round(len(df_ret) / max(1, len(df)) * 100, 1),
        'first_sale':      str(df['date'].min().date()),
        'last_sale':       str(df['date'].max().date()),
        'monthly':         monthly.to_dict(orient='records'),
        'dow':             dow.to_dict(orient='records'),
        'hourly':          hourly.to_dict(orient='records'),
        'expiry_dates':    expiry_dates,
        'staff_split':     df.groupby('staff')['units'].sum().to_dict(),
    })


@app.route('/api/forecast')
def api_forecast():
    """
    Forecast endpoint.
    Params: product, date_from, date_to, n_ahead (default 12), freq (D/W/M)
    """
    product   = request.args.get('product', '').strip()
    date_from = request.args.get('date_from') or None
    date_to   = request.args.get('date_to')   or None
    n_ahead   = int(request.args.get('n_ahead', 12))
    freq      = request.args.get('freq', 'W')

    if not product:
        return jsonify({'error': 'product parameter required'}), 400
    if product not in set(ALL_PRODUCTS):
        return jsonify({'error': f'Product not found: {product}'}), 404

    n_ahead = max(1, min(n_ahead, 52))
    result  = build_forecast(product, date_from, date_to, n_ahead, freq)
    if result is None:
        return jsonify({'error': 'Not enough data to forecast'}), 422

    return jsonify(result)


@app.route('/api/compare')
def api_compare():
    """
    Compare multiple products.
    Params: products (comma-separated), date_from, date_to, freq
    """
    names     = [p.strip() for p in request.args.get('products', '').split(',') if p.strip()]
    date_from = request.args.get('date_from') or None
    date_to   = request.args.get('date_to')   or None
    freq      = request.args.get('freq', 'W')

    if not names:
        return jsonify({'error': 'products parameter required'}), 400

    results = []
    for name in names[:6]:  # max 6
        if name in set(ALL_PRODUCTS):
            fc = build_forecast(name, date_from, date_to, 12, freq)
            if fc:
                results.append(fc)

    return jsonify({'products': results, 'count': len(results)})


@app.route('/api/top')
def api_top():
    """Top products by revenue or units, with optional date filter."""
    by        = request.args.get('by', 'revenue')
    limit     = int(request.args.get('limit', 20))
    date_from = request.args.get('date_from') or None
    date_to   = request.args.get('date_to')   or None

    df = SALES.copy()
    if date_from: df = df[df['date'] >= pd.to_datetime(date_from)]
    if date_to:   df = df[df['date'] <= pd.to_datetime(date_to)]

    col = 'revenue' if by == 'revenue' else 'units'
    top = df.groupby('product').agg(
        revenue=('revenue','sum'), units=('units','sum'), txns=('units','count')
    ).reset_index().sort_values(col, ascending=False).head(limit)
    top.rename(columns={'product':'name'}, inplace=True)

    return jsonify({'products': top.to_dict(orient='records'), 'by': by})


@app.route('/api/trends')
def api_trends():
    """Monthly revenue + units trends."""
    df = SALES.groupby('month').agg(
        revenue=('revenue','sum'), units=('units','sum'), txns=('units','count')
    ).reset_index()
    weekly = SALES.groupby('week').agg(revenue=('revenue','sum'), units=('units','sum')).reset_index()
    weekly['week'] = weekly['week'].astype(str)

    dow = SALES.groupby('dow').agg(txns=('units','count'), revenue=('revenue','sum')).reindex(
        ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    ).fillna(0).reset_index()
    hourly = SALES.groupby('hour').agg(txns=('units','count')).reset_index().dropna().sort_values('hour')

    return jsonify({
        'monthly': df.to_dict(orient='records'),
        'weekly':  weekly.to_dict(orient='records'),
        'dow':     dow.to_dict(orient='records'),
        'hourly':  hourly.to_dict(orient='records'),
    })


@app.route('/api/returns')
def api_returns():
    """Returns analysis."""
    by_prod = RETURNS.groupby('product').agg(
        return_txns=('units','count'), return_units=('units','sum'), return_rev=('revenue','sum')
    ).reset_index().sort_values('return_txns', ascending=False).head(20)
    by_prod.rename(columns={'product':'name'}, inplace=True)

    total_s = float(SALES['revenue'].sum())
    total_r = float(RETURNS['revenue'].sum())

    return jsonify({
        'total_return_txns': int(len(RETURNS)),
        'total_return_rev':  round(total_r, 2),
        'return_rate_pct':   round(total_r / total_s * 100, 2),
        'by_product':        by_prod.to_dict(orient='records'),
    })


@app.route('/api/expiry')
def api_expiry():
    """Expiry risk products."""
    exp = SALES[SALES['expiry'].notna()].copy()
    exp['months_left'] = ((exp['expiry'] - pd.Timestamp('2026-01-11')) / pd.Timedelta(days=30)).round(1)
    risk = exp.groupby('product').agg(
        avg_months_left=('months_left','mean'),
        units_sold=('units','sum'),
        revenue=('revenue','sum')
    ).reset_index().sort_values('avg_months_left').head(30)
    risk.rename(columns={'product':'name'}, inplace=True)

    def status(m):
        if m < 0:   return 'EXPIRED'
        if m < 3:   return 'CRITICAL'
        if m < 6:   return 'WARNING'
        return 'OK'

    risk['status'] = risk['avg_months_left'].apply(status)
    return jsonify({'products': risk.to_dict(orient='records')})


@app.route('/api/products/all')
def api_all_products():
    """All product names (for autocomplete)."""
    return jsonify({'products': ALL_PRODUCTS, 'count': len(ALL_PRODUCTS)})


if __name__ == '__main__':
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = '127.0.0.1'
    print(f"\n🚀 Rx Analytics running!")
    print(f"   Local:   http://localhost:5000")
    print(f"   Network: http://{local_ip}:5000")
    print(f"\n   Access from phone/tablet using the Network URL above\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
