import json
from datetime import datetime

# 1. Update Account Status
account_status = {
    "current_capital": 64247.98,
    "as_of": "2026-01-06"
}

with open("data/account_status.json", "w", encoding="utf-8") as f:
    json.dump(account_status, f, indent=2)
print("Updated data/account_status.json")

# 2. Update Positions
positions = {
    "512480": {
        "name": "半导体ETF",
        "entry_price": 1.083,
        "shares": 10000,
        "entry_date": "2026-01-01 09:30:00",
        "stop_loss": 1.029,  # -5%
        "take_profit": 1.245, # +15%
        "highest_price": 1.184,
        "current_price": 1.184,
        "sector": "半导体",
        "status": "holding"
    },
    "588100": {
        "name": "科创人工智能ETF",
        "entry_price": 0.739,
        "shares": 10000,
        "entry_date": "2026-01-01 09:30:00",
        "stop_loss": 0.702,
        "take_profit": 0.850,
        "highest_price": 0.792,
        "current_price": 0.792,
        "sector": "人工智能",
        "status": "holding"
    },
    "000547": {
        "name": "航天发展",
        "entry_price": 32.710,
        "shares": 200,
        "entry_date": "2026-01-01 09:30:00",
        "stop_loss": 31.07,
        "take_profit": 37.62,
        "highest_price": 34.080,
        "current_price": 34.080,
        "sector": "军工",
        "status": "holding"
    },
    "588060": {
        "name": "科创50ETF广发",
        "entry_price": 0.884,
        "shares": 7000,
        "entry_date": "2026-01-01 09:30:00",
        "stop_loss": 0.840,
        "take_profit": 1.017,
        "highest_price": 0.910,
        "current_price": 0.910,
        "sector": "指数",
        "status": "holding"
    },
    "601336": {
        "name": "新华保险",
        "entry_price": 79.471,
        "shares": 100,
        "entry_date": "2026-01-06 09:30:00",
        "stop_loss": 75.50,
        "take_profit": 91.40,
        "highest_price": 80.800,
        "current_price": 80.800,
        "sector": "保险",
        "status": "holding"
    }
}

with open("data/positions.json", "w", encoding="utf-8") as f:
    json.dump(positions, f, indent=2, ensure_ascii=False)
print("Updated data/positions.json")
