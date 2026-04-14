"""Density-Response Curve Analysis (WS1 / run_024_p2b_framework).

Reads density_scores.json from run_021, fits four curve models to the
investigability vs log_min_density relationship, computes AIC/BIC, and
writes output JSON and interactive HTML plot.

Usage:
    python3 src/scientific_hypothesis/density_response_analysis.py
"""

import json
import math
import random
import os
from collections import defaultdict
from typing import List, Dict, Tuple, Any

SEED = 42
random.seed(SEED)

DATA_PATH = "runs/run_021_density_ceiling/density_scores.json"
OUT_DIR = "runs/run_024_p2b_framework"
JSON_OUT = os.path.join(OUT_DIR, "density_response_curve.json")
HTML_OUT = os.path.join(OUT_DIR, "plots", "density_response.html")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_filtered_data(path: str) -> List[Dict[str, Any]]:
    """Load and filter records to C1_compose and C2_multi_op methods only."""
    with open(path) as f:
        records = json.load(f)
    allowed = {"C1_compose", "C2_multi_op"}
    filtered = [r for r in records if r["method"] in allowed]
    return filtered


# ---------------------------------------------------------------------------
# Binning
# ---------------------------------------------------------------------------

def quantile_bins(data: List[Dict], n_bins: int = 10) -> List[Dict[str, Any]]:
    """Split data into n_bins quantile bins by log_min_density.

    Returns list of bin dicts with n_total, n_investigated,
    investigability_rate, mean_log_density, bin_range.
    """
    sorted_data = sorted(data, key=lambda r: r["log_min_density"])
    n = len(sorted_data)
    bins = []
    bin_size = n / n_bins
    for i in range(n_bins):
        start = int(round(i * bin_size))
        end = int(round((i + 1) * bin_size))
        chunk = sorted_data[start:end]
        if not chunk:
            continue
        log_vals = [r["log_min_density"] for r in chunk]
        inv = [r["investigated"] for r in chunk]
        n_total = len(chunk)
        n_inv = sum(inv)
        bins.append({
            "bin": i + 1,
            "n_total": n_total,
            "n_investigated": n_inv,
            "investigability_rate": n_inv / n_total,
            "mean_log_density": sum(log_vals) / n_total,
            "bin_range": [min(log_vals), max(log_vals)],
            "min_density_range": [
                min(r["min_density"] for r in chunk),
                max(r["min_density"] for r in chunk),
            ],
        })
    return bins


# ---------------------------------------------------------------------------
# OLS helpers
# ---------------------------------------------------------------------------

def _mean(vals: List[float]) -> float:
    """Return arithmetic mean."""
    return sum(vals) / len(vals)


def ols_linear(xs: List[float], ys: List[float]) -> Tuple[float, float]:
    """Fit y = a*x + b via closed-form OLS normal equations.

    Returns (a, b).
    """
    n = len(xs)
    mx, my = _mean(xs), _mean(ys)
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    a = num / den if den != 0 else 0.0
    b = my - a * mx
    return a, b


def rss(preds: List[float], ys: List[float]) -> float:
    """Residual sum of squares."""
    return sum((p - y) ** 2 for p, y in zip(preds, ys))


def log_likelihood_bernoulli(preds: List[float], ys: List[float]) -> float:
    """Bernoulli log-likelihood for binary outcomes."""
    eps = 1e-9
    return sum(
        y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps))
        for p, y in zip(preds, ys)
    )


def aic_bic(loglik: float, k: int, n: int) -> Tuple[float, float]:
    """Return (AIC, BIC) given log-likelihood, param count, sample size."""
    aic = 2 * k - 2 * loglik
    bic = k * math.log(n) - 2 * loglik
    return aic, bic


# ---------------------------------------------------------------------------
# Model fitting
# ---------------------------------------------------------------------------

def fit_linear(xs: List[float], ys: List[float]) -> Dict[str, Any]:
    """Fit linear model y_hat = a*x + b, clamped to [0, 1]."""
    a, b = ols_linear(xs, ys)
    preds = [max(0.0, min(1.0, a * x + b)) for x in xs]
    r = rss(preds, ys)
    ll = log_likelihood_bernoulli(preds, ys)
    k = 2
    aic, bic = aic_bic(ll, k, len(ys))
    return {"params": {"a": a, "b": b}, "preds": preds, "rss": r,
            "loglik": ll, "aic": aic, "bic": bic, "k": k}


