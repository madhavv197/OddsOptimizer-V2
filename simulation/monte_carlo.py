import pandas as pd
import numpy as np
from tqdm import tqdm

def set_seed(seed):
    np.random.seed(seed)

def simulate_monte_carlo(past_bets, num_simulations, initial_balance, beta, max_risk, ruin_threshold, ev_treshold=0.1):
    results = []
    for _ in tqdm(range(num_simulations), desc="Simulating Monte Carlo", unit="simulation"):
        result = single_monte_carlo(past_bets, initial_balance, beta, max_risk, ruin_threshold, ev_treshold)
        results.append(result)
    return pd.DataFrame(results)

def single_monte_carlo(past_bets, initial_balance, beta, max_risk, ruin_threshold, ev_treshold):
    data = get_simulation_data(past_bets, threshold=ev_treshold)
    data, bin_counts = bin_data(data)
    grouped = data.groupby(["ev_bin", "odds_bin"]).agg(
    avg_pred_win_rate=("bet_win_rate", "mean"),
    actual_hit_rate=("hit", "mean"),
    count=("hit", "count")).reset_index()

    # print(grouped.sort_values("count", ascending=False).head(50))

    # exit()
    sampled_data = sample_data(data, bin_counts, 600)

    window_size = 20
    num_windows = len(sampled_data) // window_size

    bankroll = initial_balance
    peak = initial_balance
    drawdown = 0
    returns = []
    ruined = False
    time_underwater = 0
    simulated_hits = 0
    total_bets = 0

    for i in range(num_windows):
        start = i * window_size
        end = start + window_size
        window = sampled_data.iloc[start:end]

        profit, sim_window = simulate_step(window, initial_balance=bankroll, max_risk=max_risk, beta=beta)
        returns.append(profit)
        simulated_hits += sim_window["sim_result"].sum()
        total_bets += len(sim_window)

        bankroll += profit
        peak = max(peak, bankroll)
        drawdown = max(drawdown, peak - bankroll)

        if bankroll < initial_balance:
            time_underwater += 1

        if bankroll <= ruin_threshold * initial_balance:
            ruined = True
            break

    roi = (bankroll - initial_balance) / initial_balance
    volatility = np.std(returns) if returns else 0
    sharpe = (np.mean(returns) / volatility) if volatility else 0
    simulated_hit_rate = simulated_hits / total_bets if total_bets else 0

    return {
        "final_bankroll": bankroll,
        "roi": roi,
        "ruined": ruined,
        "max_drawdown": drawdown,
        "volatility": volatility,
        "sharpe_ratio": sharpe,
        "underwater_time": time_underwater,
        "simulated_hit_rate": simulated_hit_rate,
    }

def simulate_step(window, initial_balance, max_risk, beta):
    window = window.copy()
    window["risk"] = 1 + window["ev"] * beta
        
    window["risk"] = (max_risk*initial_balance*window["risk"])/window["risk"].sum()

    window["sim_result"] = np.random.rand(len(window)) < window["bet_win_rate"]


    window["payout"] = np.where(
        window["sim_result"],
        window["risk"] * (window["bet_odds"] - 1),
        -window["risk"]                            
    )
    window["actual_payout"] = np.where(window["hit"] == 1,
        window["risk"] * (window["bet_odds"] - 1),
        -window["risk"]
    )
    
    total_profit = window["payout"].sum()
    real_profit = window["actual_payout"].sum()
    # print(window)
    # print(total_profit)
    # print(real_profit)

    return total_profit,  window

def get_simulation_data(past_bets, threshold=0.1):
    data = past_bets.copy().dropna()
    data["hit"] = (data["bet"] == data["outcome"]).astype(int)

    data["bet_odds"] = data.apply(lambda row: row[f"odds_{row['bet']}"], axis=1)
    data["bet_win_rate"] = data.apply(lambda row: row[f"{row['bet']}_win_%"], axis=1)

    data = data[["bet_win_rate", "bet_odds", "ev", "hit"]]
    data = data[data["ev"] > threshold]

    return data

def bin_data(data):
    ev_bins = [0, 0.01, 0.03, 0.07, 0.15, 1.0]
    odds_bins = [1.0, 2.5, 4.0, 7.0, 20.0]
    data["ev_bin"] = pd.cut(data["ev"], bins=ev_bins, labels=False)
    data["odds_bin"] = data.groupby("ev_bin")["bet_odds"].transform(
    lambda x: pd.cut(x, bins=odds_bins, labels=False))
    bin_counts = data.groupby(["ev_bin", "odds_bin"]).size().reset_index(name="count")
    bin_counts["weight"] = bin_counts["count"] / bin_counts["count"].sum()
    return data, bin_counts

def sample_data(data, bin_counts, num_samples):
    sampled_rows = []

    bin_choices = bin_counts[["ev_bin", "odds_bin"]].values
    bin_weights = bin_counts["weight"].values

    high_odds_limit = 2
    high_odds_count = 0

    for _ in range(num_samples):
        ev_bin, odds_bin = bin_choices[np.random.choice(len(bin_choices), p=bin_weights)]

        candidates = data[(data["ev_bin"] == ev_bin) & (data["odds_bin"] == odds_bin)]

        if not candidates.empty:
            sample = candidates.sample(n=1).iloc[0]

            if sample["bet_odds"] > 6.0:
                if high_odds_count >= high_odds_limit:
                    continue
                high_odds_count += 1

            sampled_rows.append(sample)
        else:
            continue

    sampled_data = pd.DataFrame(sampled_rows)
    return sampled_data

if __name__ == "__main__":
    set_seed(2)
    past_bets = pd.read_csv("data/old_strat/past_bets.csv")
    
    results = simulate_monte_carlo(past_bets, num_simulations=10000, initial_balance=100, beta=2, max_risk=0.3, ruin_threshold=0.5)
    
    print("Final results:")
    print("Average ROI:", results["roi"].mean())
    print("Average max drawdown:", results["max_drawdown"].mean())
    print("Average volatility:", results["volatility"].mean())
    print("Average Sharpe ratio:", results["sharpe_ratio"].mean())
    print("Average time underwater:", results["underwater_time"].mean())
    print("Percentage of ruined simulations:", results["ruined"].mean() * 100)
    print("Average final bankroll:", results["final_bankroll"].mean())