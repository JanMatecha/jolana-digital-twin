# Jolana Digital Twin

Postupne budovane digitalni dvojce pro praci s daty z diabetu 1. typu.

Prvni iterace umi:

- nacist CSV export z FreeStyle Libre,
- vycistit casove znacky a ciselne hodnoty s desetinnou carkou,
- prevest data pres readery do univerzalniho domenoveho formatu,
- ulozit glukozu, jidlo a inzulin do SQLite,
- nacist rucne doplnene jidlo z CSV,
- zobrazit interaktivni webovy graf v prohlizeci,
- porovnat merenou glukozu s jednoduchym odezvovym modelem,
- spocitat model glukozy v Pythonu i v Modelice a vizualne porovnat vysledky.

## Co musi byt nainstalovane v systemu

Zakladni webova aplikace potrebuje:

- Python 3.11 nebo novejsi,
- `pip` pro instalaci Python balicku,
- Git pro stazeni projektu a verzovani,
- moderni webovy prohlizec, napr. Edge, Chrome nebo Firefox.

Pro praci s Modelica modely je navic potreba:

- OpenModelica s dostupnym prikazem `omc` v systemove `PATH`,
- volitelne OpenModelica MCP server, pokud se modely kontroluji nebo spousti z Codexu.

Webova aplikace umi OpenModelica spustit primo z Pythonu. Pokud `omc` neni v
`PATH`, pokusi se najit beznou instalaci ve `C:\Program Files\OpenModelica...`.
Kdyz OpenModelica dostupna neni, web stale zobrazi Python model a ukaze
varovani, ze Modelica simulace neprobehla.

Na Windows je vhodne overit instalaci prikazy:

```powershell
python --version
python -m pip --version
git --version
omc --version
```

Python knihovny pouzite projektem jsou uvedene v `requirements.txt`:

- `pandas` pro nacitani a transformaci tabulek,
- `matplotlib` pro puvodni CLI vystup do PNG,
- `streamlit` pro webove GUI,
- `plotly` pro interaktivni grafy,
- `cachetools<6` kvuli kompatibilite Streamlitu.

## Instalace Python prostredi

Doporuceny postup je pouzit virtualni prostredi:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Pokud uz je virtualni prostredi aktivni, staci:

```powershell
python -m pip install -r requirements.txt
```

## Spusteni webove aplikace

```powershell
python -m streamlit run jolana_digital_twin/presentation/streamlit_app.py
```

Aplikace se otevre v prohlizeci na `http://localhost:8501`.

Webove GUI umi:

- vybrat anonymni ukazkova data, lokalni realny Libre export nebo nahrany CSV soubor,
- filtrovat obdobi podle dne, hodiny a posuvniku,
- zobrazit merenou glukozu, modelovanou glukozu a samostatne vlivy sacharidu a inzulinu,
- zobrazit Python model a Modelica model v jednom grafu pro kontrolu shody,
- zobrazit jidlo, tuky a inzulin ve spodnim panelu se stejnou casovou osou,
- pouzit hover pres oba grafy najednou,
- ladit parametry odezvoveho modelu v postrannim panelu.

## Spusteni pres Docker na Synology NAS

Na Synology NAS DS918+ s DSM 7.1.1 a Docker balickem lze aplikaci spustit jako
Streamlit kontejner na portu `8501`.

Naklonovani repozitare:

```sh
git clone https://github.com/JanMatecha/jolana-digital-twin.git
cd jolana-digital-twin
```

Pred prvnim spustenim vytvor lokalni slozky pro data a vystupy. Tyto slozky
zustavaji mimo Git a mimo Docker image:

```sh
mkdir -p data/raw data/processed data/manual data/db outputs
```

Spusteni nebo rebuild kontejneru:

```sh
docker compose up -d --build
```

Overeni, ze kontejner bezi:

```sh
docker ps
```

Aplikace bude dostupna na:

```text
http://192.168.1.14:8501
```

Zobrazeni logu:

```sh
docker compose logs -f
```

Vypnuti kontejneru:

```sh
docker compose down
```

Persistentni slozky `data/raw`, `data/processed`, `data/manual`, `data/db` a
`outputs` jsou pripojene do kontejneru pres `docker-compose.yml`. Osobni
zdravotni data tak zustavaji jen lokalne na NASu a nejsou soucasti Gitu.

## CLI vystup do PNG

Jednoduchy puvodni CLI vystup do PNG zustava dostupny:

```powershell
python -m jolana_digital_twin.cli data/examples/free_style_libre_sample.csv --plot outputs/glucose.png
```