def fit_piecewise(xs: List[float], ys: List[float]) -> Dict[str, Any]:
    """Fit piecewise threshold: y = p_high if x >= tau else p_low.

    Grid search over all unique x values. Returns best tau by RSS.
    """
    unique_xs = sorted(set(xs))
    best_rss = math.inf
    best_tau = unique_xs[0]
    best_p_high = 1.0
    best_p_low = 0.0
    best_preds: List[float] = []

    for tau in unique_xs:
        high_ys = [ys[i] for i in range(len(xs)) if xs[i] >= tau]
        low_ys = [ys[i] for i in range(len(xs)) if xs[i] < tau]
        p_high = _mean(high_ys) if high_ys else 1.0
        p_low = _mean(low_ys) if low_ys else 0.0
        preds = [p_high if x >= tau else p_low for x in xs]
        r = rss(preds, ys)
        if r < best_rss:
            best_rss = r
            best_tau = tau
            best_p_high = p_high
            best_p_low = p_low
            best_preds = preds

    ll = log_likelihood_bernoulli(best_preds, ys)
    k = 3  # tau, p_high, p_low
    aic, bic = aic_bic(ll, k, len(ys))
    return {
        "tau_log": best_tau,
        "tau_original": 10 ** best_tau,
        "p_low": best_p_low,
        "p_high": best_p_high,
        "preds": best_preds,
        "rss": best_rss,
        "loglik": ll,
        "aic": aic,
        "bic": bic,
        "k": k,
    }


def fit_saturating(xs: List[float], ys: List[float]) -> Dict[str, Any]:
    """Fit saturating model y_hat = 1 - exp(-a * x).

    Grid search a in [0.01, 5.0] with 500 steps.
    """
    steps = 500
    a_min, a_max = 0.01, 5.0
    best_rss_val = math.inf
    best_a = a_min
    best_preds: List[float] = []

    for i in range(steps):
        a = a_min + (a_max - a_min) * i / (steps - 1)
        preds = [max(0.0, min(1.0, 1 - math.exp(-a * x))) for x in xs]
        r = rss(preds, ys)
        if r < best_rss_val:
            best_rss_val = r
            best_a = a
            best_preds = preds

    ll = log_likelihood_bernoulli(best_preds, ys)
    k = 1
    aic, bic = aic_bic(ll, k, len(ys))
    return {"a": best_a, "preds": best_preds, "rss": best_rss_val,
            "loglik": ll, "aic": aic, "bic": bic, "k": k}


def fit_sigmoid(xs: List[float], ys: List[float]) -> Dict[str, Any]:
    """Fit sigmoid y_hat = 1 / (1 + exp(-k*(x - x0))).

    Grid search k in [0.5, 10.0] (50 steps), x0 in [min_x, max_x] (50 steps).
    """
    k_steps, x0_steps = 50, 50
    k_min, k_max = 0.5, 10.0
    x_min, x_max = min(xs), max(xs)
    best_rss_val = math.inf
    best_k, best_x0 = k_min, _mean(xs)
    best_preds: List[float] = []

    for ki in range(k_steps):
        k_val = k_min + (k_max - k_min) * ki / (k_steps - 1)
        for xi in range(x0_steps):
            x0 = x_min + (x_max - x_min) * xi / (x0_steps - 1)
            preds = [1 / (1 + math.exp(-k_val * (x - x0))) for x in xs]
            r = rss(preds, ys)
            if r < best_rss_val:
                best_rss_val = r
                best_k = k_val
                best_x0 = x0
                best_preds = preds

    ll = log_likelihood_bernoulli(best_preds, ys)
    k = 2
    aic, bic = aic_bic(ll, k, len(ys))
    return {"k": best_k, "x0": best_x0, "preds": best_preds,
            "rss": best_rss_val, "loglik": ll, "aic": aic, "bic": bic, "k_params": k}


# ---------------------------------------------------------------------------
# Good operating zone
# ---------------------------------------------------------------------------

