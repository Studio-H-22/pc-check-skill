# PC check — teljes skill

Jófogás, **Facebook Marketplace** és **HardverApró** friss PC-hirdetéseinek ingyenes gyűjtése, majd audio-központú /1000 értékelése. Teljes, hordozható skill, 2026. október 13-án pontosított adatfeldolgozással és pontozási referenciákkal; HardverApró-gyűjtővel kiegészítve.

## Bárkinek, másik gépen, Codexben

A repó nyilvános; letöltéséhez nem kell GitHub-bejelentkezés. Másold ezt a kérésedbe:

> Telepítsd a teljes PC check skillt a https://github.com/Studio-H-22/pc-check-skill repó gyökeréből, a scripts és references mappákkal együtt. A „pc check” és „check pc” kérésre olvasd el a SKILL.md-t, futtasd a Jófogás-, Facebook- és HardverApró-gyűjtést, majd értékeld a friss eredményt. Alaphelyszín Budapest és Pest vármegye mindhárom forrásnál. Csak ingyenes, kreditfogyasztás nélküli gyűjtőt használj. A működő környezetet használd újra.

## Alapértékek

- Keresőkifejezés: `pc 32gb`; keresési ársáv: 40 000–400 000 Ft.
- Terület: **Budapest és Pest vármegye**, Jófogáson, Facebookon és HardverAprón. Jófogáson és HardverAprón két keresés (`budapest` + `pest`), majd deduplikálás. Facebookon az igazolt helyadat szerint szűrni kell: a budapesti keresés más megyei találatokat is adhat. HardverAprón a `city` mező több települést is listázhat.
- Vásárlási keret: 300 000 Ft, kivételesen legfeljebb 350 000 Ft a kötelező bővítéssel együtt.
- Minimum: 32 GB RAM, legalább 500/512 GB SSD, összesen legalább 1 TB belső tárhely.
- Prioritás: Neural DSP > Serum > Spitfire SSO > Ableton > DaVinci > ár/érték. Súlyok és a teljes eredmény követelményei: [SKILL.md](SKILL.md).
- Nincs kötelező top 3 korlát; minden aktuális találatot meg kell őrizni, az adathiányos és kizárt hirdetéseket is.

Az alapértékek szabadon felülírhatók a kérésben. Nem kell ugyanazt a keretet vagy helyszínt használnod. Példák:

```text
pc check
pc check: gamer pc, 64 GB RAM, 150–300 ezer Ft, Budapest és Pest vármegye
pc check: pc 32gb, 100–250 ezer Ft, országosan; vásárlási maximum 250 ezer Ft
pc check: pc 32gb, 80–200 ezer Ft, Győr-Moson-Sopron; minimum 1 TB SSD
```

A keresési ársáv és a vásárlási maximum két külön beállítás: írd le mindkettőt, ha eltérnek. Jófogáson más területhez a webhelyen ellenőrzött hely-útvonalat kell használni. Facebookon a keresési középpont mellett a tényleges hirdetéshelyet is ellenőrizni kell. A `pc 32gb` kulcsszó nem igazolja, hogy a gépben valóban 32 GB RAM van; ezt a teljes leírás dönti el.

A pontozás elsősorban zenekészítésre és másodsorban videóvágásra készült. Általános gaming-FPS rangsornak nem tekinthető; más célhoz a kérésben adj meg új értékelési prioritást.

## Tartalom

- [SKILL.md](SKILL.md): a teljes értékelési és gyűjtési szabályrendszer.
- [Jófogás Python](scripts/jofogas_pc_gyujto.py): teljes leírások az oldalba ágyazott adatokból; a keresési URL-be is átadott árszűrővel.
- [Facebook Python](scripts/facebook_pc_gyujto.py): saját, ingyenes, nyilvános Marketplace-gyűjtő; API-kulcs és proxy nélkül.
- [HardverApró Python](scripts/hardverapro_pc_gyujto.py): komplett asztali PC kategória, megye- és árszűrővel; JSON + `.txt` kimenet.
- [Függőségek](scripts/requirements.txt).
- [Ingyenes gyűjtés és korlátai](references/free-collection.md).
- [Apify régi opcionális eljárás](references/apify-marketplace.md): alapértelmezésben kikapcsolva; csak új, kifejezett Apify-kérésre használható.

## Python futtatás

Python 3 szükséges; a helyi folyamat Python 3.13-mal működött. A repó mappájából az első alkalommal:

