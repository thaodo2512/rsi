from typing import Dict, Optional

import logging

import numpy as np
import pandas as pd

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, CategoricalParameter

try:
    import talib.abstract as ta
except Exception as e:  # pragma: no cover - container provides TA-Lib
    ta = None  # type: ignore

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
except Exception:
    SentimentIntensityAnalyzer = None  # type: ignore

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

    def informative_pairs(self):
        return []

    # ---------- Feature helpers ----------
    def add_sentiment_features(self, dataframe: pd.DataFrame, metadata: Dict) -> pd.DataFrame:
        """Add sentiment features using VADER when available. Fallback to neutral.
        This is a lightweight placeholder fetching stubbed texts – replace with real API calls.
        """
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
        """Fetch CNN/Alternative.me Fear & Greed Index, fallback to 0.5 neutral."""
        fg_value = 0.5
        try:
            resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
            if resp.ok:
                fg_value = int(resp.json()["data"][0]["value"]) / 100.0
        except Exception as e:
            logger.info("Fear&Greed fetch failed, using neutral 0.5: %s", e)

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
        else:
            dataframe["rsi"] = ta.RSI(dataframe, timeperiod=int(self.rsi_period.value))
            dataframe["willr"] = ta.WILLR(dataframe, timeperiod=int(self.willr_period.value))
            dataframe["adx"] = ta.ADX(dataframe)

        # Add sentiment & fear/greed
        dataframe = self.add_sentiment_features(dataframe, metadata)
        dataframe = self.add_fear_greed(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: Dict) -> pd.DataFrame:
        dataframe.loc[:, "enter_long"] = 0

        dataframe.loc[
            (
                (dataframe["rsi"] < 30)
                & (dataframe["willr"] < -80)
                & (dataframe["adx"] > int(self.adx_min.value))
            ),
            ["enter_long"],
        ] = 1

        return dataframe

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
