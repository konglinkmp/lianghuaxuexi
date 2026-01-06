"""
板块强度过滤（行业 + 概念）
"""

from dataclasses import dataclass
from datetime import datetime
import json
import os
from typing import Iterable, Optional, Set

import pandas as pd

from config.config import (
    ENABLE_SECTOR_STRENGTH_FILTER,
    SECTOR_STRENGTH_LOOKBACK,
    SECTOR_STRENGTH_TOP_PCT,
    SECTOR_STRENGTH_REQUIRE_EXCESS,
    SECTOR_STRENGTH_REQUIRE_BOTH,
    SECTOR_STRENGTH_APPLY_LAYERS,
    SECTOR_STRENGTH_ALLOW_NO_CONCEPT,
    SECTOR_STRENGTH_CACHE_FILE,
    CONCEPT_STRENGTH_TOP_N,
    CONCEPT_STRENGTH_OUTPUT_FILE,
)
from ..core.data_fetcher import get_stock_industry, get_stock_concepts, get_index_daily_history


@dataclass
class SectorStrengthFilter:
    strong_industries: Set[str]
    strong_concepts: Set[str]

    def is_allowed(self, industry: str, concepts: Iterable[str], layer: Optional[str] = None) -> bool:
        if not ENABLE_SECTOR_STRENGTH_FILTER:
            return True

        if SECTOR_STRENGTH_APPLY_LAYERS == "aggressive" and layer not in (None, "AGGRESSIVE"):
            return True

        industry_ok = industry in self.strong_industries if industry else False
        concepts = list(concepts) if concepts else []
        concept_ok = any(c in self.strong_concepts for c in concepts)

        if SECTOR_STRENGTH_REQUIRE_BOTH:
            if SECTOR_STRENGTH_ALLOW_NO_CONCEPT and not concepts:
                return industry_ok
            return industry_ok and concept_ok

        return industry_ok or concept_ok

    def strength_flags(self, industry: str, concepts: Iterable[str]) -> tuple[bool, bool, str]:
        industry_ok = industry in self.strong_industries if industry else False
        concepts = list(concepts) if concepts else []
        concept_ok = any(c in self.strong_concepts for c in concepts)

        if industry_ok and concept_ok:
            label = "双强"
        elif industry_ok:
            label = "行业强"
        elif concept_ok:
            label = "概念强"
        else:
            label = "弱"

        return industry_ok, concept_ok, label


def build_sector_strength_filter(stock_pool: Optional[pd.DataFrame] = None) -> SectorStrengthFilter:
    if not ENABLE_SECTOR_STRENGTH_FILTER:
        return SectorStrengthFilter(set(), set())

    cached = _load_cache()
    if cached is not None:
        return cached

    industry_candidates, concept_candidates = _collect_candidates(stock_pool)
    market_return = _get_market_return()

    strong_industries = _calc_strong_names(
        kind="industry",
        candidates=industry_candidates,
        market_return=market_return,
    )
    strong_concepts = _calc_strong_names(
        kind="concept",
        candidates=concept_candidates,
        market_return=market_return,
    )

    filt = SectorStrengthFilter(strong_industries, strong_concepts)
    _save_cache(filt)
    return filt


