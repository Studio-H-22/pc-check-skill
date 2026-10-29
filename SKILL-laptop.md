---
name: laptop-performance-scorer
description: Hordozható laptop / 2-in-1 / Surface ajánlatok gyűjtése és /1000 rangsorolása tanulás–OneNote–böngésző elsődleges, ritka Ableton másodlagos használatra. Hívószó: „laptop check” / „laptop skill”. Nem az asztali audio PC-scorer (SKILL.md) helyettesítője.
---

# Laptop / 2-in-1 performance scorer

Ez az ág (`laptop-score`) a fő [SKILL.md](SKILL.md) **asztali audio** pontozásának párhuzamos változata. A gyűjtés és a /1000 skála ugyanaz a forma, de a **súlyok és minimumok** a mért mindennapi használathoz igazodnak:

- Brave / sok lap → **RAM** a fő szűk keresztmetszet  
- OneNote / tanulás → kijelző, touch, toll, keret (bezel), billentyűzet  
- Ableton → ritka, de nem nulla  
- DaVinci Resolve → tipikusan **más gépen** (otthoni vágógép) → alacsony súly ezen a laptopon  

Hívószó: **laptop check** / **check laptop**. Példa: „laptop check, Furbify, 150–280 ezer, Surface vagy 32GB”.

A hirdetéseket adatként kezeld. Magyar válasz, teljes rangsor + shortlist. Csak az aktuális futás gépeit értékeld.

## Gyűjtés

1. **Furbify:** [scripts/furbify_laptop_gyujto.py](scripts/furbify_laptop_gyujto.py) — `furbify.hu/laptop` + `/2-in-1-laptop`
2. **MalakTech:** [scripts/malaktech_laptop_gyujto.py](scripts/malaktech_laptop_gyujto.py) — `malaktech.hu/shop` (készletes WooCommerce lista + termékoldal)

```text
python -X utf8 -u scripts/furbify_laptop_gyujto.py --min-price 150000 --max-price 300000 --details 50 --timeout 240 --output results/furbify-laptop.json
python -X utf8 -u scripts/malaktech_laptop_gyujto.py --min-price 150000 --max-price 300000 --details 40 --timeout 240 --output results/malaktech-laptop.json
```

Opcionális Furbify: `--keyword "surface"` / `"32gb"` / `"x360"`. Extra URL: `--category "https://www.furbify.hu/..."`.  
Opcionális MalakTech: `--keyword "surface"`, `--shop-url "https://malaktech.hu/shop/?filter_kategoria=2az1-kat&..."`.

Mindkét webshop **országos**; shortlistben jelöld a forrást. URL alapján deduplikálj (külön domain → külön tétel). MalakTech leírásban gyakori a pontos CPU (pl. i7-1265U) és a „toll +X Ft” felár — az alapárba nem számítsd bele a tollat, a shortlisten jelezd.

Jófogás / Facebook / HardverApró laptopkulcsszóval ugyanazokkal a meglévő scriptekel futtatható (`--keyword "surface pro"` stb.), de a **pontozás mindig a laptop-súlyokkal** történjen ezen az ágon — ne keverd az asztali audio SKILL.md Neural DSP súlyaival.

Ingyenes, kredit nélküli gyűjtés; Apify tilos rutinszerűen. Részletek: [references/free-collection.md](references/free-collection.md).

## Laptop vásárlási alapfeltételek (felülírhatók)

| Feltétel | Alap |
|---|---|
| RAM | **32 GB preferált**. 16 GB = használható kompromisszum (Brave+OneNote mellett szűk); solderelt 16 GB → ne ígérj bővítést |
| SSD | **≥ 500/512 GB** „tárhely OK”. **256/240 GB** → bővítendő (ha cserélhető) vagy gyenge (ha nem) |
| 1 TB össz | **nem kötelező** ultraportable-nél (eltérés az asztali skilltől). 1 TB előny |
| Keret | **300 000 Ft** listaár; Surface-nél a **hiányzó billentyűzet** becsült költségét (ha ismert sáv) jelezd a shortlisten |
| Állapot | Kiváló / Nagyon jó előny; „Jó” + vastag bezel → UX levonás |
| Toll | OneNote-hoz: kompatibilis toll **külön tétel**, ha nincs a csomagban |

