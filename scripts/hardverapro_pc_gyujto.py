"""HardverApró — komplett asztali PC hirdetések ingyenes gyűjtője.

Playwright + BeautifulSoup, API-kulcs/proxy nélkül.
Kategória: PC, szerver / Asztali gép / Komplett asztali PC.
A kereső űrlapot tölti ki (a puszta GET gyakran indexre irányít),
majd a találati kártyákat és opcionálisan a hirdetésoldal leírását olvassa.

Futtatás:
    python -X utf8 hardverapro_pc_gyujto.py --keyword "32gb" --location budapest
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

CATEGORY_PATH = "/aprok/pc_szerver/asztali_gep/komplett_asztali_pc"
BASE_ORIGIN = "https://hardverapro.hu"
SEARCH_PATH = f"{CATEGORY_PATH}/keres.php"
PAGE_SIZE = 100
DELAY_BETWEEN_PAGES = 1.5
DELAY_BETWEEN_DETAILS = 0.8
HEADLESS = True

# HardverApró megye-azonosítók: /muvelet/telepules/listaz.php?mode=county
COUNTY_IDS = {
    "budapest": (0, "Budapest"),
    "pest": (13, "Pest"),
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def parse_price_huf(text: str | None) -> int | None:
    if not text:
        return None
    raw = text.strip()
    if re.search(r"keresem|csere", raw, re.I):
        return None
    # 1,96M Ft / 2M Ft
    m = re.search(r"([\d]+(?:[.,]\d+)?)\s*[Mm]\b", raw)
    if m:
        try:
            return int(float(m.group(1).replace(",", ".")) * 1_000_000)
        except ValueError:
            return None
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return None
    try:
        value = int(digits)
    except ValueError:
        return None
    return value if value > 0 else None


def normalize_ad_url(href: str | None) -> str | None:
    if not href:
        return None
    url = urljoin(BASE_ORIGIN + "/", href)
    parsed = urlparse(url)
    if parsed.hostname not in {"hardverapro.hu", "www.hardverapro.hu"}:
        return None
    if "/apro/" not in parsed.path:
        return None
    # kanonikus friss.html nélkül is elfogadható; a kártyák friss.html-t adnak
    return urlunparse(("https", "hardverapro.hu", parsed.path, "", "", ""))


def ad_id_from_url(url: str) -> str | None:
    m = re.search(r"/apro/([^/]+)/", url)
    return m.group(1) if m else None


def accept_cookie_banner(page) -> None:
    page.evaluate(
        """() => {
        const texts = /ELFOGADOM|Elfogadom|Accept all|Accept All|Összes elfogad|Agree/i;
        const buttons = [...document.querySelectorAll('button, [role=button]')];
        const hit = buttons.find((b) => texts.test((b.innerText || '').trim()));
        if (hit) hit.click();
        }"""
    )
    page.wait_for_timeout(700)


def safe_goto(page, url: str, timeout: int = 45000) -> None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    except Exception as exc:  # noqa: BLE001 — gyűjtő: folytatunk részleges oldallal
        print(f"   [WARN] Betöltési hiba ({exc}), folytatom.")
    page.wait_for_timeout(1200)


def build_search_url(keyword: str, min_price: int, max_price: int, location: str, offset: int = 0) -> str:
    params: dict[str, str | int] = {
        "stext": keyword,
        "minprice": min_price,
        "maxprice": max_price,
        "noiced": 1,
    }
    county = COUNTY_IDS.get(location)
    if county is not None:
        params["stcid"] = county[0]
    else:
        # Üres stcid tartja a keresőt keres.php-n; stcid nélküli GET gyakran indexre esik.
        params["stcid"] = ""
    if offset:
        params["offset"] = offset
    return f"{BASE_ORIGIN}{SEARCH_PATH}?{urlencode(params)}"


def _on_search_results(page) -> bool:
    if "keres.php" not in page.url:
        return False
    try:
        html = page.content()
    except Exception:  # noqa: BLE001
        return False
    return bool(re.search(r"\d[\d\s]*\s+találat", html, re.I))


def submit_search(page, keyword: str, min_price: int, max_price: int, location: str) -> None:
    """Cookie után GET, ha kell űrlap. Index.html nem elfogadható szűrt találat."""
    land = f"{BASE_ORIGIN}{CATEGORY_PATH}/index.html"
    safe_goto(page, land)
    accept_cookie_banner(page)

    county = COUNTY_IDS.get(location)
    stcid = "" if county is None else str(county[0])
    stcid_text = "" if county is None else county[1]

    # 1) Közvetlen GET (Pest/országos és sokszor Budapest is stabil süti után)
    direct = build_search_url(keyword, min_price, max_price, location)
    print(f"   [INFO] Kereső GET: {direct}")
    safe_goto(page, direct)
    accept_cookie_banner(page)
    if _on_search_results(page):
        return

    # 2) Űrlap + navigációvárás (Budapest stcid=0 GET néha indexre esik)
    print("   [INFO] GET nem adott keresőtalálatot; űrlapos próbálkozás.")
    safe_goto(page, land)
    accept_cookie_banner(page)
    try:
        with page.expect_navigation(timeout=45000, wait_until="domcontentloaded"):
            page.evaluate(
                """({ keyword, minPrice, maxPrice, stcid, stcidText }) => {
                const form = document.querySelector('form[action*="keres.php"]');
                if (!form) throw new Error('kereső űrlap nem található');
                const set = (name, value) => {
                  const el = form.querySelector(`[name="${name}"]`);
                  if (el) el.value = value;
                };
                set('stext', keyword);
                set('minprice', String(minPrice));
                set('maxprice', String(maxPrice));
                set('stcid', stcid);
                set('stcid_text', stcidText);
                set('stmid', '');
                set('stmid_text', '');
                form.querySelectorAll('input[name="__buying"]').forEach((el) => {
                  if (el.value === '1') el.checked = false;
                  if (el.value === '0') el.checked = true;
                });
                const noiced = form.querySelector('input[name="noiced"]');
                if (noiced) noiced.checked = true;
                form.submit();
                }""",
                {
                    "keyword": keyword,
                    "minPrice": min_price,
                    "maxPrice": max_price,
                    "stcid": stcid,
                    "stcidText": stcid_text,
                },
            )
    except Exception as exc:  # noqa: BLE001
        print(f"   [WARN] Űrlap-navigáció: {exc}")

    page.wait_for_timeout(1500)
    if not _on_search_results(page):
        print(f"   [ERROR] Nincs érvényes keresőoldal ({page.url}).")


def parse_result_count(soup: BeautifulSoup) -> int | None:
    for text in soup.stripped_strings:
        m = re.search(r"([\d\s]+)\s+találat", text, re.I)
        if m:
            try:
                return int(re.sub(r"\s+", "", m.group(1)))
            except ValueError:
                return None
    return None


def parse_listing_cards(html: str) -> tuple[list[dict], BeautifulSoup]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for li in soup.select("li.media[data-uadid], li.media"):
        title_a = li.select_one("h1 a[href*='/apro/'], .uad-col-title a[href*='/apro/']")
        if not title_a:
            continue
        title = title_a.get_text(" ", strip=True)
        if not title or title.lower() == "előresorolva":
            continue
        url = normalize_ad_url(title_a.get("href"))
        if not url or url in seen:
            continue
        seen.add(url)
        price_el = li.select_one(".uad-col-price .uad-price, .uad-price")
        price_text = price_el.get_text(" ", strip=True) if price_el else ""
        city_el = li.select_one(".uad-cities")
        city = city_el.get_text(" ", strip=True) if city_el else ""
        uadid = li.get("data-uadid") or ad_id_from_url(url)
        records.append(
            {
                "id": str(uadid) if uadid else ad_id_from_url(url),
                "title": title,
                "url": url,
                "price_text": price_text,
                "price_huf": parse_price_huf(price_text),
                "city": city or None,
                "description_text": "",
                "detail_status": "list_only",
            }
        )
    return records, soup


def enrich_with_details(page, records: list[dict], details: int, deadline: float) -> None:
    for record in records[:details]:
        if time.monotonic() >= deadline:
            record["detail_status"] = "timeout"
            break
        url = record["url"]
        try:
            safe_goto(page, url, timeout=30000)
            soup = BeautifulSoup(page.content(), "html.parser")
            content = soup.select_one(".uad-content")
            text = content.get_text("\n", strip=True) if content else ""
            if text:
                record["description_text"] = text
                record["detail_status"] = "public_details_read"
            else:
                record["detail_status"] = "no_description"
            details_box = soup.select_one(".uad-details")
            if details_box and record.get("price_huf") is None:
                price_guess = parse_price_huf(details_box.get_text(" ", strip=True))
                if price_guess is not None:
                    record["price_huf"] = price_guess
                    record["price_text"] = record.get("price_text") or f"{price_guess} Ft"
                    record["price_source"] = "detail"
            time.sleep(DELAY_BETWEEN_DETAILS)
        except Exception as exc:  # noqa: BLE001
            record["detail_status"] = f"error:{type(exc).__name__}"
            print(f"   [WARN] Részlet hiba: {url} ({exc})")


def next_page_url(current_url: str, soup: BeautifulSoup, page_index: int) -> str | None:
    nxt = soup.select_one("a[rel='next']")
    if nxt and nxt.get("href"):
        href = urljoin(BASE_ORIGIN + "/", nxt["href"])
        if "keres.php" in href:
            return href
        # Ha a next az indexre mutat, építsünk kereső URL-t offsettel.
    parsed = urlparse(current_url)
    if "keres.php" not in parsed.path:
        return None
    qs = parse_qs(parsed.query)
    qs["offset"] = [str(page_index * PAGE_SIZE)]
    flat = {k: v[-1] for k, v in qs.items()}
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(flat), ""))


def write_txt(path: Path, records: list[dict]) -> None:
    blocks = []
    for i, item in enumerate(records, start=1):
        price = item.get("price_huf")
        price_bit = f"({price} Ft)" if price is not None else f"({item.get('price_text') or 'ár ismeretlen'})"
        city = item.get("city") or ""
        loc_bit = f"\n{city}" if city else ""
        blocks.append(
            f"{i}: {item.get('title', '')} {price_bit}\n"
            f"{item.get('url', '')}{loc_bit}\n\n"
            f"{item.get('description_text') or ''}".rstrip()
        )
    path.write_text("\n\n\n".join(blocks), encoding="utf-8")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="HardverApró komplett asztali PC gyűjtő.")
    parser.add_argument("--keyword", default="32gb", help="Keresőkifejezés (stext)")
    parser.add_argument("--min-price", type=int, default=40000)
    parser.add_argument("--max-price", type=int, default=400000)
    parser.add_argument(
        "--location",
        default="budapest",
        help="budapest | pest | magyarorszag (országos, megyeszűrő nélkül)",
    )
    parser.add_argument("--max-pages", type=int, default=5, help="Találati oldalak max. száma")
    parser.add_argument("--details", type=int, default=40, help="Hány hirdetésoldalt nyisson meg leírásért")
    parser.add_argument("--timeout", type=int, default=180, help="Teljes futás másodpercben")
    parser.add_argument("--output", default="hardverapro-pc.json")
    parser.add_argument("--browser-executable")
    args = parser.parse_args(argv)
    args.location = args.location.strip().lower()
    if args.location not in {"budapest", "pest", "magyarorszag"}:
        parser.error("location: budapest, pest vagy magyarorszag")
    if not args.keyword.strip():
        parser.error("A kulcsszó nem lehet üres.")
    if args.min_price < 0 or args.max_price < args.min_price:
        parser.error("Az ársáv érvénytelen.")
    if args.max_pages < 1 or args.details < 0 or args.timeout < 1:
        parser.error("Pozitív korlát szükséges.")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    started = time.monotonic()
    deadline = started + args.timeout
    output = Path(args.output)
    launch_kwargs = {"headless": HEADLESS}
    if args.browser_executable:
        launch_kwargs["executable_path"] = args.browser_executable

    result = {
        "source": "hardverapro-public-local",
        "schema_version": 1,
        "category": "komplett_asztali_pc",
        "search": {
            "keyword": args.keyword,
            "min_price": args.min_price,
            "max_price": args.max_price,
            "location": args.location,
            "max_pages": args.max_pages,
            "details": args.details,
        },
        "status": "partial",
        "result_count_reported": None,
        "records": [],
        "scraper_cost_usd": 0,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "notes": [],
    }

    print(
        f"HardverApró keresés: {args.location}, '{args.keyword}', "
        f"ár: {args.min_price}-{args.max_price} Ft"
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_kwargs)
        page = browser.new_page(locale="hu-HU", user_agent=USER_AGENT)
        page.set_default_timeout(10000)
        try:
            submit_search(page, args.keyword.strip(), args.min_price, args.max_price, args.location)
            if "keres.php" not in page.url and "stext=" not in page.url:
                result["notes"].append(f"A keresés nem maradt a kereső URL-en: {page.url}")
                print(f"   [WARN] Váratlan URL: {page.url}")

            by_url: dict[str, dict] = {}
            for page_num in range(1, args.max_pages + 1):
                if time.monotonic() >= deadline:
                    result["notes"].append("Időkorlát a lapozás közben.")
                    break
                html = page.content()
                cards, soup = parse_listing_cards(html)
                if page_num == 1:
                    result["result_count_reported"] = parse_result_count(soup)
                    result["search_url"] = page.url
                    print(f"   Jelentett találat: {result['result_count_reported']}")

                if page_num == 1 and "keres.php" not in page.url:
                    result["notes"].append("Nem keresőoldalon vagyunk; a kategória-indexet ne kezeld szűrt találatként.")
                    print("   [ERROR] A keresés indexre esett — nincs megbízható szűrt lista.")
                    by_url.clear()
                    break

                new_on_page = 0
                for card in cards:
                    title_l = (card.get("title") or "").lower()
                    if re.search(r"felvásárl|beszámítást keres|pc-t keresek|számítógépet keres", title_l):
                        continue
                    price = card.get("price_huf")
                    if price is None:
                        continue
                    if not (args.min_price <= price <= args.max_price):
                        continue
                    if card["url"] not in by_url:
                        by_url[card["url"]] = card
                        new_on_page += 1
                        print(f"   [MATCH] {price} Ft - {card['title'][:70]}")
                print(f"-> {page_num}. oldal: +{new_on_page}, összesen {len(by_url)}")

                if not cards or new_on_page == 0:
                    break
                reported = result["result_count_reported"]
                if reported is not None and (
                    len(by_url) >= reported or reported <= page_num * PAGE_SIZE
                ):
                    break
                if page_num >= args.max_pages:
                    break

                nxt = next_page_url(page.url, soup, page_num)
                if not nxt or "keres.php" not in nxt:
                    # Űrlapos keresés után építsünk offsetes kereső URL-t.
                    nxt = build_search_url(
                        args.keyword.strip(),
                        args.min_price,
                        args.max_price,
                        args.location,
                        offset=page_num * PAGE_SIZE,
                    )
                time.sleep(DELAY_BETWEEN_PAGES)
                safe_goto(page, nxt)
                if "keres.php" not in page.url:
                    result["notes"].append(f"Lapozás indexre esett ({page.url}).")
                    break

            records = list(by_url.values())
            result["records"] = records
            if records:
                enrich_with_details(page, records, args.details, deadline)
                result["status"] = "ok" if any(r.get("description_text") for r in records) else "partial"
            else:
                result["status"] = "no_accessible_records"
                debug_path = output.with_suffix(".debug.html")
                debug_path.write_text(page.content(), encoding="utf-8")
                result["notes"].append(f"Üres lista; debug HTML: {debug_path}")
                print(f"   [DEBUG] {debug_path}")
        finally:
            browser.close()

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".txt":
        write_txt(output, result["records"])
        meta_path = output.with_suffix(".meta.json")
        meta_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Kész! {len(result['records'])} hirdetés -> {output} (+ {meta_path.name})")
    else:
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        # szöveges másolat könnyű olvasáshoz
        txt_side = output.with_suffix(".txt")
        write_txt(txt_side, result["records"])
        print(f"Kész! {len(result['records'])} hirdetés -> {output} (+ {txt_side.name})")

    return 0 if result["records"] or result["status"] == "no_accessible_records" else 1


if __name__ == "__main__":
    raise SystemExit(main())
