from playwright.sync_api import sync_playwright
import json
from pathlib import Path
import time
import random as rand
import pandas as pd
from utils.dataloader import DataLoader

class Executor:
    def __init__(self, data_dir: str, config_path: str) -> None:
        self.data_loader = DataLoader(data_dir, config_path)
        self.config_mgr = self.data_loader.config_mgr
        self.browser_mgr = self.data_loader.browser_mgr
        self.session_file = self.data_loader.session_file
        self.past_bets = self.data_loader.past_bets
        self.pending_bets = self.data_loader.get_new_bets()
        self.placed_bets = self.data_loader.placed_bets
        
    def _place_bet(self, page, bet):
        page.fill("[data-testid='search-field']", f"{bet.home_team} vs {bet.away_team}")
        time.sleep(5)

        anchors = page.locator("a[data-testid='selectable-event-wrapper-anchor']")
        count = anchors.count()

        clicked = False
        for i in range(count):
            anchor = anchors.nth(i)
            parent_text = anchor.evaluate("el => el.parentElement.innerText.toLowerCase()")

            if bet.home_team.lower() in parent_text and bet.away_team.lower() in parent_text:
                anchor.evaluate("el => el.click()")
                time.sleep(2)
                clicked = True
                break

        if not clicked:
            print(f"Could not find anchor for {bet.home_team} vs {bet.away_team}")
            
        time.sleep(2)

        event_wrappers = page.locator("div[class*='eventMarketWrapper']")
        for i in range(event_wrappers.count()):
            wrapper = event_wrappers.nth(i)
            header = wrapper.locator("div[data-testid='market-header']").inner_text().lower()
            if "resultaat" in header:
                market = wrapper.locator("div[data-testid='market-container']")
                buttons = market.locator("button[data-testid='outcome-button']")
                for j in range(buttons.count()):
                    button = buttons.nth(j)
                    try:
                        description = button.locator("span[data-testid='outcome-odds-description']").inner_text().lower()
                        if bet.side == "home" and bet.home_team.lower() in description:
                            button.click()
                            break
                        elif bet.side == "draw" and "gelijkspel" in description:
                            button.click()
                            break
                        elif bet.side == "away" and bet.away_team.lower() in description:
                            button.click()
                            break
                    except:
                        continue
                break

        time.sleep(2)

        #risk = 0.10 # testing

        try:
            bet_slip = page.locator("[data-testid='leg-user-input-stake-wrapper']")
            stake_input = bet_slip.locator("input[data-testid='stake-input']")
            stake_input.wait_for(state="visible", timeout=5000)
            stake_input.fill(str(bet.risk))
        except Exception as e:
            print(f"Skipping bet on {bet.home_team} vs {bet.away_team}")
            return

        time.sleep(1)

        ok_button = page.locator("button:has-text('Plaats weddenschap')")
        ok_button.click()

        time.sleep(2)
        
    def place_bets(self):
        p, browser, context, page = self.browser_mgr._initialise_browser("https://sport.toto.nl/")
        page.click("text=AKKOORD")
        self.browser_mgr._login(page, "username", "password")
