import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from utils.browser_manager import BroswerManager
from utils.config_manager import ConfigManager
from engine import models
from thefuzz import process


class DataLoader:
    def __init__(self, data_dir, config_path) -> None: 
        self.data_dir = data_dir
        self.past_bets = pd.read_csv(f"{data_dir}/past_bets.csv")
        self.pending_bets = None
        self.placed_bets = pd.read_csv(f"{data_dir}/placed_bets.csv")
        # self.failed_bets = pd.read_csv(f"{data_dir}/failed_bets.csv")
        self.session_file = f"{data_dir}/session_cookies.json"
        self.browser_mgr = BroswerManager(data_dir, config_path)
        self.config_mgr = ConfigManager(config_path)

    def _get_best_match(self, name, choices, threshold=70):
        best_match, score = process.extractOne(name, choices)
        return best_match if score >= threshold else None
    
    def resolve_past_bets(self):
        past_matches = self.browser_mgr.get_past_matches()
        rows_to_add = []
        rows_to_remove = []
        for i, row in self.placed_bets.iterrows():
            print(row)
            bet = models.Bet(
                match_id=row["match_id"],
                team=row["team"],
                side = row["side"],
                odds=row["odds"],
                win_rate=row["win_rate"],
                ev=row["ev"],
                risk=row["risk"],
                strategy=row["strategy"],
                placed=row["placed"],
                timestamp=row["timestamp"],
                hit=row["hit"],
                payout=row["payout"],
                profit=row["profit"]
            )
            for match in past_matches:
                if bet.timestamp == match["date"] and (bet.team == match["home_team"] or bet.team == match["away_team"]):
                    bet.hit = True if match["outcome"] == bet.side else False
                    bet.payout = bet.risk * bet.odds if bet.hit else -bet.risk
                    bet.profit = bet.risk * (bet.odds - 1) if bet.hit else -bet.risk 
                    rows_to_remove.append(i)
                    rows_to_add.append({
                        "match_id": bet.match_id,
                        "team": bet.team,
                        "side": bet.side,
                        "odds": bet.odds,
                        "win_rate": bet.win_rate,
                        "ev": bet.ev,
                        "risk": bet.risk,
                        "strategy": bet.strategy,
                        "placed": bet.placed,
                        "timestamp": bet.timestamp,
                        "hit": bet.hit,
                        "payout": bet.payout,
                        "profit": bet.profit
                    })
                    break
        self.placed_bets.drop(rows_to_remove, inplace=True)
        new_bets = pd.DataFrame(rows_to_add)
        self.past_bets = pd.concat([self.past_bets, new_bets], ignore_index=True)   
        print(self.placed_bets)
        print(self.past_bets)

    def get_new_bets(self):
        future_matches = self.browser_mgr.get_future_matches()
        odds_data = self.browser_mgr.get_odds()
        
        # print(future_matches)
        # print(odds_data)
        
        weekly_exposure = self.config_mgr.get_setting("weekly_exposure")
        beta = self.config_mgr.get_setting("beta")
        ev_threshold = self.config_mgr.get_setting("ev_threshold")
        initial_bankroll = self.config_mgr.get_setting("initial_bankroll")
        strategy = self.config_mgr.get_setting("strategy")
        
        odds_lookup = {
            (
                self.config_mgr.get_translation(o["home_team"]),
                self.config_mgr.get_translation(o["away_team"]),
            ): o
            for o in odds_data
        }
        
        bets = []
        
        for match in future_matches:
            home_team = self.config_mgr.get_translation(match["home_team"])
            away_team = self.config_mgr.get_translation(match["away_team"])
            match_date = match["date"]
            home_win_prob = match["home_win_prob"]
            away_win_prob = match["away_win_prob"]
            draw_prob = match["draw_prob"]
            
            odds = None
            for (odd_home, odd_away), o in odds_lookup.items():
                home_score = process.extractOne(home_team, [odd_home])[1]
                away_score = process.extractOne(away_team, [odd_away])[1]
                if home_score >= 70 and away_score >= 70:
                    odds = o
                    break
            if not odds:
                continue
            
            win_odds, draw_odds, loss_odds = odds["win_odds"], odds["draw_odds"], odds["loss_odds"]

            ev_map = {
                "home": (home_win_prob * (win_odds - 1)) - (1 - home_win_prob),
                "away": (away_win_prob * (loss_odds - 1)) - (1 - away_win_prob),
                "draw": (draw_prob * (draw_odds - 1)) - (1 - draw_prob)
            }

            side, ev = max(ev_map.items(), key=lambda x: x[1])
            #print(ev)
            if ev < ev_threshold:
                continue
            
            side_map = {
                "home": (home_team, win_odds, home_win_prob),
                "draw": ("draw", draw_odds, draw_prob),
                "away": (away_team, loss_odds, away_win_prob)
            }
            bet_team, bet_odds, bet_prob = side_map[side]
            
            bets.append({
                "match_id": f"{home_team} vs {away_team}",
                "home_team": home_team,
                "away_team": away_team,
                "team": bet_team,
                "side": side,
                "odds": bet_odds,
                "win_rate": bet_prob,
                "ev": ev,
                "strategy": strategy,
                "placed": False,
                "risk": None,
                "timestamp": match_date,
                "hit": None,
                "payout": None,
                "profit": None,
            })
        self.pending_bets = pd.DataFrame(bets)
        
        self.pending_bets["risk"] = 1 + self.pending_bets["ev"] * beta
        
        self.pending_bets["risk"] = (weekly_exposure*initial_bankroll)*(self.pending_bets["risk"]/self.pending_bets["risk"].sum())
        
        return self.pending_bets
        
    def save_all(self):
        self.placed_bets.to_csv(self.data_dir / "placed_bets.csv", index=False)
        self.past_bets.to_csv(self.data_dir / "past_bets.csv", index=False)
        self.failed_bets.to_csv(self.data_dir / "failed_bets.csv", index=False)
        
        
    def move_failed_bet(self, bet):
        self.pending_bets.drop(self.pending_bets[self.pending_bets["match_id"] == bet.match_id].index, inplace=True)
        self.failed_bets = pd.concat([self.failed_bets, pd.DataFrame([bet.__dict__])], ignore_index=True)
    

if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_loader = DataLoader(data_dir, "config.yaml")

    # Step 2: Get new bets
    pending_bets = data_loader.get_new_bets()
    print(pending_bets)
    exit()
    # Step 3: Set as pending bets and save
    data_loader.pending_bets = pending_bets
    pending_bets.to_csv(data_dir / "pending_bets.csv", index=False)

    # Step 4: Save all
    data_loader.save_all()