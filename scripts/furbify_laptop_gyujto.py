"""Furbify — felújított laptop / 2-in-1 / Surface gyűjtő (ingyenes, Playwright).

Kategóriák: /laptop, /2-in-1-laptop (és opcionális kereső URL).
Lista: .product-list-item + a[href*='/laptop-']; részletek: adatlap tábla.
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
    f"{BASE}/laptop",
    f"{BASE}/2-in-1-laptop",
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

    def add_from_anchor(a, item=None) -> None:
        href = a.get("href") or ""
        if "/laptop-" not in href and "surface" not in href.lower():
            return
        url = urljoin(BASE + "/", href).split("?")[0]
        if url in seen:
            return
        seen.add(url)
        title_el = None
        if item is not None:
            title_el = item.select_one(".product-list-name")
        title = (
            title_el.get_text(" ", strip=True)
            if title_el
            else a.get_text(" ", strip=True) or a.get("aria-label") or url
        )
        price_text = ""
        snippet = ""
        code = None
        if item is not None:
            price_el = item.select_one(".special-price, .solo-price, .product-list-price")
            price_text = price_el.get_text(" ", strip=True) if price_el else ""
            attrs = item.select_one(".product-list-attributes")
            snippet = attrs.get_text(" ", strip=True) if attrs else ""
            code = item.get("data-product-code")
        if not price_text:
            # popular-products blocks often put price near the card
            parent = a.parent
            for _ in range(4):
                if parent is None:
                    break
                price_text = parent.get_text(" ", strip=True)
                if "Ft" in price_text:
                    break
                parent = parent.parent
            price_text = price_text[:120] if price_text else ""
        out.append(
            {
                "id": code or url.rsplit("-", 1)[-1],
                "title": title.strip() or url,
                "url": url,
                "price_text": price_text,
                "price_huf": parse_price(price_text),
                "list_snippet": snippet,
                "description_text": "",
                "specs": {},
                "stock": None,
                "detail_status": "list_only",
            }
        )

    for item in soup.select(".product-list-item"):
        a = item.select_one("a[href*='/laptop-'], a[href*='laptop-']")
        if a:
            add_from_anchor(a, item)

    # fallback: any product link on the page (popular strip, etc.)
    for a in soup.select("a[href*='/laptop-']"):
        add_from_anchor(a, None)

    return out


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    specs = {}
    for tr in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) >= 2:
            specs[cells[0]] = " | ".join(cells[1:])
    stock = specs.get("Készlet")
    keys = [
        "Processzor",
        "Memória (RAM)",
        "Háttértár",
        "Videokártya",
        "Grafika",
        "Kijelző",
        "Touchscreen",
        "Operációs rendszer",
        "Esztétikai állapot",
        "Készlet",
        "Billentyűzet",
        "Állapot",
    ]
    lines = [f"{k}: {specs[k]}" for k in keys if specs.get(k)]
    # also keep unknown useful keys
    for k, v in specs.items():
        if k not in keys and any(
            x in k.lower() for x in ("kijelző", "display", "pen", "toll", "keyboard", "billenty")
        ):
            lines.append(f"{k}: {v}")
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
        before = page.locator(".product-list-item, a[href*='/laptop-']").count()
        try:
            btn.first.click(timeout=5000, force=True)
            page.wait_for_timeout(2200)
        except Exception as exc:  # noqa: BLE001
            print(f"   [WARN] load-more: {exc}")
            break
        after = page.locator(".product-list-item, a[href*='/laptop-']").count()
        if after <= before:
            break
    return parse_list_cards(page.content())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Furbify laptop / 2-in-1 gyűjtő")
    ap.add_argument("--min-price", type=int, default=100000)
    ap.add_argument("--max-price", type=int, default=350000)
    ap.add_argument("--details", type=int, default=50)
    ap.add_argument("--max-loads", type=int, default=10, help="„Következő termékek” kattintások")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--include-oos", action="store_true")
    ap.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Extra kategória/kereső URL (többször megadható). Alap: /laptop + /2-in-1-laptop",
    )
    ap.add_argument("--keyword", default="", help="Cím/snippet szűrő (pl. surface, 32gb, x360)")
    ap.add_argument("--output", default="furbify-laptop.json")
    ap.add_argument("--browser-executable")
    args = ap.parse_args(argv)

    categories = list(DEFAULT_CATEGORIES)
    if args.categories:
        categories.extend(args.categories)

    started = time.monotonic()
    deadline = started + args.timeout
    result = {
        "source": "furbify-laptop-public-local",
        "schema_version": 1,
        "mode": "laptop",
        "categories": categories,
        "search": {
            "min_price": args.min_price,
            "max_price": args.max_price,
            "details": args.details,
            "keyword": args.keyword,
        },
        "status": "partial",
        "records": [],
        "scraper_cost_usd": 0,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "notes": ["laptop-score branch collector"],
    }

    launch = {"headless": True}
    if args.browser_executable:
        launch["executable_path"] = args.browser_executable

    kw = (args.keyword or "").strip().lower()
    by_url: dict[str, dict] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch)
        page = browser.new_page(locale="hu-HU", user_agent=USER_AGENT)
        try:
            for cat in categories:
                if time.monotonic() >= deadline:
                    break
                print(f"-> Furbify laptop lista: {cat}")
                cards = load_all_list_pages(page, cat, args.max_loads)
                print(f"   kártyák: {len(cards)}")
                for c in cards:
                    by_url.setdefault(c["url"], c)

            records = list(by_url.values())
            filtered = []
            for r in records:
                p = r.get("price_huf")
                if p is not None and not (args.min_price <= p <= args.max_price):
                    continue
                blob = f"{r.get('title','')} {r.get('list_snippet','')}".lower()
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
                    page.wait_for_timeout(1000)
                    accept_cookies(page)
                    detail = parse_detail(page.content())
                    r["specs"] = detail["specs"]
                    r["stock"] = detail["stock"]
                    r["description_text"] = detail["description_text"]
                    if detail.get("price_huf_detail") is not None:
                        r["price_huf"] = detail["price_huf_detail"]
                    r["detail_status"] = (
                        "public_details_read" if r["description_text"] else "no_description"
                    )
                    r["cpu"] = detail["specs"].get("Processzor")
                    r["ram"] = detail["specs"].get("Memória (RAM)")
                    r["storage"] = detail["specs"].get("Háttértár")
                    r["gpu"] = detail["specs"].get("Videokártya") or detail["specs"].get("Grafika")
                    r["display"] = detail["specs"].get("Kijelző")
                    r["touch"] = detail["specs"].get("Touchscreen")
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
