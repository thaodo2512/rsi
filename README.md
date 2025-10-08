# AI-Driven Crypto Trading (Freqtrade + FreqAI)

This repo scaffolds an adaptive RSI + WILLR strategy for Freqtrade with optional FreqAI and GPU acceleration.

Quickstart
- Ensure Docker and Docker Compose are installed. For GPU usage, install NVIDIA drivers + Container Toolkit.
- First build (installs FreqAI deps like datasieve/torch): `docker compose build`
- Start the bot in dry-run: `docker compose up -d`
- Open FreqUI: http://localhost:8080
- Edit pairs and API keys in `user_data/config.json` (dry-run is enabled by default)

Key Files
- `docker-compose.yml` – Freqtrade service with optional NVIDIA GPU.
- `user_data/config.json` – Bot config (pairs, exchange, web UI, etc.).
- `user_data/strategies/MyFreqAIStrategy.py` – RSI + WILLR + ADX with sentiment and Fear & Greed.
- `user_data/requirements.txt` – Extra deps (VADER sentiment), optional.

Notes
- Sentiment and Fear & Greed fetch gracefully degrade to neutral if unavailable.
- Fear & Greed for backtesting: place a CSV at `user_data/data/fear_greed.csv` with columns `date,value` (see `user_data/data/fear_greed.example.csv`). Or run `python scripts/fetch_fear_greed.py` to download history.
- FreqAI is configured inside `user_data/config.json` under the `freqai` key and enabled by default. Compose passes `--freqaimodel LightGBMRegressor` (dependency preinstalled in our image). You can switch models in `docker-compose.yml` if desired.
- Logs are sent to stdout/stderr; use `docker compose logs -f` instead of a file path to avoid permission issues on bind mounts.
- If you see permission errors writing under `user_data/`, run: `scripts/fix_perms.sh` to set ownership to container user (1000:1000).
- This is a starting point; use Freqtrade backtesting/hyperopt to calibrate periods and thresholds.

Backtesting
- Download enough data (train_period_days + backtest window), e.g.: `./scripts/download.sh 5m "BTC/USDT ETH/USDT" 420`
- Run backtest over a date range: `./scripts/backtest.sh 2023-01-01 2023-12-31`
- View results in console output and `user_data/backtest_results/` (if generated)

Disclaimer: For educational use only. Not financial advice.
