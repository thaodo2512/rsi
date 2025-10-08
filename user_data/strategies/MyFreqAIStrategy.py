from typing import Dict, Optional

import logging

import numpy as np
import pandas as pd

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
)
from freqtrade.enums import RunMode

try:
    import talib.abstract as ta
except Exception as e:  # pragma: no cover - container provides TA-Lib
    ta = None  # type: ignore

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
except Exception:
    SentimentIntensityAnalyzer = None  # type: ignore

import os
import requests


logger = logging.getLogger(__name__)


class MyFreqAIStrategy(IStrategy):
    # Core settings
    timeframe = "5m"
    process_only_new_candles = True
    startup_candle_count = 200

    # Minimal ROI and stoploss for scalping focus
    minimal_roi = {
        "0": 0.02,
        "30": 0.01,
        "90": 0
    }

    stoploss = -0.03

    use_exit_signal = True
    exit_profit_only = False
    ignore_buying_expired_candle_after = 120

    plot_config = {
        "main_plot": {
            "close": {"color": "white"},
        },
        "subplots": {
            "RSI": {"rsi": {"color": "blue"}},
            "ADX": {"adx": {"color": "orange"}},
            "WILLR": {"willr": {"color": "purple"}},
            "Sentiment": {
                "sentiment_normalized": {"color": "green"},
                "fear_greed": {"color": "red"}
            },
        },
    }

    # Optional hyperopt ranges (kept minimal)
    rsi_period = IntParameter(9, 21, default=14, space="buy")
    willr_period = IntParameter(10, 21, default=14, space="buy")
    adx_min = IntParameter(20, 35, default=25, space="buy")
    sentiment_floor = DecimalParameter(0.0, 1.0, default=0.0, decimals=2, space="buy")

    def informative_pairs(self):
        return []

    # ---------- Feature helpers ----------
    def add_sentiment_features(self, dataframe: pd.DataFrame, metadata: Dict) -> pd.DataFrame:
        """Add sentiment features using VADER when available. Fallback to neutral.
        This is a lightweight placeholder fetching stubbed texts – replace with real API calls.
        """
        # Disable network during backtesting/hyperopt to keep runs reproducible
        if self._is_historic_run():
            dataframe["sentiment_compound"] = 0.0
            dataframe["sentiment_normalized"] = 0.5
            return dataframe
        try:
            analyzer = SentimentIntensityAnalyzer() if SentimentIntensityAnalyzer else None
        except Exception:
            analyzer = None

        score: Optional[float] = None
        if analyzer:
            try:
                texts = [
                    f"{metadata.get('pair', 'PAIR')} bullish momentum!",
                    f"Concerns around {metadata.get('pair', 'PAIR')} pullback",
                ]
                scores = [analyzer.polarity_scores(t)["compound"] for t in texts]
                score = float(pd.Series(scores).mean())
            except Exception as e:
                logger.warning("Sentiment analysis failed, defaulting neutral: %s", e)

        if score is None:
            score = 0.0

        dataframe["sentiment_compound"] = score
        # Normalize [-1,1] -> [0,1]
        dataframe["sentiment_normalized"] = (dataframe["sentiment_compound"] + 1.0) / 2.0
        return dataframe

    def add_fear_greed(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Attach Fear & Greed Index.
        Priority: use historical CSV if present -> live API (non-historic only) -> neutral 0.5.
        """
        # Try historical CSV merge first (reproducible backtests)
        try:
            fg_path = os.path.join("/freqtrade", "user_data", "data", "fear_greed.csv")
            if os.path.exists(fg_path):
                fg = pd.read_csv(fg_path)
                # Expect columns: date (YYYY-MM-DD), value (0..100)
                if {"date", "value"}.issubset(set(fg.columns)) and "date" in dataframe.columns:
                    fg["date"] = pd.to_datetime(fg["date"]).dt.date
                    left = dataframe.copy()
                    left["_date_only"] = pd.to_datetime(left["date"]).dt.date
                    fg["fear_greed"] = fg["value"].astype(float) / 100.0
                    merged = left.merge(
                        fg[["date", "fear_greed"]],
                        left_on="_date_only",
                        right_on="date",
                        how="left",
                    )
                    dataframe["fear_greed"] = merged["fear_greed"].fillna(0.5).values
                    return dataframe
        except Exception as e:  # pragma: no cover
            logger.warning("Failed to merge historical Fear&Greed: %s", e)

        # Live fetch only when not backtesting/hyperopting
        fg_value = 0.5
        if not self._is_historic_run():
            try:
                resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
                if resp.ok:
                    fg_value = int(resp.json()["data"][0]["value"]) / 100.0
            except Exception as e:
                logger.warning("Fear&Greed fetch failed, using neutral 0.5: %s", e)

        dataframe["fear_greed"] = fg_value
        return dataframe

    # ---------- Indicators & Signals ----------
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: Dict) -> pd.DataFrame:
        # RSI and WILLR
        if ta is None:
            # Basic numpy fallbacks if TA-Lib not present (very rough)
            dataframe["rsi"] = pd.Series(np.nan, index=dataframe.index)
            dataframe["willr"] = pd.Series(np.nan, index=dataframe.index)
            dataframe["adx"] = pd.Series(np.nan, index=dataframe.index)
            logger.warning("TA-Lib not available: indicators set to NaN; no trades will trigger.")
        else:
            dataframe["rsi"] = ta.RSI(dataframe, timeperiod=int(self.rsi_period.value))
            dataframe["willr"] = ta.WILLR(dataframe, timeperiod=int(self.willr_period.value))
            dataframe["adx"] = ta.ADX(dataframe)

        # Add sentiment & fear/greed
        dataframe = self.add_sentiment_features(dataframe, metadata)
        dataframe = self.add_fear_greed(dataframe)

        # Volume rolling mean (basic filter)
        if "volume" in dataframe.columns:
            dataframe["vol_sma50"] = dataframe["volume"].rolling(50).mean()

        # Attempt FreqAI pipeline (safe no-op if disabled or unavailable)
        try:
            if getattr(self, "freqai", None):
                dataframe = self.freqai.start(dataframe, metadata, self)
        except Exception as e:  # pragma: no cover
            logger.warning("FreqAI integration skipped due to error: %s", e)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: Dict) -> pd.DataFrame:
        dataframe.loc[:, "enter_long"] = 0

        cond = (
            (dataframe["rsi"] < 30)
            & (dataframe["willr"] < -80)
            & (dataframe["adx"] > int(self.adx_min.value))
        )

        # Optional volume filter when available
        if "vol_sma50" in dataframe.columns:
            cond &= dataframe["volume"] > dataframe["vol_sma50"].fillna(0)

        # Optional sentiment floor if provided via hyperopt/config (default 0.0 = disabled)
        if "sentiment_normalized" in dataframe.columns and float(self.sentiment_floor.value) > 0.0:
            cond &= dataframe["sentiment_normalized"] >= float(self.sentiment_floor.value)

        # Optional FreqAI gating if predictions exist
        if "do_predict" in dataframe.columns:
            cond &= dataframe["do_predict"] == 1
        if "DI_values" in dataframe.columns:
            cond &= dataframe["DI_values"].fillna(1.0) < 0.05

        dataframe.loc[cond, ["enter_long"]] = 1

        return dataframe

    # ---------- FreqAI hooks ----------
    def set_freqai_targets(self, dataframe: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """Define regression target as forward return over N candles (label_period_candles)."""
        try:
            n = int(self.freqai_info["feature_parameters"].get("label_period_candles", 12))
        except Exception:
            n = 12
        future_close = dataframe["close"].shift(-n)
        dataframe["&-return"] = (future_close / dataframe["close"]) - 1.0
        return dataframe

    def feature_engineering_standard(self, dataframe: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """Provide core features for FreqAI. Columns must be prefixed with '%-'."""
        # Ensure base indicators exist
        if "rsi" not in dataframe.columns and ta is not None:
            dataframe["rsi"] = ta.RSI(dataframe, timeperiod=int(self.rsi_period.value))
        if "willr" not in dataframe.columns and ta is not None:
            dataframe["willr"] = ta.WILLR(dataframe, timeperiod=int(self.willr_period.value))
        if "adx" not in dataframe.columns and ta is not None:
            dataframe["adx"] = ta.ADX(dataframe)

        dataframe["%-rsi"] = dataframe.get("rsi")
        dataframe["%-willr"] = dataframe.get("willr")
        dataframe["%-adx"] = dataframe.get("adx")
        if "fear_greed" in dataframe.columns:
            dataframe["%-fear_greed"] = dataframe["fear_greed"].fillna(0.5)
        if "sentiment_normalized" in dataframe.columns:
            dataframe["%-sentiment"] = dataframe["sentiment_normalized"].fillna(0.5)
        if "volume" in dataframe.columns:
            if "vol_sma50" not in dataframe.columns:
                dataframe["vol_sma50"] = dataframe["volume"].rolling(50).mean()
            dataframe["%-vol_above_sma50"] = (dataframe["volume"] > dataframe["vol_sma50"].fillna(0)).astype(float)
        return dataframe

    # ---------- Helpers ----------
    def _is_historic_run(self) -> bool:
        """True for backtesting/hyperopt to ensure reproducibility (no live APIs)."""
        try:
            return bool(self.dp and self.dp.runmode in {RunMode.BACKTEST, RunMode.HYPEROPT})
        except Exception:
            return False

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: Dict) -> pd.DataFrame:
        dataframe.loc[:, "exit_long"] = 0

        # Simple exit: Overbought or profit target met by ROI table
        dataframe.loc[
            (
                (dataframe["rsi"] > 70)
                | (dataframe["willr"] > -20)
            ),
            ["exit_long"],
        ] = 1

        return dataframe
