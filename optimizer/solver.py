"""Split a budget across networks to get the most installs while keeping
portfolio ROAS at or above a target within a payback window.

    maximize    sum_i installs_i(B_i)
    subject to  sum_i B_i = budget
                sum_i ARPU_i(window) * installs_i(B_i) >= target_roas * budget

installs_i(B) = k_i * B^a_i with 0 < a_i < 1 is concave, so this is a convex
problem with one best answer. We find it from the optimality conditions:

    (1 + lam * ARPU_i) * installs_i'(B_i) = mu    for every network

In words: at the optimum, one more dollar is worth the same on every network,
where "worth" counts installs plus lam times the revenue they bring. lam is the
price of the ROAS rule: 0 when the rule does not bind, larger when it pushes
money toward high-ARPU networks. For a given lam, each B_i has a closed form;
mu is found by bisection so the budget adds up, and lam by bisection so ROAS
lands exactly on the target.
"""
from dataclasses import dataclass

from .model import Network


class Infeasible(ValueError):
    pass


def allocate_for_profit(nets: list[Network], budget: float, window: int = 180) -> "Allocation":
    """Maximize net revenue (revenue by the window minus spend), spending at most the budget.

        maximize  sum_i ARPU_i * installs_i(B_i) - B_i    subject to  sum_i B_i <= budget

    Optimality: ARPU_i * installs_i'(B_i) = 1 + nu. Each network gets money until one more
    dollar there returns exactly 1 + nu dollars by the window. nu = 0 when the budget is not
    used up: past that point an extra dollar would earn back less than a dollar.
    """
    arpu = [n.arpu_at(window) for n in nets]

    def spend_for(nu):
        return [(r * n.k * n.a / (1 + nu)) ** (1 / (1 - n.a)) for n, r in zip(nets, arpu)]

    spend = spend_for(0.0)
    if sum(spend) > budget:
        lo, hi = 0.0, 1.0
        while sum(spend_for(hi)) > budget:
            hi *= 2
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if sum(spend_for(mid)) > budget else (lo, mid)
        spend = spend_for(hi)
    installs = [n.installs(x) for n, x in zip(nets, spend)]
    return Allocation(budget=sum(spend), window=window, target_roas=float("nan"), spend=spend,
                      installs=installs, cpi=[n.cpi_at(x) for n, x in zip(nets, spend)],
                      revenue=[r * i for r, i in zip(arpu, installs)], roas_binding=False)


@dataclass
class Allocation:
    budget: float
    window: int
    target_roas: float
    spend: list[float]
    installs: list[float]
    cpi: list[float]
    revenue: list[float]
    roas_binding: bool

    @property
    def total_installs(self) -> float:
        return sum(self.installs)

    @property
    def avg_cpi(self) -> float:
        return self.budget / self.total_installs

    @property
    def roas(self) -> float:
        return sum(self.revenue) / self.budget


def _spend_for(nets, arpu, lam, mu):
    # From (1 + lam*arpu) * k * a * B^(a-1) = mu  ->  B = ((1 + lam*arpu) * k * a / mu)^(1/(1-a))
    return [((1 + lam * r) * n.k * n.a / mu) ** (1 / (1 - n.a)) for n, r in zip(nets, arpu)]


def _allocate_for_lambda(nets, arpu, lam, budget):
    lo, hi = 1e-12, 1e6
    for _ in range(200):  # bisection on log scale
        mu = (lo * hi) ** 0.5
        if sum(_spend_for(nets, arpu, lam, mu)) > budget:
            lo = mu
        else:
            hi = mu
    spend = _spend_for(nets, arpu, lam, (lo * hi) ** 0.5)
    scale = budget / sum(spend)  # remove the last bisection rounding
    return [s * scale for s in spend]


def _roas(nets, arpu, spend, budget):
    return sum(r * n.installs(s) for n, r, s in zip(nets, arpu, spend)) / budget


def allocate(nets: list[Network], budget: float, target_roas: float = 1.0, window: int = 30) -> Allocation:
    arpu = [n.arpu_at(window) for n in nets]
    spend = _allocate_for_lambda(nets, arpu, 0.0, budget)
    binding = False
    if _roas(nets, arpu, spend, budget) < target_roas:
        binding = True
        lam_hi = 1.0
        while _roas(nets, arpu, _allocate_for_lambda(nets, arpu, lam_hi, budget), budget) < target_roas:
            lam_hi *= 4
            if lam_hi > 1e9:
                raise Infeasible(f"no split of ${budget:,.0f} reaches {target_roas:.0%} D{window} ROAS")
        lam_lo = 0.0
        for _ in range(100):
            lam = (lam_lo + lam_hi) / 2
            if _roas(nets, arpu, _allocate_for_lambda(nets, arpu, lam, budget), budget) < target_roas:
                lam_lo = lam
            else:
                lam_hi = lam
        spend = _allocate_for_lambda(nets, arpu, lam_hi, budget)
    installs = [n.installs(s) for n, s in zip(nets, spend)]
    return Allocation(
        budget=budget, window=window, target_roas=target_roas, spend=spend, installs=installs,
        cpi=[n.cpi_at(s) for n, s in zip(nets, spend)],
        revenue=[r * i for r, i in zip(arpu, installs)], roas_binding=binding,
    )
