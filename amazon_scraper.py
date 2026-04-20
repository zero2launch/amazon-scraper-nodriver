import asyncio
import csv
import json
import re
import sys
from urllib.parse import quote_plus

import nodriver as uc


BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--lang=en-US",
    "--window-size=1440,900",
    "--no-first-run",
    "--no-default-browser-check",
]

ZIP_CODE = "10001"

LED_CSS = """
@keyframes led-pulse {
  0%   { box-shadow: 0 0 0 0 rgba(0,170,255,0.9), 0 0 16px 4px rgba(0,170,255,0.6) inset; }
  50%  { box-shadow: 0 0 22px 8px rgba(0,170,255,0.9), 0 0 40px 12px rgba(0,200,255,0.7) inset; }
  100% { box-shadow: 0 0 0 0 rgba(0,170,255,0.0), 0 0 16px 4px rgba(0,170,255,0.6) inset; }
}
@keyframes led-sweep {
  0%   { transform: translateX(-110%); opacity: 0; }
  20%  { opacity: 1; }
  100% { transform: translateX(110%); opacity: 0; }
}
.led-scan-active {
  position: relative !important;
  outline: 2px solid #00aaff !important;
  border-radius: 6px !important;
  animation: led-pulse 0.9s ease-in-out infinite !important;
  transition: outline-color 0.2s ease !important;
  overflow: hidden !important;
}
.led-scan-active::after {
  content: "";
  position: absolute;
  top: 0; left: 0;
  width: 40%; height: 100%;
  background: linear-gradient(90deg,
    rgba(255,255,255,0) 0%,
    rgba(120,220,255,0.35) 40%,
    rgba(255,255,255,0.9) 50%,
    rgba(120,220,255,0.35) 60%,
    rgba(255,255,255,0) 100%);
  pointer-events: none;
  animation: led-sweep 0.9s linear infinite;
  z-index: 9999;
}
#led-toast {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 2147483647;
  padding: 10px 16px;
  background: rgba(10,15,25,0.88);
  color: #cfefff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 14px;
  font-weight: 600;
  border: 1px solid rgba(0,170,255,0.6);
  border-radius: 10px;
  box-shadow: 0 6px 24px rgba(0,170,255,0.35), 0 0 0 1px rgba(0,170,255,0.2) inset;
  backdrop-filter: blur(6px);
  letter-spacing: 0.2px;
}
"""


async def inject_overlay(tab):
    js = f"""
    (() => {{
      if (document.getElementById('led-scan-style')) return;
      const st = document.createElement('style');
      st.id = 'led-scan-style';
      st.textContent = {json.dumps(LED_CSS)};
      document.head.appendChild(st);
      const t = document.createElement('div');
      t.id = 'led-toast';
      t.textContent = '⚡ Starting…';
      document.body.appendChild(t);
    }})();
    """
    await tab.evaluate(js)


async def set_toast(tab, text):
    await tab.evaluate(
        f"(() => {{ const t = document.getElementById('led-toast'); "
        f"if (t) t.textContent = {json.dumps(text)}; }})();"
    )


async def highlight_card(tab, asin, on=True):
    if on:
        js = (
            f"(() => {{ const el = document.querySelector('[data-asin={json.dumps(asin)}]'); "
            f"if (el) {{ el.classList.add('led-scan-active'); "
            f"el.scrollIntoView({{behavior:'smooth', block:'center'}}); }} }})();"
        )
    else:
        js = (
            f"(() => {{ const el = document.querySelector('[data-asin={json.dumps(asin)}]'); "
            f"if (el) el.classList.remove('led-scan-active'); }})();"
        )
    await tab.evaluate(js)


def clean(s):
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


async def set_location(tab, zip_code):
    try:
        await tab.evaluate(
            "(() => { const b = document.querySelector('#nav-global-location-popover-link'); "
            "if (b) b.click(); })();"
        )
        await asyncio.sleep(1.5)
        await tab.evaluate(
            f"(() => {{ const i = document.querySelector('#GLUXZipUpdateInput'); "
            f"if (i) {{ i.value = {json.dumps(zip_code)}; "
            f"i.dispatchEvent(new Event('input', {{bubbles:true}})); }} }})();"
        )
        await asyncio.sleep(0.5)
        await tab.evaluate(
            "(() => { const btns = document.querySelectorAll('#GLUXZipUpdate input, "
            "#GLUXZipUpdate span input, #GLUXZipInputSection input[type=submit]'); "
            "for (const b of btns) { b.click(); break; } })();"
        )
        await asyncio.sleep(1.5)
        await tab.evaluate(
            "(() => { const c = document.querySelector("
            "'.a-popover-footer input[name=\"glowDoneButton\"], "
            ".a-popover-footer .a-button-input, "
            "button[name=\"glowDoneButton\"]'); "
            "if (c) c.click(); })();"
        )
        await asyncio.sleep(1.5)
    except Exception as e:
        print(f"[warn] location set: {e}", file=sys.stderr)


