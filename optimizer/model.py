"""Channel data and the cost-of-scale model.

Each network has a baseline CPI measured at a baseline spend (default $100,000),
and cumulative revenue per install (ARPU) at day 1, 7, 15, 30, 60 and 90.

Scaling: every +25% budget on a network raises its CPI by a fixed percentage,
compounding, depending on the channel type:

    ad networks +10%   DSPs +15%   social networks +20%

    CPI(B) = CPI0 * (B / B0) ** e,   e = ln(1 + g) / ln(1.25)

so installs(B) = B / CPI(B) = k * B ** a with a = 1 - e (0 < a < 1):
every extra dollar buys fewer installs than the last (diminishing returns).
"""
import csv
import math
from dataclasses import dataclass, field

SCALING_PER_25PCT = {"ad_network": 0.10, "dsp": 0.15, "social": 0.20}
ARPU_DAYS = (1, 7, 15, 30, 60, 90)


@dataclass
class Network:
    name: str
    type: str
    cpi: float                      # baseline CPI at baseline spend
    arpu: dict = field(default_factory=dict)  # day -> cumulative ARPU
    base_spend: float = 100_000.0

    @property
    def elasticity(self) -> float:
        g = SCALING_PER_25PCT[self.type]
        return math.log(1 + g) / math.log(1.25)

    @property
    def a(self) -> float:
        return 1 - self.elasticity

    @property
    def k(self) -> float:
        return self.base_spend ** self.elasticity / self.cpi

    def cpi_at(self, spend: float) -> float:
        return self.cpi * (spend / self.base_spend) ** self.elasticity if spend > 0 else self.cpi

    def installs(self, spend: float) -> float:
        return self.k * spend ** self.a if spend > 0 else 0.0

    def arpu_at(self, day: int) -> float:
        """Cumulative ARPU at a day; days past the data are projected (see project_arpu)."""
        if day in self.arpu:
            return self.arpu[day]
        return project_arpu(self.arpu, day)


def project_arpu(arpu: dict, day: int) -> float:
    """Project cumulative ARPU to a later day with a power curve ARPU = c * day^b,
    fitted (least squares in log-log) on the day-7-and-later points.
    Simple and transparent; it assumes growth keeps slowing at the same rate."""
    pts = [(d, v) for d, v in sorted(arpu.items()) if d >= 7 and v > 0]
    if len(pts) < 2:
        raise ValueError("need at least two ARPU points from day 7 on to project")
    xs = [math.log(d) for d, _ in pts]
    ys = [math.log(v) for _, v in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    c = math.exp(my - b * mx)
    return c * day ** b


def load_csv(path: str) -> list[Network]:
    """Columns: name, type (ad_network | dsp | social), cpi, d1, d7, d15, d30, d60, d90.
    Optional: base_spend. ARPU columns may be left blank."""
    nets = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["type"] not in SCALING_PER_25PCT:
                raise ValueError(f"{row['name']}: type must be one of {sorted(SCALING_PER_25PCT)}")
            arpu = {d: float(row[f"d{d}"]) for d in ARPU_DAYS if row.get(f"d{d}", "").strip()}
            nets.append(Network(row["name"], row["type"], float(row["cpi"]), arpu,
                                float(row.get("base_spend") or 100_000)))
    return nets
