# PC check

Jófogás PC-gyűjtő és audio-központú /1000 értékelő Codexhez.

## Másik gépen

Jelentkezz be GitHubra a Studio-H-22 fiókkal (a tárhely privát), majd másold ezt a Codexbe:

> Telepítsd a PC check skillt ebből a GitHub-tárhelyből: https://github.com/Studio-H-22/pc-check-skill . A skill a tárhely gyökerében van. Tedd elérhetővé minden projektemben, állítsd be a szükséges Python-, Playwright- és BeautifulSoup-környezetet, és a „pc check” kérésre futtasd a friss gyűjtést, majd az értékelést. A megadott kulcsszó-, ár- és helyszűrőket alkalmazd; helyszűrő nélkül országosan keress.

## Használat

- `pc check`: alapkeresés és teljes értékelés.
- `pc check, kulcsszó: pc 64gb, 100–250 ezer Ft, Budapest`: egyedi szűrők.
- Az új vásárlási követelmények felülírják a személyes alapértékeket.

## Python

Python 3 szükséges. `python -m pip install -r scripts/requirements.txt`, majd `python -m playwright install chromium`.

`python -X utf8 -u scripts/jofogas_pc_gyujto.py --keyword "pc 32gb" --min-price 40000 --max-price 400000 --location magyarorszag --max-pages 10`

A kimenet az aktuális munkakönyvtárba kerül. Minden gyűjtéshez új mappát használj. A webhely szerkezete változhat; a hibás vagy részleges gyűjtést a skill szabályai szerint jelölni kell. Az értékelést a Codex végzi a SKILL.md szabályaival, nem a Python.
