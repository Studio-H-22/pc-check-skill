# Facebook Marketplace — Apify kiegészítés

**Alapértelmezésben kikapcsolva.** Az alapfolyamatban csak külön scraperdíj és kreditfogyasztás nélküli megoldás használható. Az ajándék 5 USD Apify-kredit nem számít ingyenes gyűjtési módnak. Ezt a régi, opcionális eljárást kizárólag új, kifejezett Apify-kéréskor alkalmazd; egy korábbi futás engedélye nem öröklődik. Ingyenes alapfolyamat: [free-collection.md](free-collection.md).

Actor: `apify/facebook-marketplace-scraper`, azonosító: `U5DUNxhH3qKt5PnCf`.

- [Console / input](https://console.apify.com/actors/U5DUNxhH3qKt5PnCf/input)
- [Aktuális bemeneti séma](https://console.apify.com/actors/U5DUNxhH3qKt5PnCf/info/inputSchema)
- [Aktuális díjazás](https://console.apify.com/actors/U5DUNxhH3qKt5PnCf/info/pricing)

## Bemenet

A 2026. október 4-én ellenőrzött séma:

```json
{
  "startUrls": [
    {"url": "https://www.facebook.com/marketplace/budapest/search/?query=pc%2032gb"}
  ],
  "resultsLimit": 100,
  "includeListingDetails": true
}
```

- `startUrls`: kötelező URL-objektumlista; hely-, kategória- és keresési Marketplace URL-t fogad.
- `resultsLimit`: pozitív egész. Elhagyva korlátlan gyűjtés lehet; mindig állíts be véges korlátot. A 100 példa, nem kötelező vagy garantált találatszám. Több URL esetén a korlát összesített/per-URL jelentését az aktuális dokumentációból ellenőrizd.
- `includeListingDetails`: legyen `true`, mert alapértelmezésben `false`, és a PC-pontozáshoz szükség van a leírásra. Az extra részletek külön díjasak lehetnek.

A felhasználó kulcsszavát, ársávját és helyszűrőjét vidd át a Facebook keresőjében ellenőrzött URL-be; ne találj ki actor-mezőket árra vagy megyére. Budapest és Pest megye nem egyenértékű egy budapesti keresési sugárral. A Marketplace találatai között a célterületen kívüli ajánlat is lehet: az eredmény tényleges helyadata alapján utószűrj. Ismeretlen helyű rekordot ne nevezz igazoltan megfelelőnek. Helyszűrő nélkül ne állítsd egy budapesti keresésről, hogy országos.

Az Apify futtatása kreditet/költséget fogyaszt. Új futtatás előtt ellenőrizd az aktuális, részleteket is tartalmazó díjazást és a felhasználó által engedélyezett költségkeretet. Ha nincs elégséges engedélyezett keret, konkrét becsült költségplafonra kérj jóváhagyást; a skill bővítése önmagában nem futtatási vagy előfizetési engedély. Ne indíts új előfizetést, automatikus ismétlést vagy ütemezést. A README régi árait ne tekintsd mérvadónak.

## Futtatás és eredmény

Használd az elérhető Apify-kapcsolatot, API-t vagy bejelentkezett Console-t. Ne másolj API-kulcsot a skillbe, inputfájlba, naplóba vagy chatbe. Beállítható paramétereket és gyűjtési korlátot mutass röviden, ha jóváhagyás kell.

Várd meg a futtatás végállapotát; olvasd a naplót és exportáld a konkrét futtatás datasetjét JSON-ként a friss gyűjtés mappájába. Őrizd meg a run/dataset azonosítót, időpontot, bemenetet, futtatási állapotot, nyers rekordszámot és a szűrés utáni egyedi darabszámot. Hibás/részleges futtatást ne nevezz teljesnek. Ne indíts automatikus újrafuttatást ugyanarra az üres vagy hibás eredményre, mert további költséget okozhat.

## Mezők és közös pontozás

A dokumentált keresési rekordmezők: `id`, `listingUrl`, `facebookUrl`, `marketplace_listing_title`, `listing_price.amount`, `listing_price.formatted_amount`, `location.reverse_geocode.city`, `location.reverse_geocode.state`, `is_live`, `is_pending`, `is_sold`, `is_hidden`. A részletes leírás és attribútumok mezőneveit a tényleges exportból ellenőrizd; ne feltételezd, hogy minden rekord tartalmazza őket.

- Ár: pénznem ellenőrzése után dolgozz Ft-ban. Az `amount_with_offset_in_currency` értéket ne használd közvetlenül árként; ne szorozd automatikusan az `amount` értékét százzal. Hiányzó/alkuképes árat ne pótolj kitalált értékkel.
- Sold/hidden rekordot zárj ki a vásárlási shortlistből; pending rekordot jelölj függőként. A státusz nem garantálja az elérhetőséget.
- Facebook deduplikálás: item-ID, illetve normalizált `/marketplace/item/<id>/` URL. Tartsd meg az eredeti rekordazonosítókat/sorszámokat és a forrást.
- Jófogás és Facebook közt azonos konfiguráció/cím nem bizonyított duplikátum. Csak igazolt azonosságnál vond össze; eltérő árakat és forráslinkeket őrizd meg.
- A leírásból nyerd ki ugyanazokat a CPU/GPU/VRAM/RAM/alaplap/tárhely/táp/hűtés/garancia mezőket, mint Jófogásnál. Hiányzó modell esetén ne találgass. A forrástól függetlenül ugyanazok a /1000 súlyok és vásárlási feltételek érvényesek.
- Az adott kérés friss Jófogás- és Facebook-listájából közös teljes rangsort és közös vásárlási shortlistet készíts, teljes eredeti címekkel és kattintható hirdetéslinkekkel. A források nyers és egyedi darabszámait külön is közöld. Ha a Facebook nem futott, ezt egyértelműen nevezd meg.
