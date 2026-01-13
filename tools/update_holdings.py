import json
from datetime import datetime

# 1. Update Account Status
account_status = {
    "current_capital": 85189.66,
    "as_of": "2026-01-12"
}

with open("data/runtime/account_status.json", "w", encoding="utf-8") as f:
    json.dump(account_status, f, indent=2)
print("Updated data/runtime/account_status.json")

# 2. Update Positions
positions = {
    "002050": {
        "name": "三花智控",
        "entry_price": 56.780,
        "shares": 200,
        "entry_date": "2026-01-12 09:30:00",
        "stop_loss": 53.94,
        "take_profit": 65.30,
        "highest_price": 57.000,
        "current_price": 57.000,
        "sector": "家用电器",
        "status": "holding"
    },
    "600410": {
        "name": "华胜天成",
        "entry_price": 22.060,
        "shares": 400,
        "entry_date": "2026-01-12 09:30:00",
        "stop_loss": 20.95,
        "take_profit": 25.37,
        "highest_price": 22.090,
        "current_price": 22.090,
        "sector": "计算机",
        "status": "holding"
    },
    "601336": {
        "name": "新华保险",
        "entry_price": 76.725,
        "shares": 100,
        "entry_date": "2026-01-12 09:30:00",
        "stop_loss": 72.88,
        "take_profit": 88.23,
        "highest_price": 80.060,
        "current_price": 80.060,
        "sector": "保险",
        "status": "holding"
    },
    "002195": {
        "name": "岩山科技",
        "entry_price": 10.532,
        "shares": 600,
        "entry_date": "2026-01-12 09:30:00",
        "stop_loss": 10.00,
        "take_profit": 12.11,
        "highest_price": 11.390,
        "current_price": 11.390,
        "sector": "软件服务",
        "status": "holding"
    },
    "600589": {
        "name": "大位科技",
        "entry_price": 10.422,
        "shares": 600,
        "entry_date": "2026-01-12 09:30:00",
        "stop_loss": 9.90,
        "take_profit": 11.98,
        "highest_price": 10.422,
        "current_price": 10.320,
        "sector": "半导体",
        "status": "holding"
    },
    "600862": {
        "name": "中航高科",
        "entry_price": 25.948,
        "shares": 200,
        "entry_date": "2026-01-12 09:30:00",
        "stop_loss": 24.65,
        "take_profit": 29.84,
        "highest_price": 27.880,
        "current_price": 27.880,
        "sector": "航空航天",
        "status": "holding"
    },
    "000559": {
        "name": "万向钱潮",
        "entry_price": 20.155,
        "shares": 200,
        "entry_date": "2026-01-12 09:30:00",
        "stop_loss": 19.14,
        "take_profit": 23.18,
        "highest_price": 20.450,
        "current_price": 20.450,
        "sector": "汽车零部件",
        "status": "holding"
    }
}

with open("data/runtime/positions.json", "w", encoding="utf-8") as f:
    json.dump(positions, f, indent=2, ensure_ascii=False)
print("Updated data/runtime/positions.json")
