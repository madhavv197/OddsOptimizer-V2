import argparse

parser = argparse.ArgumentParser(description="OddsOptimizer betting engine")

parser.add_argument("--min-risk", action="store_true", help="Only place bets with risk = 0.1 EUR")
parser.add_argument("--update", action="store_true", help="Only resolve past bets, no new betting")
parser.add_argument("--limit", type=int, help="Max number of bets to place this run")

args = parser.parse_args()

from utils.dataloader import DataLoader
from utils.executor import Executor
from pathlib import Path
import pandas as pd
pd.set_option("display.max_columns", None)

if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parent / "data"
    data_loader = DataLoader(data_dir, "config.yaml")
    executor = Executor(data_loader=data_loader)

    print("[INFO] Resolving past bets...")
    data_loader.resolve_past_bets()
    

    if not args.update:
        print("[INFO] Generating new bets...")
        pending_bets = data_loader.get_new_bets()
        print(data_loader.pending_bets)
        if args.min_risk:
            print("[MIN RISK] Overriding risk to 0.1 EUR per bet")
            pending_bets["risk"] = 0.1

        if args.limit:
            pending_bets = pending_bets.head(args.limit)

        print(f"[INFO] Placing {len(pending_bets)} bets...")
        executor.place_bets(pending_bets=pending_bets)

    data_loader.save_all()
    print("[INFO] Session complete.")