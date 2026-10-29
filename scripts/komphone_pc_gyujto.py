"""KomPhone.hu — új/felújított gamer PC gyűjtő (ingyenes, Playwright).

UNAS webshop. Alapkonfig a termékoldal Memória/SSD mezője (gyakran 16GB + 480GB),
a címbeli 16/32/64GB sáv NEM automatikus 32GB.

A kategória-lista alapból nem mindig adja az összes gépet — list_num + rendezés
+ kapcsolódó termékek BFS kell a teljesebb lefedéshez.
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
    f"{BASE}/felujitott-gamer-pc?list_num=100&order=price_asc",
    f"{BASE}/felujitott-gamer-pc?list_num=100&order=price_desc",
    f"{BASE}/felujitott-gamer-pc?list_num=100&order=name",
    f"{BASE}/belepo-gamer-konfigok-500-000-ft-alatt?list_num=100",
]
DEFAULT_SEEDS = [
    # Ismert, ársávba eső gép — a sima kategórialista gyakran kihagyja
    f"{BASE}/Gamer-szamitogep-GIGABYTE-B760M-i5-13600K-16GB-DDR",
]
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
PRODUCT_HREF_RE = re.compile(
    r"Gamer-szamitogep|gamer-szamitogep|epitett-komphone|Epitett-KomPhone|"
    r"argarancia-epitett|AZONNAL-KESZLETROL",
    re.I,
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
    nums = [
        int(re.sub(r"\s+", "", n))
        for n in re.findall(r"(\d[\d\s]*)\s*Ft", text.replace("\xa0", " "))
    ]
    nums = [n for n in nums if 10_000 <= n <= 5_000_000]
    if not nums:
        return None
    if len(nums) >= 2:
        return min(nums)
    return nums[0]


def canon_url(url: str) -> str:
    return urljoin(BASE + "/", url).split("?")[0].rstrip("/")


def is_product_url(url: str) -> bool:
    path = url.replace(BASE, "")
    if not PRODUCT_HREF_RE.search(path):
        return False
    # skip pure category pages
    if path.strip("/") in {
        "felujitott-gamer-pc",
        "belepo-gamer-konfigok-500-000-ft-alatt",
        "gamer-szamitogepek",
    }:
        return False
    return True


def parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()

    def add(title: str, url: str, price_text: str = "", sku=None) -> None:
        u = canon_url(url)
        if not is_product_url(u) or u in seen:
            return
        seen.add(u)
        out.append(
            {
                "id": sku,
                "title": title or u.rsplit("/", 1)[-1],
                "url": u,
                "price_text": price_text,
                "price_huf": parse_price(price_text),
                "description_text": "",
                "specs": {},
                "detail_status": "list_only",
            }
        )

    for item in soup.select(".js-product, div.product.list-1-card-1, .product"):
        a = item.select_one("a.product__name-link, .product__name a[href], a[href]")
        if not a:
            continue
        price_el = item.select_one(".product__price-base, .product__prices, .price")
        price_text = price_el.get_text(" ", strip=True) if price_el else ""
        add(
            a.get_text(" ", strip=True),
            a.get("href") or "",
            price_text,
            item.get("data-sku") or item.get("id"),
        )

    # fallback: any product-looking links (category pages sometimes omit card wrappers)
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        if not PRODUCT_HREF_RE.search(href):
            continue
        add(a.get_text(" ", strip=True), href)

    return out


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    # strip=True splits "Processzor:" -> "Processzor" + ":" on separate lines
    text = soup.get_text("\n", strip=True)
    specs: dict[str, str] = {}
    # Accept: "Label:\nValue" OR "Label\n:\nValue"
    labels = [
        "Processzor",
        "Alaplap",
        "Memória",
        "Videokártya",
        "SSD",
        "Tápegység",
        "Ház",
        "Hűtés",
        "Garancia",
        "Termék állapota",
    ]
    for key in labels:
        m = re.search(
            rf"{re.escape(key)}\s*:?\s*\n(?:\s*:\s*\n)?([^\n]+)",
            text,
        )
        if m:
            val = m.group(1).strip()
            if val and val != ":":
                specs[key] = val

    price = None
    m = re.search(r"Bruttó:\s*([\d\s]+)\s*Ft", text)
    if m:
        price = int(re.sub(r"\s+", "", m.group(1)))
    if price is None:
        m = re.search(r"Nettó:\s*([\d\s]+)\s*Ft\s*Bruttó:\s*([\d\s]+)\s*Ft", text)
        if m:
            price = int(re.sub(r"\s+", "", m.group(2)))
    if price is None:
        for sel in [".product-price", ".price", ".product__price-base", "[itemprop=price]"]:
            el = soup.select_one(sel)
            if el:
                price = parse_price(el.get_text(" ", strip=True))
                if price:
                    break
    if price is None:
        # title/h1 nearby amount as last resort
        h1 = soup.select_one("h1")
        if h1:
            price = parse_price(h1.find_parent().get_text(" ", strip=True) if h1.parent else "")

    title = ""
    h1 = soup.select_one("h1")
    if h1:
        title = h1.get_text(" ", strip=True)

    lines = [f"{k}: {v}" for k, v in specs.items()]
    # Only the product title — related cards on the same page also contain 16/32/64
    if re.search(r"16\s*/\s*32(?:\s*/\s*64)?", title or "", re.I):
        lines.append(
            "MEGJEGYZÉS: a címbeli 16/32/64GB sáv választható; az alapár a Memória mező szerinti kapacitás."
        )
    return {
        "title": title,
        "specs": specs,
        "description_text": "\n".join(lines),
        "price_huf_detail": price,
        "related_urls": [
            canon_url(a.get("href") or "")
            for a in soup.select("a[href]")
            if PRODUCT_HREF_RE.search(a.get("href") or "")
        ],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="KomPhone PC gyűjtő")
    ap.add_argument("--min-price", type=int, default=40000)
    ap.add_argument("--max-price", type=int, default=400000)
    ap.add_argument("--details", type=int, default=80)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--related-hops", type=int, default=2, help="Kapcsolódó termék BFS mélység")
    ap.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Extra kategória URL; alapból felújított + belépő gamer",
    )
    ap.add_argument(
        "--seed-url",
        action="append",
        dest="seed_urls",
        help="Közvetlen termék-URL (pl. ismert hiányzó gép)",
    )
    ap.add_argument("--output", default="komphone-pc.json")
    ap.add_argument("--browser-executable")
    args = ap.parse_args(argv)
    categories = args.categories or DEFAULT_CATEGORIES
    seeds = list(args.seed_urls or []) + list(DEFAULT_SEEDS)

    started = time.monotonic()
    deadline = started + args.timeout
    result = {
        "source": "komphone-public-local",
        "schema_version": 1,
        "categories": categories,
        "seed_urls": seeds,
        "search": {
            "min_price": args.min_price,
            "max_price": args.max_price,
            "details": args.details,
            "related_hops": args.related_hops,
        },
        "status": "partial",
        "records": [],
        "scraper_cost_usd": 0,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "Címbeli 16/32/64GB nem alapkonfig; a Memória/SSD mező a mérvadó.",
            "Lista: list_num=100 + több rendezés + kapcsolódó termék BFS.",
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
                page.wait_for_timeout(1600)
                accept_cookies(page)
                cards = parse_list(page.content())
                print(f"   kártyák/linkek: {len(cards)}")
                for c in cards:
                    by_url.setdefault(c["url"], c)

            for seed in seeds:
                u = canon_url(seed)
                by_url.setdefault(
                    u,
                    {
                        "id": None,
                        "title": u.rsplit("/", 1)[-1],
                        "url": u,
                        "price_text": "",
                        "price_huf": None,
                        "description_text": "",
                        "specs": {},
                        "detail_status": "seed",
                    },
                )
                print(f"-> seed: {u}")

            # detail pass + related BFS
            queue = list(by_url.keys())
            hop_of = {u: 0 for u in queue}
            fetched = 0
            i = 0
            while i < len(queue) and fetched < args.details and time.monotonic() < deadline:
                u = queue[i]
                i += 1
                r = by_url[u]
                try:
                    page.goto(u, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(1100)
                    accept_cookies(page)
                    detail = parse_detail(page.content())
                    if detail.get("title"):
                        r["title"] = detail["title"]
                    r["specs"] = detail["specs"]
                    r["description_text"] = detail["description_text"]
                    if detail.get("price_huf_detail") is not None:
                        r["price_huf"] = detail["price_huf_detail"]
                    r["cpu"] = detail["specs"].get("Processzor")
                    r["ram"] = detail["specs"].get("Memória")
                    r["storage"] = detail["specs"].get("SSD")
                    r["gpu"] = detail["specs"].get("Videokártya")
                    r["detail_status"] = (
                        "public_details_read" if r["description_text"] else "no_description"
                    )
                    fetched += 1
                    print(
                        f"   [DETAIL] {r.get('price_huf')} Ft | "
                        f"{(r.get('ram') or '?')[:20]} | {(r.get('gpu') or '?')[:24]} | {r['title'][:55]}"
                    )
                    if hop_of.get(u, 0) < args.related_hops:
                        for nu in detail.get("related_urls") or []:
                            nu = canon_url(nu)
                            if not is_product_url(nu):
                                continue
                            if nu not in by_url:
                                by_url[nu] = {
                                    "id": None,
                                    "title": nu.rsplit("/", 1)[-1],
                                    "url": nu,
                                    "price_text": "",
                                    "price_huf": None,
                                    "description_text": "",
                                    "specs": {},
                                    "detail_status": "related",
                                }
                                queue.append(nu)
                                hop_of[nu] = hop_of.get(u, 0) + 1
                except Exception as exc:  # noqa: BLE001
                    r["detail_status"] = f"error:{type(exc).__name__}"
                    print(f"   [WARN] detail {u}: {exc}")
                time.sleep(0.35)

            final = []
            for r in by_url.values():
                p = r.get("price_huf")
                if p is None:
                    continue
                if not (args.min_price <= p <= args.max_price):
                    continue
                final.append(r)
                print(f"   [MATCH] {p} Ft - {r['title'][:70]}")
            result["records"] = final
            result["discovered"] = len(by_url)
            result["details_fetched"] = fetched
            result["status"] = "ok" if final else "no_accessible_records"
            target = canon_url(DEFAULT_SEEDS[0])
            result["target_seed_present"] = any(canon_url(r["url"]) == target for r in final)
            if not result["target_seed_present"]:
                result["notes"].append(f"FIGYELEM: seed hiányzik a MATCH listából: {target}")
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
    print(
        f"Kész! {len(result['records'])} match / {result.get('discovered')} discovered "
        f"(seed_ok={result.get('target_seed_present')}) -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