```text
python -m pip install -r scripts/requirements.txt
python -m playwright install chromium
```

A működő környezetet következő alkalommal ne telepítsd újra. Minden gyűjtéshez új kimeneti mappát használj. A következő példában előbb hozd létre a `results` mappát; a parancsokat a repó gyökeréből futtasd:

```text
python -X utf8 -u scripts/jofogas_pc_gyujto.py --keyword "pc 32gb" --min-price 40000 --max-price 400000 --location budapest --max-pages 10 --output results/jofogas-budapest.txt
python -X utf8 -u scripts/jofogas_pc_gyujto.py --keyword "pc 32gb" --min-price 40000 --max-price 400000 --location pest --max-pages 10 --output results/jofogas-pest.txt
python -X utf8 -u scripts/facebook_pc_gyujto.py --keyword "pc 32gb" --min-price 40000 --max-price 400000 --location budapest --limit 50 --details 30 --timeout 60 --output results/facebook.json
python -X utf8 -u scripts/hardverapro_pc_gyujto.py --keyword "32gb" --min-price 40000 --max-price 400000 --location budapest --max-pages 5 --details 40 --timeout 180 --output results/hardverapro-budapest.json
python -X utf8 -u scripts/hardverapro_pc_gyujto.py --keyword "32gb" --min-price 40000 --max-price 400000 --location pest --max-pages 5 --details 40 --timeout 180 --output results/hardverapro-pest.json
```

A külön keresések egymással párhuzamosan futtathatók. A Facebook első nyilvános találati adagot gyűjt; a 60 másodperc felső célkorlát, nem teljes kínálat vagy garantált találatszám. A leírásokat a `description.text` vagy `description_evidence` mezőből olvasd. Az üres leírás nem sikeres adatkinyerés akkor sem, ha a státusz olvasottnak jelöli. Az ár `price.amount`, nem az átváltott `amount_with_offset_in_currency`.

## Elemzés és telefonos használat

### Ugyanaz a feldolgozás minden asszisztensben

Codexben, OpenClawban és más Python-képes környezetben is olvasd el a SKILL.md **Mezők, egységes pontozás és válaszforma** részét. Ez a Facebook-adatok kiolvasásának és az eredmény ellenőrzésének kötelező része. Frissítéskor a SKILL.md mellett a Facebook Python fájlt is cseréld le; a korábbi telepítés magától nem frissül.

Az új Facebook-export `schema_version: 2`, minden rekordban `price_huf`, `price_source`, `city`, `county_code`, `region_ok`, `description_text` mezőkkel. A nyers mezők is megmaradnak. Régi exportban az ár a `price.amount`, a város/megye a `location.reverse_geocode` alatt van; saját JSON-átalakításban se veszítsd el őket. A `BU` Budapest, a `PE` Pest vármegye: Ráckeve PE kóddal helyi találat. Leírásban megadott, egyértelmű teljesgép-ár is használható forrásjelöléssel; a hiányzó strukturált mező nem automatikus kizárás.

240+500GB SSD **740GB, ezért bővítendő** az 1TB minimumhoz. A rangsor és shortlist egyetlen értékelési rekordból készüljön: azonos gép mindenütt azonos pontot/státuszt kapjon, a teljes teljesítménylista pont szerint csökkenjen. A skill referencia-becslései közelebb tartják a különböző asszisztensek skáláját; nem mért benchmarkok, és más hardver vagy hiányos leírás nem kap automatikusan ugyanannyi pontot. A hirdetések változása miatt a győztes és a darabszám futásonként eltérhet.

A Python adatot gyűjt. A rangsort **Codex / az AI-asszisztens készíti a SKILL.md szerint**; nincs elrejtett automatikus pontozó vagy fizetős LLM API. A pontszám szakmai becslés, nem mért benchmark, az eredeti régi kalibráció nem áll rendelkezésre.

Telefonról a repó és a szabályok olvashatók, és a kimenetek átadhatók az asszisztensnek. A link önmagában nem futtat Pythont; gyűjtéshez Python/Playwright futtatására alkalmas gép vagy környezet szükséges. A skill nem szinkronizálódik automatikusan minden eszközre/profilra.

Azonos szabályrendszer és program újra használható, de a hirdetések és a webhelyek időközben változhatnak. Nulla találatot, részleges gyűjtést és technikai hibát külön kell jelezni; régi adatot ne nevezz frissnek. A teljes hordozható változat egy adott GitHub-commitból is letölthető.
