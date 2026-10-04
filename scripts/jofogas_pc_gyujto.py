"""
Jófogás - országos PC hirdetések gyűjtője (V2 - JSON-alapú)
====================================================

A korábbi verziók a látható HTML-kártyákat próbálták kiolvasni, ami törékeny
(a CSS-osztályok és szerkezet build-ről build-re változhatnak). Ez a verzió
ehelyett a Jófogás oldalába ágyazott __NEXT_DATA__ JSON blokkot olvassa ki,
ami MINDEN hirdetés adatát tartalmazza (cím, ár, url, ÉS a teljes leírás is)
már az első betöltéskor - nem is kell egyenként megnyitni a hirdetéseket.

TELEPÍTÉS:
    pip install playwright beautifulsoup4
    playwright install chromium

FUTTATÁS:
    python jofogas_pc_gyujto.py --keyword "pc 32gb" --location magyarorszag

Kimenet: pc 32gb.txt, az aktuális munkakönyvtárban, számozva.
Országos keresés, települési korlátozás nélkül.
    1: [cím] ([ár] Ft)
    [link]

    [leírás]


    2: ...
"""

import argparse
import re
import json
import time
import html as html_module
from urllib.parse import urljoin, urlparse, quote_plus

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# BEÁLLÍTÁSOK
# ---------------------------------------------------------------------------

SEARCH_KEYWORD = "pc 32gb"
MIN_PRICE = 40000
MAX_PRICE = 400000
MAX_PAGES = 10
DELAY_BETWEEN_PAGES = 2.0
OUTPUT_FILE = "pc 32gb.txt"
DEBUG_HTML_FILE = "debug_oldal.html"
HEADLESS = True



def is_jofogas_ad(ad_url, location="magyarorszag"):
    """Csak valódi Jófogás-linket fogad el, települési korlátozás nélkül."""
    parsed = urlparse(urljoin("https://www.jofogas.hu/", ad_url))
    return (
        parsed.hostname in {"www.jofogas.hu", "jofogas.hu"}
        and (location == "magyarorszag" or parsed.path.lower().startswith(f"/{location}/"))
    )


def accept_cookie_banner(page_obj):
    """Elfogadja a cookie-consent bannert, ha megjelenik. Nem kritikus, ha
    nem sikerül - a __NEXT_DATA__ JSON attól függetlenül ott van a HTML-ben."""
    possible_texts = [
        "Elfogadás és bezárás",
        "Összes elfogadása",
        "Elfogadom",
        "Elfogadás",
        "Accept all",
    ]
    contexts = [page_obj]
    try:
        contexts += list(page_obj.frames)
    except Exception:
        pass

    for ctx in contexts:
        for text in possible_texts:
            try:
                btn = ctx.get_by_role("button", name=text, exact=False).first
                if not btn.is_visible(timeout=800):
                    btn = ctx.get_by_text(text, exact=False).first
                if btn.is_visible(timeout=800):
                    btn.click(timeout=1500, force=True)
                    print(f"   [INFO] Cookie-banner gombra kattintva ('{text}').")
                    page_obj.wait_for_timeout(1000)
                    return True
            except Exception:
                continue
    return False


def safe_goto(page_obj, url, timeout=30000):
    try:
        page_obj.goto(url, wait_until="domcontentloaded", timeout=timeout)
    except Exception as e:
        print(f"   [WARN] Betöltési hiba ({e}), folytatom mindenesetre.")
    page_obj.wait_for_timeout(1500)


def clean_body_html(raw_body: str) -> str:
    """A hirdetés leírása a JSON-ban HTML-entitásokkal és <br> tagekkel van
    (pl. 'Ryzen 7\\u003cbr\\u003e...'). Ezt alakítjuk olvasható sima szöveggé."""
    if not raw_body:
        return ""
    text = html_module.unescape(raw_body)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)  # bármilyen más maradék tag eltávolítása
    text = re.sub(r"\n{3,}", "\n\n", text)  # túl sok üres sor összevonása
    return text.strip()


