# UA Budget Optimizer

How should a mobile game split its launch budget across ad networks, DSPs and social networks?

Every extra dollar on a network buys installs at a higher CPI, so pouring everything into the cheapest channel stops working fast. This tool finds the split that gets the **most installs while keeping portfolio ROAS on target** within a payback window, or the split that earns the **most net revenue** by a later day.

**Try it in the browser:** https://myagizcaglar11.github.io/ua-budget-optimizer/

## The problem

```
maximize    total installs
subject to  total spend = budget
            revenue by day D  >=  target ROAS × budget
```

**Cost of scale.** Each +25% of spend on a network raises its CPI by a fixed step, compounding:

| Channel type | CPI step per +25% spend | Why |
|---|---|---|
| Ad networks | +10% | Large in-app inventory, scales most easily |
| DSPs | +15% | Programmatic bidding, moderate pressure |
| Social networks | +20% | Auction-based, gets expensive fastest |

So `CPI(B) = CPI0 × (B / B0)^e` with `e = ln(1 + step) / ln(1.25)`, and installs grow slower than spend.

**Revenue.** Each network has cumulative ARPU at days 1, 7, 15, 30, 60 and 90. Day 180 is projected with a power curve fitted to days 7–90 (an assumption, stated on the page).

## How it is solved

Installs are a concave function of spend, so there is exactly one best split. At that split, **one more dollar is worth the same on every network**, where "worth" counts installs plus a price on revenue that the ROAS rule sets:

```
(1 + λ × ARPU_i) × installs_i'(B_i) = μ      for every network i
```

For a given λ each network's spend has a closed form; μ is found by bisection so the budget adds up, and λ by bisection so ROAS lands exactly on the target (λ = 0 when the target is not binding). The same idea solves the profit mode: each network gets money until its next dollar returns the same by the window, and spending stops early if that return drops below one dollar.

**Checked against:**
- a general-purpose optimizer (SciPy SLSQP, 30 random starts): same answer to 5 significant figures (`tests/`);
- my earlier Excel Solver (GRG Nonlinear) solution to a marketing case study: the same allocation and install count, to the install.

## Run it

```bash
pip install -r requirements-dev.txt
python -m pytest -q                                   # tests
python -m optimizer                                   # sample data, $10M, 100% D30 ROAS
python -m optimizer --roas 1.2 --window 60
python -m optimizer --objective profit --window 180
python -m optimizer --data my_networks.csv --budget 5000000
```

The solver itself needs only the Python standard library; NumPy and SciPy are used in the tests.

CSV format (`data/sample_networks.csv`): `name,type,cpi,d1,d7,d15,d30,d60,d90`, with `type` = `ad_network`, `dsp` or `social`, and CPI/ARPU measured at a $100,000 baseline spend (optional `base_spend` column to change that).

The web page (`docs/index.html`) runs the same solver in JavaScript. A CSV you load there is read in your browser and never uploaded.

## Limits

- The sample networks and numbers are made up; real CPI curves are noisier and change week to week.
- One step size per channel type is a simplification; in practice each network, country and OS has its own curve.
- Day-180 ARPU is an extrapolation and can be far off for channels with unusual retention.
- No OS or country split: that would multiply the variables but not change the method.

## About

Built by Mehmet Yağız Çağlar (ITU Industrial Engineering) with the help of AI tools, as a follow-up to a performance marketing case study: turning an Excel Solver model into a tested, reusable tool. See also my [Match-3 Review Tracker](https://github.com/myagizcaglar11/review-tracker).
