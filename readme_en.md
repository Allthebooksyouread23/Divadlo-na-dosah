# Divadlo na dosah - graduation project
Jan Dašek 2026

![alt text|775](<l.png>)

## 1. Short project description

Divadlo na dosah is a desktop information panel built on a Raspberry Pi and an e-paper display. The application continuously shows theatre program data, allows mode selection through a rotary encoder, and automatically refreshes the data from the i-divadlo.cz server at regular intervals.

The project is divided into three main parts:
- data collection (web scraping + database),
- display control and rendering on the e-paper display,
- automated operation (cron, service, scripts).

![alt text|775](<c.png>)

## 2. Basic functional principles

## 2.1 Data flow

1. The scraper downloads program data from the i-divadlo.cz website.
2. The data is stored in the SQLite database `theatre.db`.
3. The display application reads data from the database and renders screens.
4. The user controls the menu and selection with a rotary encoder.
5. Cron periodically runs the scraper and keeps the database up to date.

## 2.2 Control (encoder)

The encoder writes the current position and button press state to temporary files in `/tmp`.
The display process reads these values and uses them to change the mode, page, or selected item.

Example (simplified):
```python
# src/encoder.py
with open("/tmp/counter.txt", "w") as f:
    f.write(str(int(counter)))
with open("/tmp/knob_press.txt", "w") as f:
    f.write(str(time.time_ns()))
```

## 2.3 Display modes

The application contains several modes:
- `idle`: detail of the selected tip,
- `by_date`: tips by date,
- `by_theatre`: list of theatres and then list of performances,
- `menu`: main menu with icons.

## 2.4 Automatic return to idle

All information and selection screens have a global inactivity timeout of 5 minutes. After the limit expires, the application returns to `idle` mode.

Example (simplified):
```python
# src/display.py
screen_inactivity_timeout = 300
if output_mode != 'idle' and not menu_open and (current_time - last_user_activity) >= screen_inactivity_timeout:
    output_mode = 'idle'
    last_render_time = 0
```

## 2.5 Data updates and cache logic

The scraper works efficiently:
- it deletes old records (before today),
- it checks which dates are already present in the database,
- it downloads only the missing data for the upcoming period.

Example principle:
```python
# src/scraper.py
for day in range(FETCH_DAYS):
    date_str = (start_date + timedelta(days=day)).strftime(DATE_FMT)
    cursor.execute('SELECT COUNT(*) FROM inscenations WHERE date = ?', (date_str,))
    if cursor.fetchone()[0] == 0:
        dates_needed.append(date_str)
```

## 2.6 Periodic execution

For periodic scraper execution, a shell script is prepared that sets up a cron task (Sunday 13:00).

Example cron entry:
```bash
0 13 * * 0 cd /path/to/divadlo-infotable && python3 src/scraper.py >> /var/log/theatre_scraper.log 2>&1
```

## 3. Technologies and libraries used

## 3.1 Language and platform
- Python 3
- Raspberry Pi OS / Linux
- SQLite database

## 3.2 Python libraries in the project
- `waveshare_epd` (e-paper display driver)
- `Pillow` (rendering text, bitmaps, icons)
- `requests` (HTTP communication)
- `beautifulsoup4` (HTML parsing)
- `RPi.GPIO` (working with GPIO pins)
- `sqlite3` (Python standard library)
- `datetime`, `time`, `os`, `logging` (Python standard library)

## 3.3 External services
- i-divadlo.cz (source of performance data)
- OpenWeatherMap API (weather in the status bar)

## 4. Documentation links

## 4.1 Hardware and display
- Waveshare 7.5 inch e-Paper HAT: https://www.waveshare.com/wiki/7.5inch_e-Paper_HAT_Manual#Overview

## 4.2 Python libraries
- Pillow: https://pillow.readthedocs.io/
- Pillow ImageDraw: https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html
- BeautifulSoup: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- Requests: https://requests.readthedocs.io/en/latest/
- RPi.GPIO: https://sourceforge.net/p/raspberry-gpio-python/wiki/Home/
- SQLite3 (Python): https://docs.python.org/3/library/sqlite3.html

## 4.3 Services and operation
- OpenWeatherMap API: https://openweathermap.org/api
- Cron (crontab): https://man7.org/linux/man-pages/man5/crontab.5.html
- systemd: https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html

## 5. Detailed description of Python files

### src/display.py
This file is the main control point of the whole application. It handles initialization of the e-paper display, connection to the database, reading values from the rotary encoder, and deciding which screen should currently be shown. In a single endless loop it watches for changes in the files in `/tmp`, switches between the `idle`, `by_date`, `by_theatre`, and menu modes, and also handles putting the display to sleep when inactive. Without this file, the whole project would not be controlled, because it connects the hardware, database, and rendering part.

### src/draw_modes.py
The `draw_modes.py` file contains all functions that create the final image for the e-paper display. It is not just simple text drawing, but also layout handling, paging, highlighting selected items, working with icons, and additional weather display in the status bar. This module is important because it separates visual logic from program control: `display.py` only passes data and `draw_modes.py` turns it into a concrete screen.

### src/encoder.py
This file handles the rotary encoder connected to the GPIO pins of the Raspberry Pi. It watches changes on the CLK and DT signals, detects the direction of rotation, and also reacts to button presses. Instead of communicating directly with the rest of the program, it writes its state to temporary files in `/tmp`, which are then read by `display.py`. Thanks to this, encoder handling is simple, reliable, and runs separately from display rendering.

### src/scraper.py
The `scraper.py` file handles regular data collection from the i-divadlo.cz website and stores it in the `theatre.db` database. It first prepares the database structure, then removes old records, and then checks which days in the planned period are still missing in the database. It downloads only the missing data from the website, parses it, and stores it as performances. This significantly reduces the number of unnecessary requests and makes the process suitable even for energy-efficient operation on a Raspberry Pi.

### src/inscenation_info_scraper.py
This module is used for detailed loading of information about one specific performance. From the target page it can obtain the author, premiere, creators, actors, description, performance length, list of dates, theatre logo, and rating. In the application it is mainly used when the user opens a performance detail and wants to see more information than just the basic database record. Because it is a separate module, this type of scraping is isolated from the main scraper and can be adjusted more easily if the HTML structure of the website changes.

### src/db_inspector.py
The `db_inspector.py` file is a helper maintenance tool for database inspection. It is mainly useful during development and debugging because it can quickly show the number of records, date range, number of tips, number of theatres, or the size of the database file. It is not part of the normal application flow, but it is a very useful tool for verifying that the scraper writes data correctly and that the database matches expectations.

## 6. Project structure (selection)
- `src/display.py` - main application loop, rendering modes, timeouts.
- `src/draw_modes.py` - rendering functions for individual screens.
- `src/encoder.py` - reading the rotary encoder and button.
- `src/scraper.py` - data collection and database updates.
- `src/inscenation_info_scraper.py` - detailed scraping of one performance page.
- `setup_weekly_scraper.sh` - cron task setup for periodic scraping.
- `SCRAPER_SETUP.md` - operational notes for the scraper.

## 7. Running the project

## 7.1 Running the application locally
```bash
./start_all.sh
```

## 7.1.1 Stopping the application
```bash
sudo systemctl stop infoboard.service
```

## 7.2 Manual database update
```bash
python3 src/scraper.py
```

## 7.3 Setting up automatic weekly scraper execution
```bash
bash setup_weekly_scraper.sh
```

## 8. Possible future extensions
- Export selected data (for example CSV/JSON).
- Simple web interface for remote management.
- Integration of Google Calendar functionality (adding performances, displaying the calendar).