def extract_next_data(html: str):
    """Kigyűjti és JSON-ná alakítja a __NEXT_DATA__ script tartalmát."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError:
        return None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Jófogás PC-gyűjtő, választható keresési szűrőkkel.")
    parser.add_argument("--keyword", default=SEARCH_KEYWORD, help="Keresőkifejezés, például: pc 64gb")
    parser.add_argument("--min-price", type=int, default=MIN_PRICE, help="Minimum ár Ft-ban")
    parser.add_argument("--max-price", type=int, default=MAX_PRICE, help="Maximum ár Ft-ban")
    parser.add_argument("--location", default="magyarorszag", help="Jófogás hely-útvonal, pl. magyarorszag, budapest vagy pest")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES)
    parser.add_argument("--output", default=OUTPUT_FILE, help="Kimeneti szövegfájl")
    args = parser.parse_args(argv)
    args.location = args.location.strip().lower().strip("/")
    if not re.fullmatch(r"[a-z0-9_-]+", args.location):
        parser.error("A hely egy Jófogás URL-útvonal legyen, nem teljes URL vagy szabad szöveg.")
    if not args.keyword.strip():
        parser.error("A kulcsszó nem lehet üres.")
    if args.min_price < 0 or args.max_price < args.min_price:
        parser.error("Az ársáv érvénytelen.")
    if args.max_pages < 1:
        parser.error("Legalább egy oldalt meg kell adni.")
    return args


def main():
    args = parse_args()
    matches = []  # dicts: title, price, url, description

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page_obj = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="hu-HU",
        )

        print(f"Keresés: {args.location}, '{args.keyword}', ár: {args.min_price}-{args.max_price} Ft")

        for page_num in range(1, args.max_pages + 1):
            url = f"https://www.jofogas.hu/{args.location}?q={quote_plus(args.keyword)}&o={page_num}"
            print(f"-> {page_num}. találati oldal: {url}")

            safe_goto(page_obj, url)
            if page_num == 1:
                accept_cookie_banner(page_obj)

            html = page_obj.content()
            data = extract_next_data(html)

            if not data:
                print("   [WARN] Nem található __NEXT_DATA__ JSON ezen az oldalon.")
                with open(DEBUG_HTML_FILE, "w", encoding="utf-8") as dbg:
                    dbg.write(html)
                print(f"   [DEBUG] Nyers HTML elmentve: {DEBUG_HTML_FILE}")
                break

            try:
                ads = data["props"]["pageProps"]["adList"]["ads"]
            except (KeyError, TypeError):
                print("   Nincs több hirdetés ezen az oldalon (adList üres), megállok.")
                break

            if not ads:
                print("   Üres hirdetéslista, megállok a lapozással.")
                break

            for ad in ads:
                title = ad.get("subject", "")
                price_info = ad.get("price") or {}
                price = price_info.get("value")
                ad_url = ad.get("url", "")
                body = ad.get("body", "")

                if not is_jofogas_ad(ad_url, args.location):
                    print(f"   [SKIP] Nem megfelelő helyű vagy nem Jófogás-hirdetés: {title}")
                    continue

                if price is not None and args.min_price <= price <= args.max_price:
                    matches.append(
                        {
                            "title": title,
                            "price": price,
                            "url": urljoin("https://www.jofogas.hu/", ad_url),
                            "description": clean_body_html(body),
                        }
                    )
                    print(f"   [MATCH] {price} Ft - {title}")

            # lapozás vége ellenőrzése a pager infóból
            try:
                pager = data["props"]["pageProps"]["adList"]["pager"]
                if page_num >= pager.get("last_page", page_num):
                    print("   Elértük az utolsó oldalt.")
                    break
            except (KeyError, TypeError):
                pass

            time.sleep(DELAY_BETWEEN_PAGES)

        browser.close()

    if not matches:
        print("\nNem találtam egyetlen hirdetést sem a megadott ártartományban.")
        return

    output_blocks = []
    for i, item in enumerate(matches, start=1):
        block = (
            f"{i}: {item['title']} ({item['price']} Ft)\n"
            f"{item['url']}\n\n"
            f"{item['description']}"
        )
        output_blocks.append(block)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n\n\n".join(output_blocks))

    print(f"\nKész! {len(matches)} hirdetés elmentve ide: {args.output}")


if __name__ == "__main__":
    main()
