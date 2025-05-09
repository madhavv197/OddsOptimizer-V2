import yaml
import json

class ConfigManager():
    def __init__(self, config_path="config.yaml", json_path="utils/team_map.json") -> None:
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        with open(json_path) as f:
            self.team_name_map = json.load(f)
    def get_setting(self, key: str, default=None):
        return self.config.get("settings", {}).get(key, default)
    
    def get_leagues(self):
        return self.config.get("leagues", [])
    
    def get_translation(self, input_team: str) -> str:
        return self.team_name_map.get(input_team.strip(), input_team)