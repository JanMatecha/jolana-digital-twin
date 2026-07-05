# Data implementation plan

Stav dokumentu: 2026-07-05  
Repo: `JanMatecha/jolana-digital-twin`

Tento dokument popisuje cilovou datovou architekturu projektu Jolana Digital Twin, aktualni stav implementace a dalsi kroky. Cilem je mit jasne oddelene zdrojove soubory, hlavni databazi, prilohy a odvozene vystupy tak, aby byla data bezpecna, dohledatelna a nepocitala se omylem dvakrat.

## 1. Zakladni princip

```text
GitHub = kod aplikace + anonymizovana ukazkova data
Docker image = behove prostredi
Notebook = lokalni vyvojova data
NAS = produkcni zdravotni data
SQLite = hlavni aktualni databaze
Raw CSV / fotky / audio = puvodni zdroje a prilohy
```

Skutecna zdravotni data se nikdy nemaji commitovat do Gitu. GitHub ma obsahovat jen kod, dokumentaci a anonymizovana testovaci data.

## 2. Cilove ulozeni dat

### Vyvoj na notebooku

```text
JOLANA_ENV=dev
JOLANA_DATA_DIR=data-dev
JOLANA_DB_PATH=data-dev/db/jolana-dev.sqlite
```

### Produkce na NASu uvnitr Dockeru

```text
JOLANA_ENV=prod
JOLANA_DATA_DIR=/app/data
JOLANA_DB_PATH=/app/data/db/jolana.sqlite
```

### Produkce fyzicky na NASu

```text
/volume1/docker/jolana-digital-twin/data/db/jolana.sqlite
```

Cilove budou produkcni data ulozena ve strukture:

```text
data/
  raw/
    libre/
    dexcom/
    gluroo/
    nightscout/
    other/
  processed/
  manual/
  db/
    jolana.sqlite
  attachments/
    meals/
  derived/
    markdown/
    json/
  exports/
  backups/
```

Vyklad slozek:

```text
raw/         puvodni exporty a vstupni soubory, nemenit
processed/   pripadne normalizovane mezivystupy
manual/      docasne rucni CSV soubory a prechodna data
db/          hlavni SQLite databaze
attachments/ fotky, audio a dalsi prilohy
derived/     transcript, summary, extracted JSON a dalsi odvozene vystupy
exports/     vystupy z aplikace
backups/     zalohy databaze a dulezitych souboru
```

## 3. Hlavni databaze

Hlavni databaze bude SQLite:

```text
Vyvoj:    data-dev/db/jolana-dev.sqlite
Produkce: /app/data/db/jolana.sqlite
NAS:      /volume1/docker/jolana-digital-twin/data/db/jolana.sqlite
```

SQLite je pro tuto fazi vhodna, protoze aplikace bezi lokalne nebo na NASu, data jsou osobni a neni potreba samostatny databazovy server.

## 4. Aktualni stav implementace

Hotovo:

```text
- existuje konfigurace JOLANA_ENV, JOLANA_DATA_DIR a JOLANA_DB_PATH
- aplikace umi vytvorit datove podslozky
- Docker mountuje datove slozky mimo image
- Git ignoruje produkcni data, SQLite databaze, CSV exporty, fotky a audio
- existuje persistentni SQLite foundation
- pri startu aplikace se vytvori databaze podle JOLANA_DB_PATH
- existuje tabulka schema_migrations se schema verzi 1
- aplikace v UI ukazuje, jaky CSV zdroj je prave nacteny
- existuje explicitni persistentni import Libre CSV do JOLANA_DB_PATH
- raw kopie importovanych Libre CSV se ukladaji do data/raw/libre/
- importy jsou chranene proti duplicitam pomoci sha256 checksumu
- v UI existuje volba Nacist z databaze pro zobrazeni dat z persistentni SQLite
```

Dulezite omezeni aktualniho stavu:

```text
CSV -> temporary SQLite -> dataframe -> graf
nebo
persistentni SQLite -> dataframe -> graf
```

Aplikace stale umi nacitat Libre CSV pres docasnou SQLite databazi pro aktualni zobrazeni. Persistentni `jolana.sqlite` se uz vytvari, lze do ni explicitne importovat Libre CSV a pres volbu `Nacist z databaze` ji lze pouzit jako zdroj grafu.

## 5. Soucasne zdroje dat v UI

### Anonymni ukazkova data

Soubor z repozitare:

```text
data/examples/free_style_libre_sample.csv
```

Pouziva se pro demo, testy a bezpecny vyvoj.

### Lokalni realna data

