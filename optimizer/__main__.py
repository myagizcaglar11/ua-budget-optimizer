"""Command line:  python -m optimizer --data data/sample_networks.csv --budget 10000000 --roas 1.0 --window 30"""
import argparse

from .model import load_csv
from .solver import Infeasible, allocate, allocate_for_profit


def main(argv=None):
    p = argparse.ArgumentParser(description="Split a UA budget across networks for the most installs at a ROAS target.")
    p.add_argument("--data", default="data/sample_networks.csv")
    p.add_argument("--budget", type=float, default=10_000_000)
    p.add_argument("--roas", type=float, default=1.0, help="portfolio ROAS target, 1.0 = 100%%")
    p.add_argument("--window", type=int, default=30, help="payback window in days (30, 60, 90, or later = projected)")
    p.add_argument("--objective", choices=["installs", "profit"], default="installs",
                   help="installs: most installs at the ROAS target; profit: most net revenue by the window")
    args = p.parse_args(argv)

    nets = load_csv(args.data)
    if args.objective == "profit":
        a = allocate_for_profit(nets, args.budget, args.window)
        print(f"Most D{a.window} net revenue with up to ${args.budget:,.0f}: spends ${a.budget:,.0f}, "
              f"net ${sum(a.revenue) - a.budget:,.0f}\n")
    else:
        try:
            a = allocate(nets, args.budget, args.roas, args.window)
        except Infeasible as e:
            print(f"Infeasible: {e}")
            return 1
        print(f"Budget ${a.budget:,.0f} | target D{a.window} ROAS {a.target_roas:.0%} "
              f"({'binding' if a.roas_binding else 'not binding'})\n")
    print(f"{'Network':14}{'Type':12}{'Spend':>14}{'Share':>8}{'Installs':>12}{'CPI':>9}{'ROAS':>8}")
    for n, s, i, c, r in sorted(zip(nets, a.spend, a.installs, a.cpi, a.revenue), key=lambda t: -t[1]):
        print(f"{n.name:14}{n.type:12}{s:>14,.0f}{s / a.budget:>8.1%}{i:>12,.0f}{c:>9.2f}{r / s:>8.0%}")
    print(f"\nTotal installs {a.total_installs:,.0f} | average CPI ${a.avg_cpi:.2f} | portfolio ROAS {a.roas:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
