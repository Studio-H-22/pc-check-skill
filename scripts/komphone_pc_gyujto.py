"""KomPhone.hu — új/felújított gamer PC gyűjtő (ingyenes, Playwright).

UNAS webshop. Alapkonfig a termékoldal Memória/SSD mezője (gyakran 16GB + 480GB),
a címbeli 16/32/64GB sáv NEM automatikus 32GB.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE = "https://www.komphone.hu"
DEFAULT_CATEGORIES = [
    f"{BASE}/felujitott-gamer-pc",
    f"{BASE}/belepo-gamer-konfigok-500-000-ft-alatt",
]
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def accept_cookies(page) -> None:
    for sel in [
        "button:has-text('Elfogadom')",
        "button:has-text('ELFOGADOM')",
        "button:has-text('Összes elfogadása')",
        "button:has-text('Accept')",
        "#cookie-accept",
    ]:
        try:
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=2000)
                page.wait_for_timeout(600)
                return
        except Exception:
            continue


def parse_price(text: str | None) -> int | None:
    if not text:
        return None
    # take the last Ft amount if sale/old both present: "5 949 900 Ft 899 900 Ft" -> prefer smaller current?
    # Komphone often shows old then new, or single. Prefer the minimum plausible sale price.
    nums = [int(re.sub(r"\s+", "", n)) for n in re.findall(r"(\d[\d\s]*)\s*Ft", text.replace("\xa0", " "))]
    nums = [n for n in nums if n > 0]
    if not nums:
        return None
    if len(nums) >= 2:
        return min(nums)
    return nums[0]


def parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for item in soup.select(".js-product, div.product.list-1-card-1"):
        a = item.select_one("a.product__name-link, .product__name a[href]")
        if not a:
            continue
        url = urljoin(BASE + "/", a.get("href") or "")
        if url in seen:
            continue
        seen.add(url)
        title = a.get_text(" ", strip=True)
        price_el = item.select_one(".product__price-base, .product__prices")
        price_text = price_el.get_text(" ", strip=True) if price_el else ""
        sku = item.get("data-sku") or item.get("id")
        out.append(
            {
                "id": sku,
                "title": title,
                "url": url.split("?")[0],
                "price_text": price_text,
                "price_huf": parse_price(price_text),
                "description_text": "",
                "specs": {},
                "detail_status": "list_only",
            }
        )
    return out


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    specs: dict[str, str] = {}
    # Label\nValue pattern used on Komphone product pages
    patterns = {
        "Processzor": r"Processzor\n([^\n]+)",
        "Alaplap": r"Alaplap\n([^\n]+)",
        "Memória": r"Memória\n([^\n]+)",
        "Videokártya": r"Videokártya\n([^\n]+)",
        "SSD": r"SSD\n([^\n]+)",
        "Tápegység": r"Tápegység\n([^\n]+)",
        "Ház": r"Ház\n([^\n]+)",
        "Hűtés": r"Hűtés\n([^\n]+)",
        "Garancia": r"Garancia:\n?([^\n]+)",
        "Termék állapota": r"Termék állapota:\n?([^\n]+)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            specs[key] = m.group(1).strip()

    # Bruttó price
    price = None
    m = re.search(r"Bruttó:\s*([\d\s]+)\s*Ft", text)
    if m:
        price = int(re.sub(r"\s+", "", m.group(1)))
    if price is None:
        for sel in [".product-price", ".price", ".product__price-base"]:
            el = soup.select_one(sel)
            if el:
                price = parse_price(el.get_text(" ", strip=True))
                if price:
                    break

    lines = [f"{k}: {v}" for k, v in specs.items()]
    # note base-config reminder in description for scorers
    if re.search(r"16\s*/\s*32|16\s*/\s*32\s*/\s*64|16/32/64", text):
        lines.append(
            "MEGJEGYZÉS: a címbeli 16/32/64GB sáv választható; az alapár a Memória mező szerinti kapacitás."
        )
    return {"specs": specs, "description_text": "\n".join(lines), "price_huf_detail": price}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="KomPhone PC gyűjtő")
    ap.add_argument("--min-price", type=int, default=40000)
    ap.add_argument("--max-price", type=int, default=400000)
    ap.add_argument("--details", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Extra kategória URL; alapból felújított + belépő gamer",
    )
    ap.add_argument("--output", default="komphone-pc.json")
    ap.add_argument("--browser-executable")
    args = ap.parse_args(argv)
    categories = args.categories or DEFAULT_CATEGORIES

    started = time.monotonic()
    deadline = started + args.timeout
    result = {
        "source": "komphone-public-local",
        "schema_version": 1,
        "categories": categories,
        "search": {
            "min_price": args.min_price,
            "max_price": args.max_price,
            "details": args.details,
        },
        "status": "partial",
        "records": [],
        "scraper_cost_usd": 0,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "Címbeli 16/32/64GB nem alapkonfig; a Memória/SSD mező a mérvadó.",
        ],
    }

    launch = {"headless": True}
    if args.browser_executable:
        launch["executable_path"] = args.browser_executable

    by_url: dict[str, dict] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch)
        page = browser.new_page(locale="hu-HU", user_agent=USER_AGENT)
        try:
            for cat in categories:
                if time.monotonic() >= deadline:
                    break
                print(f"-> KomPhone lista: {cat}")
                page.goto(cat, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1800)
                accept_cookies(page)
                cards = parse_list(page.content())
                print(f"   kártyák: {len(cards)}")
                for c in cards:
                    by_url.setdefault(c["url"], c)

            records = list(by_url.values())
            for r in records[: args.details]:
                if time.monotonic() >= deadline:
                    r["detail_status"] = "timeout"
                    break
                try:
                    page.goto(r["url"], wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(1200)
                    accept_cookies(page)
                    detail = parse_detail(page.content())
                    r["specs"] = detail["specs"]
                    r["description_text"] = detail["description_text"]
                    if detail.get("price_huf_detail") is not None:
                        r["price_huf"] = detail["price_huf_detail"]
                    r["cpu"] = detail["specs"].get("Processzor")
                    r["ram"] = detail["specs"].get("Memória")
                    r["storage"] = detail["specs"].get("SSD")
                    r["gpu"] = detail["specs"].get("Videokártya")
                    r["detail_status"] = "public_details_read" if r["description_text"] else "no_description"
                except Exception as exc:  # noqa: BLE001
                    r["detail_status"] = f"error:{type(exc).__name__}"
                    print(f"   [WARN] detail {r['url']}: {exc}")
                time.sleep(0.5)

            final = []
            for r in records:
                p = r.get("price_huf")
                if p is not None and not (args.min_price <= p <= args.max_price):
                    continue
                if p is None:
                    # keep for scoring if in title range uncertain — still skip empty price outside
                    continue
                final.append(r)
                print(f"   [MATCH] {p} Ft - {r['title'][:70]}")
            result["records"] = final
            result["status"] = "ok" if final else "no_accessible_records"
            if not final:
                result["notes"].append(
                    "Az ársávban (alap 40–400 ezer) lehet kevés/új gép; a belépő új konfigok gyakran 400e felett vannak."
                )
        finally:
            browser.close()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    txt = out.with_suffix(".txt")
    blocks = []
    for i, r in enumerate(result["records"], 1):
        blocks.append(
            f"{i}: {r.get('title')} ({r.get('price_huf')} Ft)\n{r.get('url')}\n\n{r.get('description_text') or ''}"
        )
    txt.write_text("\n\n\n".join(blocks), encoding="utf-8")
    print(f"Kész! {len(result['records'])} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
