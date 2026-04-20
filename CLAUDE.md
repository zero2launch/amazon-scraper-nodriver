# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Install dependencies:
```
pip install -r requirements.txt
```

Run scraper (visual mode with LED overlay):
```
python amazon_scraper.py "<keyword>"
```

Run headless (no overlay):
```
python amazon_scraper.py "<keyword>" --headless
```

Default keyword if none passed: `mechanical keyboard`. Output always writes to `amazon_items.json` and `amazon_items.csv` in the working directory (overwrites previous run).

## Architecture

See [.claude/skills/amazon-scraper/SKILL.md](.claude/skills/amazon-scraper/SKILL.md) for the scraper's flow, nodriver quirks, selector traps, and overlay behavior.
