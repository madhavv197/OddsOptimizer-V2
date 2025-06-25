from playwright.sync_api import sync_playwright
import json
from pathlib import Path
import time
import random as rand
import pandas as pd
from utils.dataloader import DataLoader
from dotenv import load_dotenv
import os
from datetime import datetime

class Executor:
    def __init__(self, data_loader) -> None:
        self.data_loader = data_loader
        self.config_mgr = self.data_loader.config_mgr
        self.browser_mgr = self.data_loader.browser_mgr
        self.session_file = self.data_loader.session_file
        self.past_bets = self.data_loader.past_bets
        self.placed_bets = self.data_loader.placed_bets
        self.failed_bets = self.data_loader.failed_bets
        load_dotenv()
        self.username = os.getenv("TOTO_USERNAME")
        self.password = os.getenv("TOTO_PASSWORD")
          
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
            if "resultaat" in header and "vroege" not in header:
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
        
        viewport = page.viewport_size
        center_x = viewport["width"] // 2
        center_y = 265  # locked based on visual
        page.mouse.click(center_x, center_y)

        #risk = 0.10 # testing

        try:
            bet_slip = page.locator("[data-testid='leg-user-input-stake-wrapper']")
            stake_input = bet_slip.locator("input[data-testid='stake-input']")
            stake_input.wait_for(state="visible", timeout=5000)
            time.sleep(1)
            #print(bet.risk)
            stake_input.fill(str(bet.risk))
            #print("found stake input")
        except Exception as e:
            print(f"Skipping bet on {bet.home_team} vs {bet.away_team}")
            print("Moving bet to failed bets, check log for further details.")
            message = f"Skipping bet on {bet.home_team} vs {bet.away_team}. Coudn't find stake input. Error: {e}"
            self.data_loader.add_to_log(message=message)
            self.data_loader.move_failed_bet(bet)
            return

        time.sleep(1)
        # Check for and accept odds changes if present before placing the bet
        try:
            accept_changes_button = page.locator("button:has-text('Accepteer alle wijzigingen')")
            if accept_changes_button.is_visible():
                self.data_loader.add_to_log(message="Accepting odds changes before placing bet")
                accept_changes_button.click()
                time.sleep(1)
        except Exception as e:
            self.data_loader.add_to_log(message=f"Error accepting odds changes: {e}")
            
        #print("waiting for ok button")
        
        ok_button = page.locator("button:has-text('Plaats weddenschap')")
        ok_button.click()
        
        bet.placed = True
        
        self.data_loader.move_placed_bet(bet)
        #print(self.data_loader.placed_bets)
        message = f"Placed bet succesfully on {bet.home_team} vs {bet.away_team} for {bet.risk} EUR"
        self.data_loader.add_to_log(message=message)
        
        time.sleep(2)
        
    def place_bets(self, pending_bets):
        page = self.browser_mgr.start_page()
        try:
            page.goto("https://sport.toto.nl/")
            page.click("text=AKKOORD")
            self.browser_mgr._login(page, self.username, self.password)
            
            page.mouse.click(10, 10)
            
            if not pending_bets.empty:
                for idx, row in pending_bets.iterrows():
                    bet = self.data_loader.get_pending_bet(row)
                    try:
                        if bet.match_id in self.placed_bets["match_id"].values:
                            print(f"Bet on {bet.home_team} vs {bet.away_team} already placed, skipping.")
                            continue
                        self._place_bet(page, bet)
                    except Exception as e:
                        #print(f"Error placing bet: {e}")
                        message = f"Error placing bet on {bet.home_team} vs {bet.away_team}. Error: {e}"
                        self.data_loader.add_to_log(message=message)
                        self.data_loader.move_failed_bet(bet)
                        continue
        finally:
            self.browser_mgr.close_page()
    
if __name__ == "__main__":
    executor = Executor("data", "config.yaml")
    print(executor.pending_bets)
    #executor.get_new_bets()
    #executor.update_past_bets()
    #executor.update_placed_bets()