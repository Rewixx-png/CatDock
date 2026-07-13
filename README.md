# CatDock

Lightweight userbot hosting platform. Forked and stripped from RewHost v5.0.0.

## Features
- Docker-based userbot containers
- Telegram bot management
- Web terminal with command buttons
- FastAPI REST API
- Multi-payment billing (Crypto, Cards, Stars)
- `--no-web` mode for bot-only deployment
- Heroku-ready (Procfile included)

## Quick Start

```bash
cp .env.example .env
# Edit .env with your bot token and settings
python bot.py
```

### With --no-web (bot only):
```bash
python bot.py --no-web
```

### On Heroku:
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

## Requirements
- Python 3.10+
- PostgreSQL 15
- Redis 7
- Docker (on worker nodes)