def find_threshold_x(model_name: str, model: Dict, target: float,
                     x_min: float, x_max: float) -> Tuple[float, float]:
    """Find minimum log_density x* where predicted investigability >= target.

    Scans 1000 points across [x_min, x_max]. Returns (log_density, density).
    """
    steps = 1000
    for i in range(steps):
        x = x_min + (x_max - x_min) * i / (steps - 1)
        pred = _predict(model_name, model, x)
        if pred >= target:
            return x, 10 ** x
    return float("nan"), float("nan")


def _predict(model_name: str, model: Dict, x: float) -> float:
    """Predict investigability at x for the given model."""
    if model_name == "linear":
        a = model["params"]["a"]
        b = model["params"]["b"]
        return max(0.0, min(1.0, a * x + b))
    elif model_name == "piecewise":
        return model["p_high"] if x >= model["tau_log"] else model["p_low"]
    elif model_name == "saturating":
        return max(0.0, min(1.0, 1 - math.exp(-model["a"] * x)))
    elif model_name == "sigmoid":
        return 1 / (1 + math.exp(-model["k"] * (x - model["x0"])))
    return float("nan")


# ---------------------------------------------------------------------------
# Curve points for plotting
# ---------------------------------------------------------------------------

def model_curve_points(model_name: str, model: Dict,
                       x_min: float, x_max: float,
                       n: int = 200) -> List[Tuple[float, float]]:
    """Return list of (x, y) pairs for a fitted curve."""
    pts = []
    for i in range(n):
        x = x_min + (x_max - x_min) * i / (n - 1)
        y = _predict(model_name, model, x)
        pts.append((x, y))
    return pts


# ---------------------------------------------------------------------------
# Piecewise threshold analysis
# ---------------------------------------------------------------------------

def piecewise_threshold_analysis(model: Dict, data: List[Dict]) -> Dict:
    """Compute delta_investigability at Youden threshold (tau=7497, log=3.875)."""
    youden_log = math.log10(7497)
    xs = [r["log_min_density"] for r in data]
    ys = [r["investigated"] for r in data]
    p_high_at_youden = _mean([ys[i] for i in range(len(xs)) if xs[i] >= youden_log]) or 0.0
    p_low_at_youden = _mean([ys[i] for i in range(len(xs)) if xs[i] < youden_log]) or 0.0
    delta = p_high_at_youden - p_low_at_youden
    return {
        "youden_tau": 7497,
        "youden_tau_log": round(youden_log, 4),
        "p_high_at_youden": round(p_high_at_youden, 4),
        "p_low_at_youden": round(p_low_at_youden, 4),
        "delta_at_youden": round(delta, 4),
    }


# ---------------------------------------------------------------------------
# HTML plot generation
# ---------------------------------------------------------------------------

def _round(v: Any, d: int = 6) -> Any:
    """Round float or pass through non-float."""
    if isinstance(v, float):
        return round(v, d)
    return v