EXTRACT_JS = """
(() => {
  const cards = document.querySelectorAll('div.s-result-item[data-asin], div[data-component-type="s-search-result"]');
  const out = [];
  cards.forEach(el => {
    const asin = el.getAttribute('data-asin') || '';
    const h2 = el.querySelector('h2');
    if (!asin || !h2) return;
    const h2txt = (h2.innerText || h2.textContent || '').trim();
    if (!h2txt) return;

    let title = '';
    const titleLink = el.querySelector('a.a-link-normal[href*="/dp/"] h2 span, h2 a span, a h2 span');
    if (titleLink) title = (titleLink.innerText || titleLink.textContent || '').trim();
    if (!title) {
      const titleA = el.querySelector('a.a-link-normal[href*="/dp/"][aria-label], a.a-text-normal[aria-label]');
      if (titleA) title = (titleA.getAttribute('aria-label') || '').trim();
    }
    if (!title) title = h2txt;

    let link = '';
    const a = el.querySelector('a.a-link-normal[href*="/dp/"], h2 a, a.a-link-normal.s-no-outline');
    if (a) link = a.getAttribute('href') || '';
    if (link && link.startsWith('/')) link = 'https://www.amazon.com' + link;

    let price = '';
    const priceWhole = el.querySelector('.a-price .a-offscreen');
    if (priceWhole) price = priceWhole.textContent.trim();

    let rating = '';
    const r = el.querySelector('span.a-icon-alt, i.a-icon-star-small span.a-icon-alt, i.a-icon-star span.a-icon-alt');
    if (r) rating = (r.textContent || '').trim();
    const rm = rating.match(/([0-9.]+)\s*out of\s*5/i);
    if (rm) rating = rm[1];

    let reviews = '';
    const rvLink = el.querySelector('a[href*="#customerReviews"], a.a-link-normal[aria-label*="ratings"], a.a-link-normal[aria-label*="reviews"]');
    if (rvLink) {
      const al = rvLink.getAttribute('aria-label') || '';
      const m = al.match(/([\d,]+)/);
      if (m) reviews = m[1];
      if (!reviews) {
        const s = rvLink.querySelector('span');
        if (s) reviews = (s.textContent || '').trim();
      }
    }
    if (!reviews) {
      const allSpans = el.querySelectorAll('span.a-size-base.s-underline-text, span.a-size-base');
      for (const s of allSpans) {
        const t = (s.textContent || '').trim();
        if (/^[\d,]+$/.test(t)) { reviews = t; break; }
      }
    }

    let img = '';
    const im = el.querySelector('img.s-image');
    if (im) img = im.getAttribute('src') || '';

    out.push({ asin, title, price, rating, reviews, url: link, image: img });
  });
  return JSON.stringify(out);
})();
"""


async def scrape(keyword: str, headless: bool = False):
    browser = await uc.start(headless=headless, browser_args=BROWSER_ARGS, lang="en-US")
    try:
        tab = await browser.get("https://www.amazon.com/")
        await asyncio.sleep(2.0)

        if not headless:
            await inject_overlay(tab)
            await set_toast(tab, "📍 Setting location…")

        await set_location(tab, ZIP_CODE)

        url = f"https://www.amazon.com/s?k={quote_plus(keyword)}"
        tab = await browser.get(url)
        await asyncio.sleep(2.5)

        if not headless:
            await inject_overlay(tab)
            await set_toast(tab, "🔎 Loading results…")

        raw_str = await tab.evaluate(EXTRACT_JS)
        if isinstance(raw_str, str):
            raw = json.loads(raw_str)
        elif isinstance(raw_str, list):
            raw = raw_str
        else:
            raw = []

        total = len(raw)
        items = []
        for i, r in enumerate(raw, start=1):
            asin = r.get("asin", "")
            if not headless:
                await set_toast(tab, f"⚡ Crawling {i}/{total}")
                await highlight_card(tab, asin, on=True)
                await asyncio.sleep(0.08)

            item = {
                "index": i,
                "title": clean(r.get("title")),
                "price": clean(r.get("price")),
                "rating": clean(r.get("rating")),
                "reviews": clean(r.get("reviews")),
                "url": clean(r.get("url")),
                "image": clean(r.get("image")),
            }
            items.append(item)

            if not headless:
                await asyncio.sleep(0.03)
                await highlight_card(tab, asin, on=False)

        if not headless:
            await set_toast(tab, f"✅ Done — {len(items)} items")
            await asyncio.sleep(1.2)

        return items
    finally:
        try:
            browser.stop()
        except Exception:
            pass


def save_json(items, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def save_csv(items, path):
    fields = ["index", "title", "price", "rating", "reviews", "url", "image"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for it in items:
            w.writerow({k: it.get(k, "") for k in fields})


async def main():
    keyword = sys.argv[1] if len(sys.argv) > 1 else "mechanical keyboard"
    headless = "--headless" in sys.argv
    items = await scrape(keyword, headless=headless)
    save_json(items, "amazon_items.json")
    save_csv(items, "amazon_items.csv")
    print(f"Saved {len(items)} items → amazon_items.json, amazon_items.csv")


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