Vystupni obrazek bude ulozen do `outputs/glucose.png`.

## Testy

```powershell
python -m unittest discover
```

## Data

Do Gitu patri jen anonymizovana testovaci data:

```text
data/examples/
```

Ukazkova data lze znovu vygenerovat:

```powershell
python tools/generate_sample_data.py
```

Rucne doplnene jidlo se nacita ze souboru:

```text
data/manual/meals.csv
```

Tento soubor je lokalni a je ignorovany Gitem. Format CSV:

```csv
timestamp,carbs_g,fat_g,protein_g,note
2026-06-22 09:40,45.0,,,"snidane"
```

Sloupce `fat_g`, `protein_g` a `note` jsou volitelne z pohledu hodnot, ale
hlavicka souboru ma zustat stejna.

## Importni vrstva

Vstupni data se maji nejdriv prevest do univerzalniho domenoveho formatu a az
potom ulozit do SQLite. GUI a budouci model potom nemusi resit konkretni format
senzoru.

```text
Libre CSV / budouci senzory
        -> reader
        -> GlucoseReading / InsulinDose / Meal
        -> SQLite
        -> GUI / statistiky / Modelica
```

Aktualni moduly:

```text
jolana_digital_twin/domain/       # univerzalni datove objekty
jolana_digital_twin/readers/      # LibreCsvReader, pozdeji dalsi senzory
jolana_digital_twin/storage/      # SQLiteStore
jolana_digital_twin/application/  # importni pipeline
```

## Prvni Modelica model

Minimalni model je v `modelica/SimpleEventGlucose.mo`. Glukoza zacina prvni
merenou hodnotou ve vybranem obdobi, mezi udalostmi je konstantni, sacharidy ji
zvysi a inzulin ji snizi.

Hladsi odezvovy model je v `modelica/GaussianResponseGlucose.mo` a jeho
referencni pythonova verze je v `jolana_digital_twin/simulation/simple_event_model.py`.
Spousteni OpenModelica z Pythonu resi
`jolana_digital_twin/simulation/modelica_event_model.py`. Kazde jidlo a kazda
davka inzulinu vytvori Gaussovu odezvu v case. Ve webovem GUI je videt Python
model, Modelica model i samostatny vliv sacharidu a inzulinu.

Ve webovem GUI jsou zatim jednoduche parametry:

- citlivost na sacharidy: celkova plocha vzestupu pod odezvovou krivkou po 1 g sacharidu v `mmol/L*h`,
- inzulinova citlivost: celkova plocha poklesu pod odezvovou krivkou po 1 jednotce inzulinu v `mmol/L*h`,
- cas vrcholu odezvy sacharidu a inzulinu,
- delka odezvy sacharidu a inzulinu.

Druhy pojem se casto oznacuje jako insulin sensitivity factor nebo correction
factor. V realne lecbe se pouziva opatrneji a muze se lisit podle denni doby.

Model je zatim zamerne jednoduchy. Slouzi hlavne k overeni retezce:

```text
mereni + jidlo + inzulin -> udalosti -> simulace -> porovnani s merenim
```

Aktualni webovy workflow:

```text
Libre CSV + manualni jidlo
        -> readery
        -> docasna SQLite
        -> Python odezvovy model
        -> Modelica odezvovy model pres OpenModelica
        -> spolecny Plotly graf
```

Detailnejsi Mermaid diagram toku dat a Modelica workflow je v
`docs/modelica_visualization.md`.

Osobni zdravotni data zustavaji jen lokalne a jsou ignorovana Gitem:

```text
data/raw/        # puvodni Libre exporty
data/processed/  # vycistena data
data/manual/     # rucne zadany inzulin, jidlo, poznamky
data/db/         # pozdeji SQLite databaze
```

Aktualni Libre export lze dat napr. do `data/raw/` a spoustet:

```powershell
python -m jolana_digital_twin.cli data/raw/libre_export.csv --plot outputs/glucose.png
```

## Smer dalsich kroku

1. Pridat samostatny rucni CSV vstup pro inzulin tam, kde chybi v exportu senzoru.
2. Dodelat tuky v manualnim jidelnim CSV a zapojit je do budouciho modelu.
3. Kalibrovat parametry modelu proti realnym datum ve vybranem obdobi.
4. Pripravit stabilni ulozeni dat do lokalni SQLite databaze mimo docasne importy.
5. Postupne presouvat dalsi fyziologii modelu z Python prototypu do Modelicy.

Tento projekt neni zdravotnicka pomucka a neslouzi k rozhodovani o lecbe.
