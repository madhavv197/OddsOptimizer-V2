from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Bet:
    match_id: str
    team: str
    side: str
    odds: float
    win_rate: float
    ev: float
    strategy: str
    placed: bool = False
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    risk: Optional[float] = 0
    timestamp: Optional[datetime] = None
    hit: Optional[bool] = None
    payout: Optional[float] = None
    profit: Optional[float] = None