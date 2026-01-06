import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from quant.strategy.auction_filter import apply_auction_filters


def test_auction_filter_cancel_on_gap():
    plan = pd.DataFrame(
        [
            {"代码": "000001", "名称": "测试股", "收盘价": 10.0, "建议买入价": 10.0},
        ]
    )
    snapshot = pd.DataFrame(
        [
            {"代码": "000001", "最新价": 10.5, "涨跌幅": 5.0, "量比": 1.0},
        ]
    )

    keep_df, cancel_df = apply_auction_filters(plan, snapshot)
    assert keep_df.empty
    assert len(cancel_df) == 1
    assert cancel_df.iloc[0]["竞价处理"] == "cancel"


def test_auction_filter_adjust_on_small_gap():
    plan = pd.DataFrame(
        [
            {"代码": "000002", "名称": "测试股2", "收盘价": 10.0, "建议买入价": 10.0},
        ]
    )
    snapshot = pd.DataFrame(
        [
            {"代码": "000002", "最新价": 10.2, "涨跌幅": 2.0, "量比": 1.0},
        ]
    )

    keep_df, cancel_df = apply_auction_filters(plan, snapshot)
    assert len(keep_df) == 1
    assert keep_df.iloc[0]["竞价处理"] in ("keep", "adjust")
    assert cancel_df.empty