CSV soubory nalezene na stroji, kde aplikace bezi.

Aplikace hleda:

```text
<JOLANA_DATA_DIR>/raw/*.csv
*_glucose_*.csv v koreni projektu jako legacy fallback
```

Vyvoj typicky:

```text
data-dev/raw/
```

Produkce uvnitr Dockeru:

```text
/app/data/raw/
```

### Nahrat CSV

Upload pres prohlizec je aktualne docasny. Soubor se pouzije jen pro aktualni zobrazeni a automaticky se neuklada do `data/raw` ani do persistentni databaze.

### Nacist z databaze

Volba cte glukozu, inzulin a jidlo z persistentni SQLite databaze podle `JOLANA_DB_PATH`. CSV/temporary workflow zustava dostupne pro nahled konkretniho souboru a pro explicitni import.

## 6. Cilovy tok dat ze zdroju

### Libre CSV

Cilovy tok:

```text
Libre export
-> ulozit kopii do data/raw/libre/
-> spocitat sha256 checksum
-> zapsat import do imports
-> precist readerem do domenoveho formatu
-> ulozit glucose_readings
-> ulozit insulin_doses
-> ulozit meals
```

Dulezite vlastnosti:

```text
- stejny soubor se nema importovat dvakrat
- import ma byt transakcni
- raw soubor se nema prepisovat
- import ma byt dohledatelny pres imports a checksum
```

### Rucni inzulin

Cilovy tok:

```text
uzivatel zada davku inzulinu v UI
-> zaznam se ulozi do insulin_doses
-> source = manual
-> status = confirmed nebo manual
-> model muze pouzit jen potvrzena a bezpecna data
```

Bezpecnostni pravidlo: pokud pozdeji Libre import prinese podobnou davku, aplikace ji nesmi automaticky pricist jako dalsi davku. Musi ji oznacit jako moznou duplicitu a nechat uzivatele rozhodnout.

### Rucni jidlo

Cilovy tok:

```text
uzivatel zada jidlo v UI
-> zaznam se ulozi do meals
-> carbs_g / fat_g / protein_g
-> source = manual
-> status = confirmed nebo draft
```

Soucasny prechodny stav: rucni jidlo se muze nacitat ze souboru:

```text
<JOLANA_DATA_DIR>/manual/meals.csv
```

### Fotky jidel

Cilovy tok:

```text
uzivatel prida fotku jidla
-> soubor se ulozi do data/attachments/meals/...
-> SQLite ulozi metadata a cestu k souboru
-> AI odhad zustane draft
-> potvrzene hodnoty se ulozi do meals
```

Fotky se nemaji ukladat jako BLOB do SQLite.

### Audio poznamky

Cilovy tok:

```text
uzivatel nahraje hlasovou poznamku
-> audio se ulozi do attachments
-> transcript / summary / extracted JSON do derived
-> odhad zustane draft
-> potvrzene hodnoty se ulozi do meals nebo insulin_doses
```

### Dexcom, Gluroo, Nightscout

Budouci zdroje maji mit vlastni reader, ale zapisovat do stejneho domenoveho modelu:

```text
reader konkretniho zdroje
-> jednotny domenovy format
-> source_records / glucose_readings / insulin_doses / meals
```

## 7. Cilovy databazovy model

Soucasny minimalni zaklad:

```text
schema_migrations
imports
glucose_readings
insulin_doses
meals
```

Cilovy model:

```text
imports
source_records
glucose_readings
insulin_doses
meals
meal_attachments
meal_extractions
duplicate_groups
audit_log
users / actors
```

Princip:

```text
source_records = puvodni importovana fakta
curated records = potvrzena data, ktera smi pouzit model
```

Priklad s inzulinem:

```text
source_records:
  Libre:  12:05, 4 jednotky
  Manual: 12:03, 4 jednotky

curated insulin_doses:
  potvrzena jedna davka kolem 12:04, 4 jednotky
```

Cilem je zabranit tomu, aby se jedna realna davka inzulinu pocitala dvakrat.

## 8. Statusy a bezpecnost modelu

Navrzene statusy pro inzulin:

```text
imported
manual
confirmed
possible_duplicate
ignored
corrected
deleted
```

Navrzene statusy pro jidlo:

```text
draft
confirmed
possible_duplicate
ignored
deleted
```

Model ma pouzivat pouze bezpecna / potvrzena data. Nemel by pouzivat:

```text
possible_duplicate
ignored
deleted
draft, pokud neni vyslovne povoleno pro experiment
```

## 9. Deduplikace inzulinu