def generate_html(data: List[Dict], bins: List[Dict],
                  models: Dict, best_model: str,
                  x_min: float, x_max: float) -> str:
    """Generate self-contained interactive HTML with scatter + curve overlay + bar chart."""
    random.seed(SEED)

    c1 = [r for r in data if r["method"] == "C1_compose"]
    c2 = [r for r in data if r["method"] == "C2_multi_op"]

    def jitter() -> float:
        return (random.random() - 0.5) * 0.04

    c1_pts = [[r["log_min_density"], r["investigated"] + jitter()] for r in c1]
    c2_pts = [[r["log_min_density"], r["investigated"] + jitter()] for r in c2]

    curve_colors = {
        "linear": "#28a745",
        "piecewise": "#fd7e14",
        "saturating": "#6f42c1",
        "sigmoid": "#795548",
    }

    curves = {}
    for name in ["linear", "piecewise", "saturating", "sigmoid"]:
        pts = model_curve_points(name, models[name], x_min, x_max, 200)
        curves[name] = [[round(x, 4), round(y, 4)] for x, y in pts]

    best_tau = models["piecewise"]["tau_log"]

    bin_labels = [f"{b['bin_range'][0]:.2f}-{b['bin_range'][1]:.2f}" for b in bins]
    bin_rates = [b["investigability_rate"] for b in bins]
    bin_ns = [b["n_total"] for b in bins]

    data_js = json.dumps({
        "c1": c1_pts,
        "c2": c2_pts,
        "curves": curves,
        "best_tau": best_tau,
        "bin_labels": bin_labels,
        "bin_rates": bin_rates,
        "bin_ns": bin_ns,
        "best_model": best_model,
        "curve_colors": curve_colors,
    })

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Density-Response Curve — KG Discovery Engine</title>
<style>
  body {{ font-family: sans-serif; background: #f8f9fa; margin: 20px; }}
  h1 {{ color: #333; font-size: 18px; }}
  canvas {{ border: 1px solid #ccc; background: #fff; display: block; margin: 8px 0; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 4px 0 12px 0; font-size: 13px; }}
  .legend-item {{ display: flex; align-items: center; gap: 4px; }}
  .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
  .legend-line {{ width: 20px; height: 3px; }}
  #tooltip {{ position: fixed; background: rgba(0,0,0,0.75); color: #fff;
              padding: 4px 8px; border-radius: 4px; font-size: 12px;
              pointer-events: none; display: none; }}
</style>
</head>
<body>
<h1>Density-Response Curve Analysis</h1>
<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#1f77b4"></div> C1_compose</div>
  <div class="legend-item"><div class="legend-dot" style="background:#d62728"></div> C2_multi_op</div>
  <div class="legend-item"><div class="legend-line" style="background:#28a745"></div> Linear</div>
  <div class="legend-item"><div class="legend-line" style="background:#fd7e14"></div> Piecewise</div>
  <div class="legend-item"><div class="legend-line" style="background:#6f42c1"></div> Saturating</div>
  <div class="legend-item"><div class="legend-line" style="background:#795548"></div> Sigmoid</div>
  <div class="legend-item"><div class="legend-line" style="background:#333; border-top: 2px dashed #333"></div> Best threshold</div>
</div>
<canvas id="scatter" width="900" height="600"></canvas>
<canvas id="barchart" width="900" height="200"></canvas>
<div id="tooltip"></div>

<script>
const D = {data_js};

(function() {{
  const sc = document.getElementById('scatter');
  const ctx = sc.getContext('2d');
  const W = 900, H = 600;
  const pad = {{left: 70, right: 30, top: 30, bottom: 50}};
  const pw = W - pad.left - pad.right;
  const ph = H - pad.top - pad.bottom;

  const allX = D.c1.map(p=>p[0]).concat(D.c2.map(p=>p[0]));
  const xMin = Math.min(...allX) - 0.05;
  const xMax = Math.max(...allX) + 0.05;
  const yMin = -0.15, yMax = 1.15;

  function tx(x) {{ return pad.left + (x - xMin) / (xMax - xMin) * pw; }}
  function ty(y) {{ return pad.top + (1 - (y - yMin) / (yMax - yMin)) * ph; }}

  // Grid
  ctx.strokeStyle = '#eee'; ctx.lineWidth = 1;
  for (let gx = Math.ceil(xMin*2)/2; gx <= xMax; gx += 0.5) {{
    ctx.beginPath(); ctx.moveTo(tx(gx), pad.top); ctx.lineTo(tx(gx), pad.top + ph); ctx.stroke();
  }}
  for (let gy = 0; gy <= 1; gy += 0.25) {{
    ctx.beginPath(); ctx.moveTo(pad.left, ty(gy)); ctx.lineTo(pad.left + pw, ty(gy)); ctx.stroke();
  }}

  // Axes
  ctx.strokeStyle = '#333'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(pad.left, pad.top); ctx.lineTo(pad.left, pad.top + ph); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(pad.left, pad.top + ph); ctx.lineTo(pad.left + pw, pad.top + ph); ctx.stroke();

  // Axis labels
  ctx.fillStyle = '#333'; ctx.font = '12px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText('log\u2081\u2080(min_density)', W / 2, H - 8);
  ctx.save(); ctx.translate(14, H / 2); ctx.rotate(-Math.PI / 2);
  ctx.fillText('Investigated (0/1 + jitter)', 0, 0); ctx.restore();

  // X tick labels
  for (let gx = Math.ceil(xMin); gx <= xMax; gx += 1) {{
    ctx.fillText(gx.toFixed(0), tx(gx), pad.top + ph + 18);
  }}
  // Y tick labels
  ctx.textAlign = 'right';
  [0, 0.25, 0.5, 0.75, 1.0].forEach(v => {{
    ctx.fillText(v.toFixed(2), pad.left - 6, ty(v) + 4);
  }});

  // Dashed threshold line
  const tau = D.best_tau;
  ctx.setLineDash([6, 4]); ctx.strokeStyle = '#333'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(tx(tau), pad.top); ctx.lineTo(tx(tau), pad.top + ph); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#333'; ctx.textAlign = 'left'; ctx.font = '11px sans-serif';
  ctx.fillText('threshold', tx(tau) + 3, pad.top + 14);

  // Fitted curves
  const cnames = ['linear','piecewise','saturating','sigmoid'];
  cnames.forEach(name => {{
    const pts = D.curves[name];
    const col = D.curve_colors[name];
    const lw = name === D.best_model ? 3 : 1.5;
    ctx.strokeStyle = col; ctx.lineWidth = lw;
    ctx.beginPath();
    pts.forEach((p, i) => {{
      const px = tx(p[0]), py = ty(p[1]);
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }});
    ctx.stroke();
  }});

  // Scatter
  function drawDots(pts, color) {{
    pts.forEach(p => {{
      ctx.beginPath();
      ctx.arc(tx(p[0]), ty(p[1]), 4, 0, Math.PI * 2);
      ctx.fillStyle = color + '99';
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 0.8;
      ctx.stroke();
    }});
  }}
  drawDots(D.c1, '#1f77b4');
  drawDots(D.c2, '#d62728');

  // Title
  ctx.fillStyle = '#333'; ctx.font = 'bold 13px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText('Investigability vs log\u2081\u2080(min_density) — C1+C2 (n=140)', W/2, pad.top - 12);

  // --- Bar chart ---
  const bc = document.getElementById('barchart');
  const bctx = bc.getContext('2d');
  const BW = 900, BH = 200;
  const bpad = {{left: 70, right: 30, top: 30, bottom: 50}};
  const bpw = BW - bpad.left - bpad.right;
  const bph = BH - bpad.top - bpad.bottom;
  const nb = D.bin_labels.length;
  const bw = bpw / nb;

  bctx.fillStyle = '#333'; bctx.font = 'bold 13px sans-serif'; bctx.textAlign = 'center';
  bctx.fillText('Investigability Rate per Density Bin', BW/2, bpad.top - 10);

  bctx.strokeStyle = '#eee'; bctx.lineWidth = 1;
  [0, 0.25, 0.5, 0.75, 1.0].forEach(v => {{
    const y = bpad.top + (1 - v) * bph;
    bctx.beginPath(); bctx.moveTo(bpad.left, y); bctx.lineTo(bpad.left + bpw, y); bctx.stroke();
  }});

  D.bin_rates.forEach((rate, i) => {{
    const x = bpad.left + i * bw + 2;
    const barH = rate * bph;
    const y = bpad.top + bph - barH;
    // Color: green=high, red=low
    const r = Math.round(255 * (1 - rate));
    const g = Math.round(200 * rate);
    bctx.fillStyle = `rgb(${{r}},${{g}},60)`;
    bctx.fillRect(x, y, bw - 4, barH);
    bctx.strokeStyle = '#fff'; bctx.lineWidth = 1;
    bctx.strokeRect(x, y, bw - 4, barH);
    // Rate label
    bctx.fillStyle = '#333'; bctx.font = '10px sans-serif'; bctx.textAlign = 'center';
    bctx.fillText((rate * 100).toFixed(0) + '%', x + (bw-4)/2, Math.min(y - 2, bpad.top + bph - 2));
    // X label
    bctx.fillStyle = '#555'; bctx.font = '9px sans-serif';
    bctx.fillText(D.bin_labels[i].split('-')[0], x + (bw-4)/2, bpad.top + bph + 14);
    // n label
    bctx.fillStyle = '#888'; bctx.font = '9px sans-serif';
    bctx.fillText('n=' + D.bin_ns[i], x + (bw-4)/2, bpad.top + bph + 26);
  }});

  // Y axis bar chart
  bctx.strokeStyle = '#333'; bctx.lineWidth = 1.5;
  bctx.beginPath(); bctx.moveTo(bpad.left, bpad.top); bctx.lineTo(bpad.left, bpad.top + bph); bctx.stroke();
  bctx.textAlign = 'right'; bctx.font = '10px sans-serif'; bctx.fillStyle = '#333';
  [0, 0.5, 1.0].forEach(v => {{
    bctx.fillText(v.toFixed(1), bpad.left - 4, bpad.top + (1 - v) * bph + 4);
  }});
  bctx.save(); bctx.translate(14, BH/2); bctx.rotate(-Math.PI/2);
  bctx.fillText('Inv. Rate', 0, 0); bctx.restore();
}})();
</script>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run density-response curve analysis and write output files."""
    data = load_filtered_data(DATA_PATH)
    n_total = len(data)
    n_c1 = sum(1 for r in data if r["method"] == "C1_compose")
    n_c2 = sum(1 for r in data if r["method"] == "C2_multi_op")
    print(f"Loaded {n_total} records: C1={n_c1}, C2={n_c2}")

    xs = [r["log_min_density"] for r in data]
    ys = [r["investigated"] for r in data]
    x_min, x_max = min(xs), max(xs)

    # Binning
    bins = quantile_bins(data, n_bins=10)
    print(f"Bins: {len(bins)} quantile bins created")

    # Model fitting
    lin = fit_linear(xs, ys)
    pie = fit_piecewise(xs, ys)
    sat = fit_saturating(xs, ys)
    sig = fit_sigmoid(xs, ys)

    models_map = {
        "linear": lin,
        "piecewise": pie,
        "saturating": sat,
        "sigmoid": sig,
    }

    # Best model by AIC
    best_model = min(models_map, key=lambda n: models_map[n]["aic"])
    print(f"Best model by AIC: {best_model}")
    for name, m in models_map.items():
        print(f"  {name:12s} AIC={m['aic']:.2f} BIC={m['bic']:.2f} RSS={m['rss']:.4f}")

    # Good operating zone (using best model)
    best = models_map[best_model]
    x95_log, x95_den = find_threshold_x(best_model, best, 0.95, x_min, x_max)
    x99_log, x99_den = find_threshold_x(best_model, best, 0.99, x_min, x_max)
    print(f"Good operating zone (best={best_model}):")
    print(f"  >= 0.95: log={x95_log:.4f}, density={x95_den:.1f}")
    print(f"  >= 0.99: log={x99_log:.4f}, density={x99_den:.1f}")

    # Piecewise threshold analysis
    pw_analysis = piecewise_threshold_analysis(pie, data)
    print(f"Piecewise: tau_log={pie['tau_log']:.4f}, tau_orig={pie['tau_original']:.1f}")
    print(f"  delta_at_youden={pw_analysis['delta_at_youden']:.4f}")

    def _clean_model(name: str, m: Dict) -> Dict:
        """Return model dict without prediction list for JSON output."""
        out = {k: v for k, v in m.items() if k not in ("preds",)}
        # Round floats
        return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in out.items()}

    result = {
        "n_total": n_total,
        "n_c1": n_c1,
        "n_c2": n_c2,
        "bins": [
            {k: (_round(v) if isinstance(v, float) else v) for k, v in b.items()}
            for b in bins
        ],
        "models": {
            "linear": _clean_model("linear", lin),
            "piecewise": _clean_model("piecewise", pie),
            "saturating": _clean_model("saturating", sat),
            "sigmoid": _clean_model("sigmoid", sig),
        },
        "best_model": best_model,
        "good_operating_zone": {
            "threshold_095": {
                "log_density": round(x95_log, 4) if not math.isnan(x95_log) else None,
                "density": round(x95_den, 1) if not math.isnan(x95_den) else None,
            },
            "threshold_099": {
                "log_density": round(x99_log, 4) if not math.isnan(x99_log) else None,
                "density": round(x99_den, 1) if not math.isnan(x99_den) else None,
            },
        },
        "piecewise_threshold_analysis": pw_analysis,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, "plots"), exist_ok=True)

    with open(JSON_OUT, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Written: {JSON_OUT}")

    html = generate_html(data, bins, models_map, best_model, x_min, x_max)
    with open(HTML_OUT, "w") as f:
        f.write(html)
    print(f"Written: {HTML_OUT}")


if __name__ == "__main__":
    main()
