import math

import numpy as np
import pytest
from scipy.optimize import minimize

from optimizer import Infeasible, Network, allocate, allocate_for_profit, load_csv, project_arpu

NETS = load_csv("data/sample_networks.csv")
BUDGET = 10_000_000


def test_cpi_rises_by_the_stated_step():
    for n in NETS:
        g = {"ad_network": 0.10, "dsp": 0.15, "social": 0.20}[n.type]
        assert n.cpi_at(125_000) == pytest.approx(n.cpi * (1 + g))
        assert n.cpi_at(100_000) == pytest.approx(n.cpi)


def test_budget_is_spent_and_roas_target_met():
    a = allocate(NETS, BUDGET, 1.0, 30)
    assert sum(a.spend) == pytest.approx(BUDGET)
    assert a.roas == pytest.approx(1.0, abs=1e-6)
    assert a.roas_binding


def test_matches_a_general_purpose_solver():
    """The closed-form answer should equal what scipy's SLSQP finds from many starts."""
    a = allocate(NETS, BUDGET, 1.0, 30)
    arpu = np.array([n.arpu_at(30) for n in NETS])
    inst = lambda x: np.array([n.installs(max(v, 0) * 1e6) for n, v in zip(NETS, x)])
    cons = [{"type": "eq", "fun": lambda x: x.sum() - BUDGET / 1e6},
            {"type": "ineq", "fun": lambda x: ((inst(x) * arpu).sum() - x.sum() * 1e6) / 1e6}]
    best = None
    for seed in range(30):
        x0 = np.random.default_rng(seed).dirichlet(np.ones(len(NETS))) * BUDGET / 1e6
        r = minimize(lambda x: -inst(x).sum() / 1e5, x0, bounds=[(1e-6, BUDGET / 1e6)] * len(NETS),
                     constraints=cons, method="SLSQP", options={"maxiter": 1000, "ftol": 1e-12})
        if r.success and (best is None or r.fun < best.fun):
            best = r
    assert a.total_installs == pytest.approx(-best.fun * 1e5, rel=1e-5)


def test_non_binding_roas_gives_the_unconstrained_optimum():
    a = allocate(NETS, BUDGET, 0.5, 30)
    assert not a.roas_binding and a.roas > 0.5
    # without the rule, one more dollar buys the same number of installs everywhere
    marginal = [n.k * n.a * s ** (n.a - 1) for n, s in zip(NETS, a.spend)]
    assert max(marginal) == pytest.approx(min(marginal), rel=1e-6)


def test_impossible_target_is_reported():
    with pytest.raises(Infeasible):
        allocate(NETS, BUDGET, 50.0, 30)


def test_profit_mode_equalizes_marginal_return():
    a = allocate_for_profit(NETS, BUDGET, 180)
    marginal = [n.arpu_at(180) * n.k * n.a * s ** (n.a - 1) for n, s in zip(NETS, a.spend)]
    assert max(marginal) == pytest.approx(min(marginal), rel=1e-6)
    assert a.budget <= BUDGET * (1 + 1e-9)


def test_profit_mode_stops_when_dollars_stop_paying_back():
    small = [Network("Only", "social", 10.0, {7: 1, 30: 2, 90: 3})]  # ROAS < 1 at any spend
    a = allocate_for_profit(small, BUDGET, 90)
    assert a.budget < BUDGET


def test_projection_follows_a_power_curve():
    arpu = {d: 2.0 * d ** 0.5 for d in (7, 15, 30, 60, 90)}
    assert project_arpu(arpu, 180) == pytest.approx(2.0 * math.sqrt(180))