Problem:

```text
Manual: 12:03, 4 U
Libre:  12:05, 4 U
```

To neni 8 U, ale pravdepodobne jedna davka.

Navrzene pravidlo pro moznou duplicitu:

```text
- casovy rozdil napr. +-15 minut
- stejna nebo velmi podobna davka
- stejny nebo neznamy typ inzulinu
- rozdilny zdroj
```

Chovani:

```text
- nebrat obe davky automaticky do modelu
- oznacit jako possible_duplicate
- nabidnout uzivateli akci:
  - sloucit jako jednu davku
  - ponechat obe
  - ignorovat manual
  - ignorovat Libre
```

## 10. Dalsi implementacni kroky

### Krok 1: Trvaly import Libre CSV do persistentni DB

Cil:

```text
Libre CSV -> data/raw/libre/ -> imports -> glucose_readings / insulin_doses / meals
```

Scope:

```text
- explicitni akce importu
- ulozit raw soubor
- sha256 checksum
- zabranit duplicitnimu importu stejneho souboru
- import v jedne transakci
- zatim bez deduplikace
```

Stav: implementovano jako explicitni import spusteny uzivatelem ve Streamlit sidebaru. CSV/temporary SQLite workflow zustava zachovane pro nahled a import.

### Krok 2: UI volba Nacist z databaze

Po trvalem importu pridat zdroj dat:

```text
Nacist z databaze
```

Aplikace pak bude umet zobrazovat data z persistentni SQLite, ne jen z aktualniho CSV.

Stav: implementovano. Volba `Nacist z databaze` cte `glucose_readings`, `insulin_doses` a `meals` z persistentni SQLite databaze podle `JOLANA_DB_PATH`.

### Krok 3: Rucni zadavani jidla a inzulinu

Pridat UI formulare:

```text
pridat jidlo
pridat inzulin
upravit zaznam
smazat/ignorovat zaznam
```

Zapisovat primo do SQLite.

### Krok 4: Statusy, audit a curated data

Pridat sloupce a pravidla:

```text
status
created_at
updated_at
deleted_at
created_by
source
source_record_id
```

### Krok 5: Deduplikace inzulinu

Detekovat mozne duplicity mezi manual, Libre a dalsimi zdroji. Model nesmi pouzit neresene duplicity.

### Krok 6: Prilohy k jidlu

Pridat podporu pro fotky/audio:

```text
attachments/meals/...
meal_attachments
meal_extractions
AI draft -> potvrzeni uzivatelem -> meals
```

### Krok 7: Backup

Zalohovat minimalne:

```text
data/db/jolana.sqlite
data/raw/
data/attachments/
data/manual/
```

Pred budoucimi migracemi produkcni databaze vzdy udelat backup.

## 11. Historie dulezitych rozhodnuti a PR

```text
PR #6 / #7:
  zavedena konfigurace datovych cest a pouzivani JOLANA_DATA_DIR

PR #10:
  persistentni SQLite foundation byla portovana na main
  aplikace pri startu vytvari databazi podle JOLANA_DB_PATH
  pridana schema_migrations verze 1

PR #11:
  UI zobrazuje aktualne vybrany zdroj dat
  rozlisuje <JOLANA_DATA_DIR>/raw a legacy fallback
  upload CSV je jasne oznacen jako docasny

PR #13:
  pridan explicitni persistentni import Libre CSV
  raw kopie se uklada do data/raw/libre/
  sha256 checksum chrani proti duplicitnimu importu

Tento PR:
  pridana volba Nacist z databaze
  grafy mohou cist z persistentni SQLite
  CSV temporary workflow zustalo zachovane
```

## 12. Kratke shrnuti

Konecny cil:

```text
Skutecna produkcni data budou na NASu v /volume1/docker/jolana-digital-twin/data/.
Hlavni pravda bude v SQLite databazi data/db/jolana.sqlite.
Raw CSV, fotky a audio budou jako soubory vedle databaze.
GitHub bude obsahovat jen kod, dokumentaci a anonymizovana testovaci data.
```

Aktualni stav:

```text
Persistentni SQLite se uz vytvari.
Datove slozky jsou oddelene pro dev a prod.
Aplikace umi explicitne importovat Libre CSV do persistentni DB.
Aplikace umi zobrazit graf z persistentni DB pres volbu Nacist z databaze.
CSV temporary workflow porad existuje pro nahled a import.
```

Nejblizsi velky krok:

```text
Rucni zadavani jidla/inzulinu do SQLite nebo statusy, audit a curated data.
```