def get_concept_strength_table(stock_pool: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    cached = _load_cache()
    if cached and hasattr(cached, "concept_ranking"):
        ranking = getattr(cached, "concept_ranking", [])
        if ranking:
            return pd.DataFrame(ranking)

    _, concept_candidates = _collect_candidates(stock_pool)
    market_return = _get_market_return()
    ranking_df = _calc_strength_ranking("concept", concept_candidates, market_return)
    if ranking_df is None or ranking_df.empty:
        return pd.DataFrame()

    _save_cache(
        build_sector_strength_filter(stock_pool),
        concept_ranking=ranking_df.to_dict(orient="records"),
    )
    return ranking_df


def generate_concept_strength_report(
    stock_pool: Optional[pd.DataFrame] = None,
    output_file: str = CONCEPT_STRENGTH_OUTPUT_FILE,
    top_n: int = CONCEPT_STRENGTH_TOP_N,
) -> pd.DataFrame:
    table = get_concept_strength_table(stock_pool)
    if table.empty:
        return table

    if top_n and top_n > 0:
        table = table.head(top_n)

    if output_file:
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            table.to_csv(output_file, index=False, encoding="utf-8-sig")
        except Exception:
            pass

    return table


def _collect_candidates(stock_pool: Optional[pd.DataFrame]) -> tuple[Set[str], Set[str]]:
    industries: Set[str] = set()
    concepts: Set[str] = set()

    if stock_pool is None or stock_pool.empty:
        return industries, concepts

    for _, row in stock_pool.iterrows():
        code = row.get("代码") or row.get("code")
        if not code:
            continue
        industry = get_stock_industry(code)
        if industry:
            industries.add(industry)
        for concept in get_stock_concepts(code):
            if concept:
                concepts.add(concept)

    return industries, concepts


def _get_market_return() -> Optional[float]:
    try:
        index_df = get_index_daily_history()
        if index_df is None or index_df.empty or len(index_df) < SECTOR_STRENGTH_LOOKBACK + 1:
            return None
        close = index_df["close"].astype(float)
        return close.iloc[-1] / close.iloc[-(SECTOR_STRENGTH_LOOKBACK + 1)] - 1
    except Exception:
        return None


def _calc_strong_names(kind: str, candidates: Set[str], market_return: Optional[float]) -> Set[str]:
    if not candidates:
        return set()

    results = []
    for name in candidates:
        hist = _fetch_board_history(kind, name)
        if hist is None or hist.empty:
            continue

        close = _extract_close(hist)
        if close is None or len(close) < SECTOR_STRENGTH_LOOKBACK + 1:
            continue

        ret = close.iloc[-1] / close.iloc[-(SECTOR_STRENGTH_LOOKBACK + 1)] - 1
        excess = ret - market_return if market_return is not None else None
        results.append((name, ret, excess))

    if not results:
        return set()

    df = pd.DataFrame(results, columns=["name", "return", "excess"])
    df["rank"] = df["return"].rank(pct=True)

    if SECTOR_STRENGTH_REQUIRE_EXCESS and market_return is not None:
        df = df[df["excess"] > 0]

    threshold = 1 - SECTOR_STRENGTH_TOP_PCT
    strong = df[df["rank"] >= threshold]["name"].tolist()
    return set(strong)


def _calc_strength_ranking(
    kind: str,
    candidates: Set[str],
    market_return: Optional[float],
) -> pd.DataFrame:
    if not candidates:
        return pd.DataFrame()

    results = []
    for name in candidates:
        hist = _fetch_board_history(kind, name)
        if hist is None or hist.empty:
            continue

        close = _extract_close(hist)
        if close is None or len(close) < SECTOR_STRENGTH_LOOKBACK + 1:
            continue

        ret = close.iloc[-1] / close.iloc[-(SECTOR_STRENGTH_LOOKBACK + 1)] - 1
        excess = ret - market_return if market_return is not None else None
        results.append((name, ret, excess))

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results, columns=["概念", "20日涨幅", "超额收益"])
    df["强度排名"] = df["20日涨幅"].rank(pct=True)
    df = df.sort_values("20日涨幅", ascending=False).reset_index(drop=True)
    return df


def _fetch_board_history(kind: str, name: str) -> Optional[pd.DataFrame]:
    try:
        import akshare as ak
    except Exception:
        return None

    try:
        if kind == "industry":
            return ak.stock_board_industry_hist_em(symbol=name)
        if kind == "concept":
            return ak.stock_board_concept_hist_em(symbol=name)
    except Exception:
        return None
    return None


def _extract_close(df: pd.DataFrame) -> Optional[pd.Series]:
    for col in ["收盘", "close", "最新价", "收盘价"]:
        if col in df.columns:
            return df[col].astype(float)
    return None


def _load_cache() -> Optional[SectorStrengthFilter]:
    if not SECTOR_STRENGTH_CACHE_FILE or not os.path.exists(SECTOR_STRENGTH_CACHE_FILE):
        return None

    try:
        with open(SECTOR_STRENGTH_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    if data.get("date") != datetime.now().strftime("%Y-%m-%d"):
        return None

    industries = set(data.get("industries", []))
    concepts = set(data.get("concepts", []))
    filt = SectorStrengthFilter(industries, concepts)
    concept_ranking = data.get("concept_ranking", [])
    if concept_ranking:
        setattr(filt, "concept_ranking", concept_ranking)
    return filt


def _save_cache(filt: SectorStrengthFilter, concept_ranking=None) -> None:
    if not SECTOR_STRENGTH_CACHE_FILE:
        return
    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "industries": sorted(list(filt.strong_industries)),
        "concepts": sorted(list(filt.strong_concepts)),
    }
    if concept_ranking is not None:
        data["concept_ranking"] = concept_ranking
    try:
        os.makedirs(os.path.dirname(SECTOR_STRENGTH_CACHE_FILE), exist_ok=True)
        with open(SECTOR_STRENGTH_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        return
