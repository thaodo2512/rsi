# Repository Guidelines

This repository hosts a Freqtrade-based crypto bot with optional FreqAI integration, focused on RSI + WILLR + ADX signals and sentiment augmentation.

## Project Structure & Module Organization
- `docker-compose.yml` – Runs Freqtrade (GPU-ready via NVIDIA Container Toolkit).
- `user_data/config.json` – Bot configuration (pairs, exchange, web UI, dry-run).
- `user_data/strategies/MyFreqAIStrategy.py` – Main strategy: RSI + WILLR + ADX, sentiment, Fear & Greed.
-- FreqAI is configured under the `freqai` key in `user_data/config.json`.
- `user_data/requirements.txt` – Extra Python deps for strategies (installed in container as needed).
- `desgin_spec` – System design notes and rationale.

## Build, Test, and Development Commands
- Start (dry-run): `docker compose up -d`
- Stop: `docker compose down`
- Download data: `docker compose run --rm freqtrade download-data -t 5m -p BTC/USDT ETH/USDT`
- Backtest: `docker compose run --rm freqtrade backtesting -c /freqtrade/user_data/config.json --strategy MyFreqAIStrategy -s 2023-01-01 -e 2023-12-31`
- Hyperopt: `docker compose run --rm freqtrade hyperopt -c /freqtrade/user_data/config.json --strategy MyFreqAIStrategy --spaces buy sell`

## Coding Style & Naming Conventions
- Python, PEP 8, 4-space indent, ~100 char lines.
- `snake_case` for functions/vars, `PascalCase` for classes, `UPPER_CASE` constants.
- Type hints for public methods; concise Google-style docstrings.
- Keep strategy functions pure and fast; avoid heavy I/O in candle loops.

## Testing Guidelines
- Prefer Freqtrade backtesting/hyperopt with fixed seeds/periods for reproducibility.
- If adding unit tests, use `pytest` and mirror strategy structure; keep tests offline.
- Include example commands, configs, and expected KPIs in PRs.

## Commit & Pull Request Guidelines
- Conventional Commits: `feat`, `fix`, `docs`, `chore`, `perf`, `test`, `ci` (e.g., `feat: add WILLR filter`).
- Branch names: `type/short-description` (e.g., `feat/rsi-willr-entry`).
- PRs: clear description, linked issues, logs/screenshots, backtest/hyperopt results, and config diffs.

## Security & Configuration Tips
- Do not commit API keys or secrets; keep `dry_run` true until validated.
- Large data/logs/DB files are gitignored; use Git LFS for binaries if needed.
- Respect API rate limits; cache external signals; degrade gracefully when offline.
