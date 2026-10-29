"""Furbify — felújított asztali / gamer PC gyűjtő (ingyenes, Playwright).

Kategóriák: /szamitogep és /szamitogep/gaming-pc-k
Lista: .product-list-item; részletek: adatlap tábla.
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

BASE = "https://www.furbify.hu"
DEFAULT_CATEGORIES = [
    f"{BASE}/szamitogep/gaming-pc-k",
    f"{BASE}/szamitogep",
]
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def accept_cookies(page) -> None:
    selectors = [
        "#cookiescript_accept",
        "button#cookiescript_accept",
        "#cookiescript_injected button:has-text('Elfogad')",
        "button:has-text('Összes elfogadása')",
        "button:has-text('Elfogadom')",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=2000)
                page.wait_for_timeout(800)
                return
        except Exception:
            continue
    page.evaluate(
        """() => {
        const wrap = document.querySelector('#cookiescript_injected, #cookiescript_injected_wrapper');
        if (wrap) wrap.remove();
        }"""
    )


def parse_price(text: str | None) -> int | None:
    if not text:
        return None
    # prefer the first/current price token with Ft
    nums = re.findall(r"(\d[\d\s]*)\s*Ft", text.replace("\xa0", " "))
    if not nums:
        return None
    try:
        return int(re.sub(r"\s+", "", nums[0]))
    except ValueError:
        return None


def parse_list_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for item in soup.select(".product-list-item"):
        a = item.select_one("a[href*='szamitogep-']")
        if not a:
            continue
        url = urljoin(BASE + "/", a.get("href") or "")
        if url in seen:
            continue
        seen.add(url)
        title_el = item.select_one(".product-list-name")
        title = title_el.get_text(" ", strip=True) if title_el else a.get_text(" ", strip=True)
        price_el = item.select_one(".special-price, .solo-price, .product-list-price")
        price_text = price_el.get_text(" ", strip=True) if price_el else ""
        attrs = item.select_one(".product-list-attributes")
        snippet = attrs.get_text(" ", strip=True) if attrs else ""
        code = item.get("data-product-code")
        out.append(
            {
                "id": code or url.rsplit("-", 1)[-1],
                "title": title,
                "url": url.split("?")[0],
                "price_text": price_text,
                "price_huf": parse_price(price_text),
                "list_snippet": snippet,
                "description_text": "",
                "specs": {},
                "stock": None,
                "detail_status": "list_only",
            }
        )
    return out


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    specs = {}
    for tr in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) >= 2:
            specs[cells[0]] = " | ".join(cells[1:])
    stock = specs.get("Készlet")
    # build description from key fields
    keys = [
        "Processzor",
        "Memória (RAM)",
        "Háttértár",
        "Videokártya",
        "Operációs rendszer",
        "Gépház formátum",
        "Esztétikai állapot",
        "Készlet",
    ]
    lines = [f"{k}: {specs[k]}" for k in keys if specs.get(k)]
    price = None
    for sel in [".special-price", ".solo-price", ".price", ".product-price"]:
        el = soup.select_one(sel)
        if el:
            price = parse_price(el.get_text(" ", strip=True))
            if price:
                break
    return {
        "specs": specs,
        "stock": stock,
        "description_text": "\n".join(lines),
        "price_huf_detail": price,
    }


def load_all_list_pages(page, category_url: str, max_loads: int) -> list[dict]:
    page.goto(category_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)
    accept_cookies(page)
    page.wait_for_timeout(500)
    for _ in range(max_loads):
        btn = page.locator("#product-category-load-more-products")
        if not btn.count() or not btn.first.is_visible():
            break
        before = page.locator(".product-list-item").count()
        try:
            btn.first.click(timeout=5000, force=True)
            page.wait_for_timeout(2200)
        except Exception as exc:  # noqa: BLE001
            print(f"   [WARN] load-more: {exc}")
            break
        after = page.locator(".product-list-item").count()
        if after <= before:
            break
    return parse_list_cards(page.content())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Furbify PC gyűjtő")
    ap.add_argument("--min-price", type=int, default=40000)
    ap.add_argument("--max-price", type=int, default=400000)
    ap.add_argument("--details", type=int, default=40)
    ap.add_argument("--max-loads", type=int, default=8, help="„Következő 24 termék” kattintások")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--include-oos", action="store_true", help="Nincs készleten termékek is")
    ap.add_argument("--output", default="furbify-pc.json")
    ap.add_argument("--browser-executable")
    args = ap.parse_args(argv)

    started = time.monotonic()
    deadline = started + args.timeout
    result = {
        "source": "furbify-public-local",
        "schema_version": 1,
        "categories": DEFAULT_CATEGORIES,
        "search": {
            "min_price": args.min_price,
            "max_price": args.max_price,
            "details": args.details,
        },
        "status": "partial",
        "records": [],
        "scraper_cost_usd": 0,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "notes": [],
    }

    launch = {"headless": True}
    if args.browser_executable:
        launch["executable_path"] = args.browser_executable

    by_url: dict[str, dict] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch)
        page = browser.new_page(locale="hu-HU", user_agent=USER_AGENT)
        try:
            for cat in DEFAULT_CATEGORIES:
                if time.monotonic() >= deadline:
                    break
                print(f"-> Furbify lista: {cat}")
                cards = load_all_list_pages(page, cat, args.max_loads)
                print(f"   kártyák: {len(cards)}")
                for c in cards:
                    by_url.setdefault(c["url"], c)

            records = list(by_url.values())
            # price prefilter when known from list
            filtered = []
            for r in records:
                p = r.get("price_huf")
                if p is None or args.min_price <= p <= args.max_price:
                    filtered.append(r)
            records = filtered

            for r in records[: args.details]:
                if time.monotonic() >= deadline:
                    r["detail_status"] = "timeout"
                    break
                try:
                    page.goto(r["url"], wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(1000)
                    accept_cookies(page)
                    detail = parse_detail(page.content())
                    r["specs"] = detail["specs"]
                    r["stock"] = detail["stock"]
                    r["description_text"] = detail["description_text"]
                    if detail.get("price_huf_detail") is not None:
                        r["price_huf"] = detail["price_huf_detail"]
                    r["detail_status"] = "public_details_read" if r["description_text"] else "no_description"
                    # CPU/RAM/GPU convenience fields from specs
                    r["cpu"] = detail["specs"].get("Processzor")
                    r["ram"] = detail["specs"].get("Memória (RAM)")
                    r["storage"] = detail["specs"].get("Háttértár")
                    r["gpu"] = detail["specs"].get("Videokártya")
                except Exception as exc:  # noqa: BLE001
                    r["detail_status"] = f"error:{type(exc).__name__}"
                    print(f"   [WARN] detail {r['url']}: {exc}")
                time.sleep(0.5)

            final = []
            for r in records:
                stock = (r.get("stock") or "").lower()
                if not args.include_oos and stock.startswith("nincs készleten"):
                    continue
                p = r.get("price_huf")
                if p is not None and not (args.min_price <= p <= args.max_price):
                    continue
                final.append(r)
                print(f"   [MATCH] {p} Ft - {r['title'][:70]}")

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
