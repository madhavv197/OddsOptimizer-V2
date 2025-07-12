import pandas as pd
import numpy as np
from datetime import datetime
from bs4 import BeautifulSoup
import time
import random as rand
from playwright.sync_api import sync_playwright
import json
from pathlib import Path
import re
import sys
import os
import yaml
from utils.config_manager import ConfigManager


class BroswerManager():
    def __init__(self, data_dir, config_path) -> None:
        self.session_file = f"{data_dir}/session_cookies.json"
        self.config_mgr = ConfigManager(config_path)
        self.p = None
        self.browser = None
        self.context = None
        self.page = None
        
    def _save_cookies(self, page):
        cookies = page.context.cookies()
        with open(self.session_file, 'w') as f:
            json.dump(cookies, f)
            
    def _load_cookies(self, page):
        if os.path.exists(self.session_file):
            with open(self.session_file, 'r') as f:
                cookies = json.load(f)
            page.context.add_cookies(cookies)

    def _prepare_page(self, url, odds=False, execute=False):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            self._load_cookies(page)

            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            
            for i in range(5, 10):
                time.sleep(rand.uniform(1.5, 2))
            
            if page.query_selector("iframe[src*='hcaptcha.com']"):
                print("\n Captcha detected! Solve it manually in the browser.")
                input("Press Enter after solving the captcha manually...")

                self._save_cookies(page)
                print("\n Captcha solved and session saved. Continuing...")
            
            if execute:
                return p, browser, context, page
            soup = BeautifulSoup(page.content(), "html.parser")

            if not odds:
                match_cards = soup.find_all("div", class_="_match-card_1u4oy_1")
                return soup, match_cards
            else:
                match_cards = soup.find_all("div", class_="selectionPrice-0-3-836")
                return soup, match_cards
        
    def _parse_match_date(self, meta_div):
        date_time_divs = meta_div.find_all("div", class_="_match-card-right-label_1u4oy_83")
        if len(date_time_divs) < 2:
            return None

        match_date_str = date_time_divs[1].text.strip()
        if "LIVE" in match_date_str:
            return None

        try:
            full_date_str = f"{datetime.now().year} {match_date_str}"
            dt = datetime.strptime(full_date_str, "%Y %b %d @ %H:%M")
            return dt.isoformat(timespec='seconds')
        except ValueError:
            print(f"Could not parse date: {match_date_str}")
            return None
        
    def _parse_percentage(self, percentage_str):
        match = re.search(r"(\d+)", percentage_str)
        return float(float(match.group(1)) / 100) if match else 0.0
    
    def _parse_match_probs(self, tbody):
        rows = tbody.find_all("tr")
        if len(rows) < 2:
            return None

        # Home and Draw
        home_team = rows[0].find("span").text.strip()
        tds_home = rows[0].find_all("td")
        if len(tds_home) == 3:  # No PR case (e.g., Nations League)
            #print(tds_home[0])
            #print(tds_home[1].text.strip())
            #print(tds_home[2])
            home_win_prob = tds_home[1].text.strip()
            #print(home_win_prob)
            draw_td = tds_home[2]
            draw_prob = next(
                (div.text.strip() for div in draw_td.find_all("div") if "%" in div.text),
                "Unknown"
            )
            #print(draw_td)
        elif len(tds_home) < 2:
            return None
        else:  # PR exists (e.g., Let and Leo)
            #print(tds_home)
            home_pr = tds_home[1].text.strip()
            try:
                home_win_prob = tds_home[2].text.strip()
            except:
                home_win_prob = "0%"
            try:
                draw_td = tds_home[3]
                draw_prob = next(
                (div.text.strip() for div in draw_td.find_all("div") if "%" in div.text),
                "Unknown"
            )
            except:
                draw_td = None
                
        # Away team
        away_team = rows[1].find("span").text.strip()
        tds_away = rows[1].find_all("td")
        
        if len(tds_away) == 2:  # No PR case
            away_win_prob = tds_away[1].text.strip()
        else:
            away_win_prob = tds_away[2].text.strip()
        
        # Parse the probabilities
        home_win_prob = self._parse_percentage(home_win_prob)
        away_win_prob = self._parse_percentage(away_win_prob)
        draw_prob = self._parse_percentage(draw_prob)

        return {
            "home_team": home_team,
            "home_win_prob": home_win_prob,
            "away_team": away_team,
            "away_win_prob": away_win_prob,
            "draw_prob": draw_prob
        }
    
    def _parse_match_results(self, tbody):
            rows = tbody.find_all("tr")
            tds_home = rows[0].find_all("td")
            tds_away = rows[1].find_all("td")

            home_team = tds_home[0].text.strip()
            away_team = tds_away[0].text.strip()
            #print(tds_home[1].text.strip())
            raw_string_home = tds_home[1].text.strip()
            raw_string_away = tds_away[1].text.strip()
            #print(raw_string_home.split(" ")[0].strip())
            home_goals = int(raw_string_home.split(" ")[0].strip())
            away_goals = int(raw_string_away.split(" ")[0].strip())

            outcome = "draw" if home_goals == away_goals else "home" if home_goals > away_goals else "away"
            
            return {
                "home_team": home_team,
                "away_team": away_team,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "outcome": outcome
            }
    def _parse_match_odds(self, match):
        team_name_a = match.find("div", class_=re.compile(r"eventCardTeamName-0-3-\d+.*"), 
                             attrs={"data-testid": "event-card-team-name-a"})
        home_team = team_name_a.text.strip() if team_name_a else "Unknown"

        team_name_b = match.find("div", class_=re.compile(r"eventCardTeamName-0-3-\d+.*"), 
                                attrs={"data-testid": "event-card-team-name-b"})
        away_team = team_name_b.text.strip() if team_name_b else "Unknown"

        # Extract odds
        odds = match.find_all("span", class_=re.compile(r"outcomePriceCommon-0-3-\d+"))
        #print(odds)
        try:
            win_odds = float(odds[0].text.strip().replace(",", "."))
        except Exception as e:
            print(f"Error parsing win odds: {e}")
            win_odds = 0.0
        try:
            draw_odds = float(odds[1].text.strip().replace(",", "."))
        except:
            draw_odds = 0.0
        try:
            loss_odds = float(odds[2].text.strip().replace(",", "."))
        except:
            loss_odds = 0.0

        # Extract date
        date_div = match.find("div", class_="timeBandGroupHeader-0-3-622")
        match_date = date_div.text.strip() if date_div else "Unknown"

        return {
            "home_team": home_team,
            "away_team": away_team,
            "win_odds": win_odds,
            "draw_odds": draw_odds,
            "loss_odds": loss_odds,
        }
        
    def get_future_matches(self):
        _, match_cards = self._prepare_page(
            "https://dataviz.theanalyst.com/opta-football-predictions/"
        )
        future_matches = []

        for match in match_cards:
            meta_div = match.find("div", class_="_match-card-meta_1u4oy_18")
            if not meta_div:
                continue

            match_date = self._parse_match_date(meta_div)
            if not match_date or datetime.fromisoformat(match_date) < datetime.now():
                continue
            
            league_div = meta_div.find("div", class_="_match-card-right-label_1u4oy_83")
            league_name = league_div.text.strip() if league_div else "Unknown"

            tbody = match.find("tbody")
            if not tbody:
                continue

            prob_data = self._parse_match_probs(tbody)
            #print(prob_data)
            if not prob_data:
                continue

            future_matches.append({
                "date": match_date,
                **prob_data
            })

        return future_matches
    
    def get_past_matches(self):
        _, match_cards = self._prepare_page("https://dataviz.theanalyst.com/opta-football-predictions/")
        past_matches = []
        for match in match_cards:
            meta_div = match.find("div", class_="_match-card-meta_1u4oy_18")
            if not meta_div:
                continue

            match_date = self._parse_match_date(meta_div)
            if not match_date or datetime.fromisoformat(match_date) > datetime.now():
                continue
            
            league_div = meta_div.find("div", class_="_match-card-right-label_1u4oy_83")
            league_name = league_div.text.strip() if league_div else "Unknown"

            tbody = match.find("tbody")
            if not tbody:
                continue

            prob_data = self._parse_match_results(tbody)
            if not prob_data:
                continue

            past_matches.append({
                "date": match_date,
                **prob_data
            })
    
        return past_matches
    
    def get_odds(self):
        leagues = self.config_mgr.get_leagues()
        # print(leagues)
        extracted_matches = []
        for prefix, url in leagues.items():
            soup, _ = self._prepare_page(url, odds=True)
            match_cards = soup.find_all("div", class_=re.compile(r"eventListItemContent-0-3-\d+"))

            for match in match_cards:
                odds_info = self._parse_match_odds(match)
                if odds_info:
                    league_name = prefix
                    odds_info["league"] = league_name
                    extracted_matches.append(odds_info)
        return extracted_matches
    
    def _login(self, page, username, password):

        page.click("text=Inloggen")

        page.fill("input[name='username']", username)
        page.fill("input[name='password']", password)
        

        page.click("button[type='submit']")
        
        page.wait_for_load_state("domcontentloaded", timeout=20000)

        for i in range(5, 10):
            time.sleep(rand.uniform(1.5, 2))
    
    def start_page(self):
        self.p = sync_playwright().start()
        self.browser = self.p.chromium.launch(headless=False)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self._load_cookies(self.page)
        return self.page

    def close_page(self):
        if self.browser:
            self.browser.close()
        if self.p:
            self.p.stop()
    
    
    
if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_loader = BroswerManager(data_dir, "config.yaml")
    odds_data = data_loader._get_odds()
    print(odds_data)
