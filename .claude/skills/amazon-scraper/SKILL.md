---
name: amazon-scraper
description: Architecture and gotchas for the nodriver-based Amazon search scraper in this repo. Load when modifying amazon_scraper.py, adding new extraction fields, changing the overlay, or debugging empty/malformed output.
---

# Amazon Scraper Architecture

Single-file async scraper ([amazon_scraper.py](../../../amazon_scraper.py)) built on `nodriver` (undetected Chrome automation). Event loop is driven by `uc.loop()`, not `asyncio.run` — nodriver manages its own loop and patching.

## Flow inside `scrape()`

1. `uc.start()` launches a patched Chrome with `BROWSER_ARGS` (automation flags off, `en-US`, 1440×900).
2. Load `amazon.com`, inject the LED CSS + toast overlay, then run `set_location()` to drive the ZIP-code popover (`#nav-global-location-popover-link` → `#GLUXZipUpdateInput` → submit → close). ZIP is hard-coded to `10001` at module top.
3. Navigate to `/s?k=<keyword>`, re-inject overlay (new page = fresh DOM), and run `EXTRACT_JS` in one shot.
4. Iterate results in Python, toggling `.led-scan-active` per card via `highlight_card()` and updating the `#led-toast` counter. Delays are 0.08s before extract, 0.03s after — both only apply in visual mode.

## nodriver quirk — JSON bridge

`tab.evaluate()` does NOT reliably deserialize arrays of objects; nested fields come back as empty strings. `EXTRACT_JS` therefore ends with `return JSON.stringify(out)` and Python re-parses it. When adding new evaluate calls that return structured data, do the same — do not rely on automatic deserialization.

## Extraction selectors

Amazon search cards have two traps:
- The outer `h2` often contains only the **brand** (e.g. "Rustler"), not the product title. The real title is under `h2 a span` or in the `aria-label` of the `a.a-link-normal[href*="/dp/"]` anchor. `EXTRACT_JS` tries these in order and falls back to raw h2 text.
- Review counts appear in multiple places; the reliable one is the `aria-label` on the reviews link, parsed with `/([\d,]+)/`. Rating is extracted from `"X out of 5"` text via regex to return just the number.

Valid-card filter: must have both a `data-asin` attribute and non-empty h2 text. Sponsored/placeholder slots without these are skipped in JS, before they reach Python.

## Overlay

CSS lives in the `LED_CSS` constant and is injected via a `<style id="led-scan-style">` tag; the toast is a fixed-position `<div id="led-toast">`. Re-injection is idempotent (guarded by `getElementById`). If you navigate to a new page, call `inject_overlay()` again — the style and toast don't survive navigation.
