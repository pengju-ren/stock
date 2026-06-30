"""数据加载层 — 从 stock-analyzer 缓存或自定义文件读取 K 线数据。

支持的来源:
  1. stock-analyzer 缓存（默认）:
     - A 股: a_kline_500d_v2.csv
     - ETF:  etf_kline_v1.csv
     - 港股: hstech_kline_v1.csv
  2. 用户自定义 CSV/Excel 文件

输出格式: 统一的 DataFrame，列 [code, date, open, high, low, close, volume]
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    import numpy as np

# 默认 stock-analyzer 缓存目录
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "stock-analyzer" / "data" / "cache"

# 缓存文件映射
CACHE_FILES = {
    "A": "a_kline_500d_v2.csv",
    "ETF": "etf_kline_v1.csv",
    "HK": "hstech_kline_v1.csv",
}

# 不同文件的列名标准化映射
# stock-analyzer 的 A 股 kline: code, date, open, high, low, close, preclose, volume, amount, ...
# ETF kline: date, open, high, low, close, volume, amount, turn, code
# hstech: same as ETF

REQUIRED_COLS = ["code", "date", "open", "high", "low", "close", "volume"]


def _normalize_columns(df: pd.DataFrame, market: str) -> pd.DataFrame:
    """标准化列名，确保包含 REQUIRED_COLS。"""
    # 确保 code 列存在
    if "code" not in df.columns:
        raise ValueError(f"数据缺少 'code' 列。可用列: {list(df.columns)}")

    # 统一 code 为字符串，去掉 .0 后缀
    df = df.copy()
    df["code"] = df["code"].astype(str).str.replace(r"\.0$", "", regex=True)

    # 确保必需列都在
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"数据缺少必需列: {missing}")

    # 只保留必需列 + name 列（如果有）
    keep = list(REQUIRED_COLS)
    if "name" in df.columns:
        keep.append("name")

    return df[keep]


def get_cache_path(market: str = "A", cache_dir: str | Path | None = None) -> Path:
    """获取指定市场的缓存文件路径。

    Args:
        market: "A" | "ETF" | "HK"
        cache_dir: 自定义缓存目录，默认使用 stock-analyzer 缓存

    Returns:
        缓存文件路径
    """
    base = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    filename = CACHE_FILES.get(market.upper())
    if not filename:
        raise ValueError(f"不支持的市场: {market}。可选: {list(CACHE_FILES)}")
    return base / filename


def load_kline(
    codes: str | list[str] | None = None,
    market: str = "A",
    cache_dir: str | Path | None = None,
    days: int | None = None,
) -> pd.DataFrame:
    """从 stock-analyzer 缓存加载 K 线数据。

    Args:
        codes: 股票代码（单个或列表），None = 全部
        market: 市场 ("A" | "ETF" | "HK")
        cache_dir: 缓存目录路径
        days: 只取最近 N 天数据

    Returns:
        DataFrame with columns: code, date, open, high, low, close, volume
    """
    path = get_cache_path(market, cache_dir)

    if not path.exists():
        raise FileNotFoundError(
            f"缓存文件不存在: {path}\n"
            f"请先运行 stock-analyzer data fetch-a (或 fetch-hk) 拉取数据。"
        )

    dtype_map = {"code": str}
    df = pd.read_csv(str(path), dtype=dtype_map, low_memory=False)

    df = _normalize_columns(df, market)

    # 过滤代码
    if codes is not None:
        if isinstance(codes, str):
            codes = [codes]
        codes_str = [str(c).replace(".0", "") for c in codes]
        df = df[df["code"].isin(codes_str)]

    # 按日期排序
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["code", "date"]).reset_index(drop=True)

    # 只取最近 N 天
    if days is not None and days > 0:
        latest = df["date"].max()
        cutoff = latest - pd.Timedelta(days=days)
        df = df[df["date"] >= cutoff]

    return df


def load_from_file(filepath: str | Path) -> pd.DataFrame:
    """从自定义 CSV/Excel 文件加载 K 线数据。

    文件必须包含列: code, date, open, high, low, close, volume
    支持 .csv / .xlsx / .xls 格式。
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(str(path), dtype={"code": str}, low_memory=False)
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(str(path), dtype={"code": str})
    else:
        raise ValueError(f"不支持的文件格式: {suffix}。支持 .csv / .xlsx / .xls")

    return _normalize_columns(df, market="custom")


def get_stock_list(market: str = "A", cache_dir: str | Path | None = None) -> list[dict]:
    """获取股票列表（代码 + 名称）。

    Returns:
        list of {"code": str, "name": str}
    """
    # 尝试从 stock list 文件读取
    base = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR

    stock_list_path = None
    if market.upper() == "A":
        stock_list_path = base / "a_stock_list_v2.csv"
    elif market.upper() == "HK":
        stock_list_path = base / "hk_stock_list.csv"

    if stock_list_path and stock_list_path.exists():
        df = pd.read_csv(str(stock_list_path), dtype={"code": str})
        df["code"] = df["code"].astype(str).str.replace(r"\.0$", "", regex=True)
        return [{"code": row["code"], "name": row.get("name", "")}
                for _, row in df.iterrows()]

    # Fallback: 从 kline 数据中提取唯一代码
    kline_path = get_cache_path(market, cache_dir)
    if kline_path.exists():
        df = pd.read_csv(str(kline_path), dtype={"code": str}, usecols=["code"])
        codes = df["code"].astype(str).str.replace(r"\.0$", "", regex=True).unique()
        return [{"code": c, "name": ""} for c in sorted(codes)]

    return []


def get_data_summary(cache_dir: str | Path | None = None) -> dict:
    """获取数据概览 — 每个市场有多少只股票、数据范围。"""
    summary = {}
    for market, filename in CACHE_FILES.items():
        path = Path(cache_dir) / filename if cache_dir else DEFAULT_CACHE_DIR / filename
        if path.exists():
            df = pd.read_csv(str(path), dtype={"code": str}, low_memory=False)
            codes = df["code"].astype(str).str.replace(r"\.0$", "", regex=True).unique()
            dates = pd.to_datetime(df["date"])
            summary[market] = {
                "stocks": len(codes),
                "bars": len(df),
                "date_from": str(dates.min().date()),
                "date_to": str(dates.max().date()),
            }
        else:
            summary[market] = {"stocks": 0, "bars": 0, "date_from": "", "date_to": ""}
    return summary
