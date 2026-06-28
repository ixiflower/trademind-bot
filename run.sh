#!/bin/bash
# TradeMind Signal Bot - Runner
cd "$(dirname "$0")"
source .venv/bin/activate
python3 bot.py