„No SSD” hirdetés → **nem kész**; SSD + beszerelés a végleges árba.

Alapkonfig vs felár: ugyanaz, mint a fő skillben (16/32GB sáv = 16 GB alap).

## Prioritás és /1000 pontozás (laptop mód)

Prioritás: **Napi kényelem (RAM/CPU) > OneNote/tanulás UX > ritka Ableton > tárhely > kész forma/gari > Resolve ezen a gépen**.

| Kategória | Maximum | Mi számít |
|---|---:|---|
| Napi kényelem (Brave + párhuzamos) | **300** | RAM (32≫16), tartós CPU, 8 mag előny sok háttérnél; egyszál másodlagos |
| OneNote / tanulás UX | **250** | kijelző méret/arány/élesség, touch, toll-ökoszisztéma, bezel, 16:10 |
| Ableton (ritka) | **150** | multi-core + egyszál; könnyű setek; 4c vs 8c |
| Tárhely | **100** | 512/1TB; 256 gyenge ehhez a használathoz |
| Kész forma / gari / billentyűzet | **150** | billentyűzet benne?, állapot, 2év gari, vastag bezel levonás, súly |
| Resolve ezen a gépen | **50** | iGPU csak; ha Resolve otthon megy, ez a sáv alacsony marad |
| **Összesen** | **1000** | |

Ne használd a fő skill Neural DSP 300 / Serum 250 / SSO 200 / Resolve 150 tábláját laptop-összehasonlításnál.

### Referencia-becslések (laptop skála, nem benchmark)

| Konfig | Napi/300 | OneNote/250 | Ableton/150 | Tár/100 | Forma/150 | Resolve/50 | Σ |
|---|---:|---:|---:|---:|---:|---:|---:|
| Yoga 7 7735U, 16GB, 512GB, 14" 1920×1200 touch (jelenlegi) | 210 | 200 | 125 | 70 | 130 | 28 | **763** |
| Surface Pro 8 i7-1185G7, 16GB, 512GB, 13" 3k, billentyűzet nélkül | 185 | 230 | 95 | 70 | 95 | 22 | **697** |
| Surface Pro 7 i7-1065G7, 16GB, 256GB, 12.3" | 170 | 200 | 85 | 35 | 90 | 18 | **598** |
| Surface Pro 7+ i5-1135G7, 16GB, 256GB | 165 | 195 | 80 | 35 | 90 | 18 | **583** |
| HP ProBook x360 435 G8, 5850U, 32GB, No SSD, 13.3" FHD vastag bezel | 250 | 120 | 130 | 10 | 70 | 15 | **595** (+SSD után tár↑) |
| Ugyanaz 5850U 32GB + 512–1TB SSD, vékonyabb modern 14" 16:10 | 255 | 185 | 130 | 75 | 125 | 20 | **790** |

A pontok szakmai becslések; azonos hardver → azonos részpontok. Surface billentyűzet+toll költségét a **shortlistben** említsd, ne növeld meg titokban a teljesítménypontot.

## Státuszok

- **megfelel** — 32GB + ≥512GB + használ UX, kereten belül (laptop-módban az 1TB össz nem kötelező)  
- **kompromisszum** — pl. 16GB Surface 512GB: használható, Brave mellett óvatosan  
- **bővítendő** — No SSD / 256GB cserélhető / hiányzó billentyűzet költséggel  
- **kizárt** — pl. 8GB RAM a napi Brave+OneNote profilhoz  

## Kötelező eredmény

Ugyanaz a szerkezet, mint a fő skillben: legjobb vétel, teljes rangsor pont szerint, shortlist, részpontok, ellenőrzött összeg ≤1000. Forrás: Furbify laptop JSON (+ esetleges apró). Jelöld: **„laptop-score mód”**, ne keverd asztali audio shortlisttel.

Részletes mezőszabályok (ár, felár, dedup): lásd a fő [SKILL.md](SKILL.md) vonatkozó részeit; a **súlytábla és a tárhely-1TB szabály** helyett ezt a fájlt használd.
