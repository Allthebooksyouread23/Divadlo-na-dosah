# Divadlo na dosah - maturitní projekt
Jan Dašek  2026
![alt text|775](<l.jpg>)
## 1. Stručný popis projektu
Divadlo na dosah je stolní informační panel postavený na Raspberry Pi a e-paper displeji. Aplikace průběžně zobrazuje zajímavý divadelní program pražských divadel, umožňuje výběr režimu přes rotační enkodér a v pravidelných intervalech automaticky aktualizuje data ze serveru i-divadlo.cz.
Projekt je rozdělen do tří hlavních částí:
- sběr dat (web scraping + databáze),
- ovládání a vykreslování na e-paper displej,
- automatizovaný provoz (cron, service, skripty).
![alt text|775](<c.png>)
## 2. Základní funkční principy
## 2.1 Tok dat
1. Skript scraperu stáhne programy z webu i-divadlo.cz.
2. Data uloží do SQLite databáze `theatre.db`.
3. Zobrazovací aplikace čte data z databáze a kreslí obrazovky.
4. Uživatel ovládá menu a výběr přes rotační enkodér.
5. Cron periodicky spouští scraper a databázi průběžně udržuje aktuální.
## 2.2 Ovládání (enkodér)
Enkodér zapisuje aktuální pozici a stisk tlačítka do dočasných souborů v `/tmp`.
Zobrazovací proces tyto hodnoty čte a podle nich mění režim, stránku nebo výběr položky.
Ukázka (zjednodušeně):
```python
# src/encoder.py
with open("/tmp/counter.txt", "w") as f:
    f.write(str(int(counter)))
with open("/tmp/knob_press.txt", "w") as f:
    f.write(str(time.time_ns()))
```
## 2.3 Režimy zobrazení
Aplikace obsahuje několik režimů:
- `idle`: detail vybraného tipu,
- `by_date`: tipy podle data,
- `by_theatre`: seznam divadel a následně seznam inscenací,
- `menu`: hlavní menu s ikonami.
## 2.4 Automatický návrat do idle
Veškeré informační a výběrové obrazovky mají globální timeout 5 minut neaktivity. Po uplynutí limitu se aplikace vrátí do režimu `idle`.
Ukázka (zjednodušeně):
```python
# src/display.py
screen_inactivity_timeout = 300
if output_mode != 'idle' and not menu_open and (current_time - last_user_activity) >= screen_inactivity_timeout:
    output_mode = 'idle'
    last_render_time = 0
```
## 2.5 Aktualizace dat a cache logika
Scraper pracuje úsporně:
- maže staré záznamy (před dneškem),
- kontroluje, které dny už v databázi jsou,
- stahuje jen chybějící data pro další období.
Ukázka principu:
```python
# src/scraper.py
for day in range(FETCH_DAYS):
    date_str = (start_date + timedelta(days=day)).strftime(DATE_FMT)
    cursor.execute('SELECT COUNT(*) FROM inscenations WHERE date = ?', (date_str,))
    if cursor.fetchone()[0] == 0:
        dates_needed.append(date_str)
```
## 2.6 Pravidelné spouštění
Pro periodické spouštění scraperu je připraven shell skript, který nastaví cron úlohu (neděle 13:00).
Ukázka cron záznamu:
```bash
0 13 * * 0 cd /cesta/k/divadlo-infotable && python3 src/scraper.py >> /var/log/theatre_scraper.log 2>&1
```
## 3. Použité technologie a knihovny
## 3.1 Jazyk a platforma
- Python 3
- Raspberry Pi OS / Linux
- SQLite databáze
## 3.2 Python knihovny v projektu
- `waveshare_epd` (ovladač e-paper displeje)
- `Pillow` (render textu, bitmap, ikon)
- `requests` (HTTP komunikace)
- `beautifulsoup4` (parsování HTML)
- `RPi.GPIO` (práce s GPIO piny)
- `sqlite3` (standardní knihovna Pythonu)
- `datetime`, `time`, `os`, `logging` (standardní knihovna)
## 3.3 Externí služby
- i-divadlo.cz (zdroj dat o inscenacích)
- OpenWeatherMap API (počasí do status baru)
## 4. Odkazy na dokumentaci
## 4.1 Hardware a display
- Waveshare 7.5 inch e-Paper HAT: https://www.waveshare.com/wiki/7.5inch_e-Paper_HAT_Manual#Overview
## 4.2 Python knihovny
- Pillow: https://pillow.readthedocs.io/
- Pillow ImageDraw: https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html
- BeautifulSoup: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- Requests: https://requests.readthedocs.io/en/latest/
- RPi.GPIO: https://sourceforge.net/p/raspberry-gpio-python/wiki/Home/
- SQLite3 (Python): https://docs.python.org/3/library/sqlite3.html
## 4.3 Služby a provoz
- OpenWeatherMap API: https://openweathermap.org/api
- Cron (crontab): https://man7.org/linux/man-pages/man5/crontab.5.html
- systemd: https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html
## 5. Podrobný popis Python souborů
### src/display.py
Tento soubor je hlavním řídicím bodem celé aplikace. Zajišťuje inicializaci e-paper displeje, připojení k databázi, čtení hodnot z rotačního enkodéru a rozhodování o tom, která obrazovka se má právě zobrazit. V jedné nekonečné smyčce sleduje změny v souborech v `/tmp`, podle nich přepíná režimy `idle`, `by_date`, `by_theatre` a menu, a zároveň hlídá uspání displeje při neaktivitě. Bez tohoto souboru by se celý projekt neřídil, protože právě zde se spojuje hardware, databáze i vykreslovací část.
### src/draw_modes.py
Soubor `draw_modes.py` obsahuje všechny funkce, které vytvářejí výsledný obraz pro e-paper displej. Nejde jen o jednoduché kreslení textu, ale také o řešení rozvržení, stránkování, zvýrazňování vybraných položek, práci s ikonami a doplňkové zobrazení počasí ve stavovém řádku. Tento modul je důležitý proto, že odděluje vizuální logiku od řízení programu: `display.py` jen předá data a `draw_modes.py` z nich vytvoří konkrétní obrazovku.
### src/encoder.py
Tento soubor obsluhuje rotační enkodér připojený na GPIO piny Raspberry Pi. Sleduje změny na signálech CLK a DT, pozná směr otáčení a reaguje i na stisk tlačítka. Namísto přímé komunikace s ostatními částmi programu zapisuje stav do dočasných souborů v `/tmp`, které následně čte `display.py`. Díky tomu je obsluha enkodéru jednoduchá, spolehlivá a zároveň běží odděleně od vykreslování na displej.
### src/scraper.py
Soubor `scraper.py` zajišťuje pravidelný sběr dat z webu i-divadlo.cz a jejich ukládání do databáze `theatre.db`. Nejprve připraví databázovou strukturu, poté odstraní staré záznamy a následně zkontroluje, které dny v plánovaném období ještě v databázi chybí. Jen tato chybějící data stáhne z webu, naparsuje a uloží jako inscenace. Tím se výrazně snižuje množství zbytečných požadavků a celý proces je vhodný i pro úsporný provoz na Raspberry Pi.
### src/inscenation_info_scraper.py
Tento modul slouží pro detailní načítání informací o jedné konkrétní inscenaci. Z cílové stránky dokáže získat autora, premiéru, tvůrce, herce, popis, délku představení, seznam termínů, logo divadla i hodnocení. V aplikaci se používá hlavně ve chvíli, kdy uživatel otevře detail představení a chce vidět více informací než jen základní záznam z databáze. Díky samostatnému modulu je tento typ scrapingu oddělený od hlavního scraperu a dá se snadněji upravit, pokud se změní HTML struktura webu.
### src/db_inspector.py
Soubor `db_inspector.py` je pomocný servisní nástroj pro kontrolu databáze. Slouží zejména při vývoji a ladění, protože umožňuje rychle zjistit počet záznamů, rozsah dat, počet tipů, počet divadel nebo velikost databázového souboru. Není to součást běžného chodu aplikace, ale velmi užitečný nástroj pro ověření, že scraper zapisuje data správně a že databáze odpovídá očekávání.
## 6. Struktura projektu (výběr)
- `src/display.py` - hlavní smyčka aplikace, vykreslování režimů, timeouty.
- `src/draw_modes.py` - vykreslovací funkce jednotlivých obrazovek.
- `src/encoder.py` - čtení rotačního enkodéru a tlačítka.
- `src/scraper.py` - sběr dat a aktualizace databáze.
- `src/inscenation_info_scraper.py` - detailní scraping stránky jedné inscenace.
- `setup_weekly_scraper.sh` - nastavení cron úlohy pro periodický scraping.
- `SCRAPER_SETUP.md` - provozní poznámky ke scraperu.
## 7. Spuštění projektu
## 7.1 Lokální spuštění aplikace 
```bash
./start_all.sh
```
## 7.1.1 Schození aplikace 
```bash
    sudo systemctl stop infoboard.service
```
## 7.2 Ruční aktualizace databáze
```bash
python3 src/scraper.py
```
## 7.3 Nastavení automatického týdenního běhu scraperu
```bash
bash setup_weekly_scraper.sh
```
## 8. Možná budoucí rozšíření
- Export vybraných dat (např. CSV/JSON).
- Jednoduché webové rozhraní pro vzdálenou správu.
- Začlenění funkce google kalendáře (přidávání inscenací, zobrazování kalendáře)
