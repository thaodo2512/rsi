# AI-Driven Crypto Trading (Freqtrade + FreqAI)

This repo scaffolds an adaptive RSI + WILLR strategy for Freqtrade with optional FreqAI and GPU acceleration.

Quickstart
- Ensure Docker, Docker Compose, and NVIDIA drivers + Container Toolkit are installed for GPU use.
- Start the bot in dry-run: `docker compose up -d`.
- Open FreqUI: http://localhost:8080.
- Edit pairs and API keys in `user_data/config.json` (dry-run is enabled by default).

Key Files
- `docker-compose.yml` – Freqtrade service with optional NVIDIA GPU.
- `user_data/config.json` – Bot config (pairs, exchange, web UI, etc.).
- `user_data/strategies/MyFreqAIStrategy.py` – RSI + WILLR + ADX with sentiment and Fear & Greed.
- `user_data/freqai_config.json` – Sample FreqAI settings (LSTM-Transformer style; adjust as needed).
- `user_data/requirements.txt` – Extra deps (VADER sentiment), optional.

Notes
- Sentiment and Fear & Greed fetch gracefully degrade to neutral if unavailable.
- Fear & Greed for backtesting: place a CSV at `user_data/data/fear_greed.csv` with columns `date,value` (see `user_data/data/fear_greed.example.csv`). Or run `python scripts/fetch_fear_greed.py` to download history.
- FreqAI is enabled by default via `--freqai-config /freqtrade/user_data/freqai_config.json` in `docker-compose.yml`.
- This is a starting point; use Freqtrade backtesting/hyperopt to calibrate periods and thresholds.

Disclaimer: For educational use only. Not financial advice.
