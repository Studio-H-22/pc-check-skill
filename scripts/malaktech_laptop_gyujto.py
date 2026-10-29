"""MalakTech (malaktech.hu) — felújított laptop / 2-in-1 gyűjtő (ingyenes).

WooCommerce /shop lista + /product/ részletek. Playwright + BeautifulSoup.
Alap: készleten lévő gépek (mt_filter + keszlet + erkezo).
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE = "https://malaktech.hu"
DEFAULT_SHOP = f"{BASE}/shop/?mt_filter=1&keszlet=1&erkezo=1"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def accept_cookies(page) -> None:
    selectors = [
        "button:has-text('Elfogad')",
        "button:has-text('Összes elfogadása')",
        "button:has-text('Elfogadom')",
        "#cookie-notice .button",
        ".cookie-consent button",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=2000)
                page.wait_for_timeout(500)
                return
        except Exception:
            continue


def parse_price(text: str | None) -> int | None:
    if not text:
        return None
    # prefer last substantial Ft amount (sale price often last)
    nums = re.findall(r"(\d[\d\s\u00a0]*)\s*Ft", text.replace("\xa0", " "))
    if not nums:
        nums = re.findall(r"(\d[\d\s]*)", text.replace("\xa0", " "))
    if not nums:
        return None
    vals = []
    for n in nums:
        try:
            vals.append(int(re.sub(r"\s+", "", n)))
        except ValueError:
            continue
    vals = [v for v in vals if v >= 1000]
    return vals[-1] if vals else None


def parse_ram_gb(text: str) -> int | None:
    m = re.search(r"(\d+)\s*GB", text, re.I)
    return int(m.group(1)) if m else None


def parse_list_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for item in soup.select(".product.type-product, .product-small.product, li.product"):
        classes = " ".join(item.get("class") or [])
        if "outofstock" in classes:
            continue
        # skip non-laptop accessories if tagged
        if "product_cat-kutyuk" in classes or "product_cat-telefon" in classes:
            continue
        a = item.select_one('a[href*="/product/"]')
        if not a:
            continue
        url = urljoin(BASE + "/", a.get("href") or "").split("?")[0]
        if url in seen:
            continue
        seen.add(url)
        title_el = item.select_one(".product-title, .woocommerce-loop-product__title, h3, h2")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title:
            img = item.select_one("img[alt]")
            title = (img.get("alt") or "").strip() if img else url.rsplit("/", 2)[-2]
        # price: prefer box price, ignore mini-cart 0 Ft by scoping to item
        price_el = item.select_one(".price .woocommerce-Price-amount, .price bdi, .price")
        price_text = price_el.get_text(" ", strip=True) if price_el else ""
        price = parse_price(price_text)
        snippet = item.get_text(" ", strip=True)[:400]
        out.append(
            {
                "id": url.rstrip("/").rsplit("/", 1)[-1],
                "title": title,
                "url": url,
                "price_text": price_text,
                "price_huf": price,
                "list_snippet": snippet,
                "description_text": "",
                "specs": {},
                "stock": "instock" if "instock" in classes else None,
                "detail_status": "list_only",
                "classes": classes,
            }
        )
    return out


def parse_attributes_table(soup: BeautifulSoup) -> dict:
    specs = {}
    for table in soup.select(
        "table.woocommerce-product-attributes, table.shop_attributes, table"
    ):
        for tr in table.select("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if len(cells) >= 2:
                key, val = cells[0], " | ".join(cells[1:])
                if key and val and key not in specs:
                    specs[key] = val
    return specs


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    specs = parse_attributes_table(soup)
    desc = ""
    for sel in [
        "#tab-description",
        ".woocommerce-Tabs-panel--description",
        ".woocommerce-product-details__short-description",
    ]:
        el = soup.select_one(sel)
        if el:
            desc = el.get_text("\n", strip=True)
            break
    # enrich specs from description labels if missing
    for label, key in [
        (r"Processzor:\s*(.+)", "Processzor"),
        (r"Videokártya:\s*(.+)", "Videokártya"),
        (r"Kijelző:\s*(.+)", "Kijelző"),
        (r"Memória:\s*(.+)", "Memória (RAM)"),
        (r"Tárhely:\s*(.+)", "Háttértár"),
    ]:
        if key not in specs:
            m = re.search(label, desc)
            if m:
                specs[key] = m.group(1).split("\n")[0].strip()
    # attribute aliases
    if "RAM" in specs and "Memória (RAM)" not in specs:
        specs["Memória (RAM)"] = specs["RAM"]
    if "Tárhely" in specs and "Háttértár" not in specs:
        specs["Háttértár"] = specs["Tárhely"]
    if "Processzor" in specs and "Processzor" not in specs:
        pass

    price = None
    for sel in [".summary p.price", "p.price", ".summary .woocommerce-Price-amount"]:
        el = soup.select_one(sel)
        if el:
            price = parse_price(el.get_text(" ", strip=True))
            if price and price > 1000:
                break

    keys = [
        "Processzor",
        "Memória (RAM)",
        "RAM",
        "Háttértár",
        "Tárhely",
        "Videokártya",
        "Kijelző",
        "Kijelzőméret",
        "Állapot",
        "Márka",
        "Extrák",
        "Kategória",
    ]
    lines = [f"{k}: {specs[k]}" for k in keys if specs.get(k)]
    if desc:
        lines.append("")
        lines.append(desc[:2500])

    h1 = soup.select_one("h1.product_title, h1")
    title = h1.get_text(strip=True) if h1 else None

    return {
        "specs": specs,
        "stock": None,
        "description_text": "\n".join(lines),
        "price_huf_detail": price,
        "title_detail": title,
    }


def shop_url(min_price: int | None, max_price: int | None, page: int, extra: str) -> str:
    base = DEFAULT_SHOP
    if extra:
        base = extra if extra.startswith("http") else urljoin(BASE + "/", extra)
    # append page + price if not already in query
    parts = []
    if "min_price=" not in base and min_price:
        parts.append(("min_price", str(min_price)))
    if "max_price=" not in base and max_price:
        parts.append(("max_price", str(max_price)))
    if page > 1:
        parts.append(("paged", str(page)))
    if not parts:
        return base
    sep = "&" if "?" in base else "?"
    return base + sep + urlencode(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MalakTech laptop gyűjtő")
    ap.add_argument("--min-price", type=int, default=100000)
    ap.add_argument("--max-price", type=int, default=350000)
    ap.add_argument("--details", type=int, default=40)
    ap.add_argument("--max-pages", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--keyword", default="", help="Cím/snippet szűrő")
    ap.add_argument(
        "--shop-url",
        default=DEFAULT_SHOP,
        help="Lista URL (alap: készletes shop)",
    )
    ap.add_argument("--include-oos", action="store_true")
    ap.add_argument("--output", default="malaktech-laptop.json")
    ap.add_argument("--browser-executable")
    args = ap.parse_args(argv)

    started = time.monotonic()
    deadline = started + args.timeout
    kw = (args.keyword or "").strip().lower()
    result = {
        "source": "malaktech-laptop-public-local",
        "schema_version": 1,
        "mode": "laptop",
        "shop_url": args.shop_url,
        "search": {
            "min_price": args.min_price,
            "max_price": args.max_price,
            "details": args.details,
            "keyword": args.keyword,
            "max_pages": args.max_pages,
        },
        "status": "partial",
        "records": [],
        "scraper_cost_usd": 0,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "notes": ["laptop-score branch — malaktech.hu"],
    }

    launch = {"headless": True}
    if args.browser_executable:
        launch["executable_path"] = args.browser_executable

    by_url: dict[str, dict] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch)
        page = browser.new_page(locale="hu-HU", user_agent=USER_AGENT)
        try:
            for pnum in range(1, args.max_pages + 1):
                if time.monotonic() >= deadline:
                    break
                url = shop_url(args.min_price, args.max_price, pnum, args.shop_url)
                print(f"-> MalakTech lista p{pnum}: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1200)
                accept_cookies(page)
                cards = parse_list_cards(page.content())
                print(f"   kártyák: {len(cards)}")
                if not cards:
                    break
                new = 0
                for c in cards:
                    if c["url"] not in by_url:
                        by_url[c["url"]] = c
                        new += 1
                if new == 0:
                    break

            records = list(by_url.values())
            filtered = []
            for r in records:
                p = r.get("price_huf")
                if p is not None and not (args.min_price <= p <= args.max_price):
                    continue
                blob = f"{r.get('title','')} {r.get('list_snippet','')}".lower()
                if "mac studio" in blob or "imac" in blob:
                    continue
                if kw and kw not in blob and kw not in (r.get("url") or "").lower():
                    continue
                filtered.append(r)
            records = filtered

            for r in records[: args.details]:
                if time.monotonic() >= deadline:
                    r["detail_status"] = "timeout"
                    break
                try:
                    page.goto(r["url"], wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(900)
                    accept_cookies(page)
                    detail = parse_detail(page.content())
                    r["specs"] = detail["specs"]
                    r["description_text"] = detail["description_text"]
                    if detail.get("price_huf_detail"):
                        r["price_huf"] = detail["price_huf_detail"]
                    if detail.get("title_detail"):
                        r["title"] = detail["title_detail"]
                    r["detail_status"] = (
                        "public_details_read" if r["description_text"] else "no_description"
                    )
                    r["cpu"] = detail["specs"].get("Processzor")
                    r["ram"] = detail["specs"].get("Memória (RAM)") or detail["specs"].get("RAM")
                    r["storage"] = detail["specs"].get("Háttértár") or detail["specs"].get(
                        "Tárhely"
                    )
                    r["gpu"] = detail["specs"].get("Videokártya")
                    r["display"] = detail["specs"].get("Kijelző") or detail["specs"].get(
                        "Kijelzőméret"
                    )
                    r["condition"] = detail["specs"].get("Állapot")
                except Exception as exc:  # noqa: BLE001
                    r["detail_status"] = f"error:{type(exc).__name__}"
                    print(f"   [WARN] detail {r['url']}: {exc}")
                time.sleep(0.4)

            final = []
            for r in records:
                p = r.get("price_huf")
                if p is not None and not (args.min_price <= p <= args.max_price):
                    continue
                final.append(r)
                print(f"   [MATCH] {p} Ft - {(r.get('title') or '')[:70]}")

            result["records"] = final
            result["status"] = "ok" if final else "no_accessible_records"
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
