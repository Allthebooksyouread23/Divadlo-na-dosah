from bs4 import BeautifulSoup
import requests
import sqlite3
from datetime import datetime, timedelta
import os
import logging

# Nastavení logování
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cesta ke skriptu a databázi
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'theatre.db')
DATE_FMT = '%d.%m.%Y'
FETCH_DAYS = 30


class Inscenation:
    def __init__(self, name, theatre, starting_time, date, tip=False, stars=0):
        self.date = date
        self.name = name
        self.theatre = theatre
        self.starting_time = starting_time
        self.tip = tip
        self.stars = stars
    
    def __repr__(self):
        tip_str = ", Tip: True" if self.tip else ""
        stars_str = f", Stars: {self.stars}" if self.stars > 0 else ""
        return f"Inscenace - Jméno: {self.name}, Divadlo: {self.theatre}, Čas: {self.starting_time}, Datum: {self.date}{tip_str}{stars_str}"


def init_database():
    """Initialize database schema if it doesn't exist"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inscenations (
            id INTEGER PRIMARY KEY,
            name TEXT,
            theatre TEXT,
            starting_time TEXT,
            date TEXT,
            tip INTEGER,
            stars INTEGER,
            url TEXT
        )
    ''')
    
    # Přidá sloupec url, pokud v tabulce ještě není.
    cursor.execute('PRAGMA table_info(inscenations)')
    existing_columns = [row[1] for row in cursor.fetchall()]
    if 'url' not in existing_columns:
        cursor.execute('ALTER TABLE inscenations ADD COLUMN url TEXT')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")


def clean_old_data():
    """Delete all performances before today"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    today = datetime.today().strftime(DATE_FMT)
    cursor.execute('DELETE FROM inscenations WHERE date < ?', (today,))
    deleted_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} old performances before {today}")
    return deleted_count


def get_dates_to_fetch():
    """Get list of dates that need to be fetched (next 30 days from today)"""
    start_date = datetime.today()
    dates_needed = []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    for day in range(FETCH_DAYS):
        current_date = start_date + timedelta(days=day)
        date_str = current_date.strftime(DATE_FMT)
        
        # Kontrola, zda už data pro daný den máme.
        cursor.execute('SELECT COUNT(*) FROM inscenations WHERE date = ?', (date_str,))
        count = cursor.fetchone()[0]
        
        if count == 0:
            dates_needed.append(date_str)
    
    conn.close()
    
    if dates_needed:
        logger.info(f"Need to fetch data for {len(dates_needed)} dates")
    else:
        logger.info("Database already contains data for next 30 days")
    
    return dates_needed

def fetch_and_update_data(dates_to_fetch):
    """Fetch performance data from internet and insert into database"""
    if not dates_to_fetch:
        logger.info("No dates to fetch")
        return 0
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    performances_dict = {}
    
    for date_str in dates_to_fetch:
        try:
            url = f"https://www.i-divadlo.cz/programovy-kalendar/?datum={date_str}"
            logger.info(f"Fetching data for {date_str}")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Najde sekci pro Prahu.
            prague_section = soup.find('div', attrs={'id': 'obsah1'})
            if not prague_section:
                logger.warning(f"No Prague section found for {date_str}")
                continue
            
            # Načte všechny řádky představení.
            rows = prague_section.find_all('tr', attrs={'class': ['div_program_lichy', 'div_program_sudy']})
            
            for row in rows:
                # Název představení.
                play_link = row.select_one('td[width="37%"] b a')
                if play_link is None:
                    continue
                name = play_link.get_text(strip=True)
                relative_url = play_link.get('href', '').strip()
                if relative_url.startswith('/'):
                    perf_url = f"https://www.i-divadlo.cz{relative_url}"
                else:
                    perf_url = relative_url
                
                # Tip a počet medailí.
                tip_link = row.select_one('td[width="37%"] a[href*="/nas-tip/"]')
                tip = bool(tip_link)
                stars = len(row.select('td[width="37%"] img[src*="medal"]'))
                
                # Název divadla.
                theatre_element = row.select_one('td[width="38%"] a')
                if theatre_element:
                    small_tag = theatre_element.find('small')
                    if small_tag:
                        small_tag.decompose()
                    theatre = theatre_element.get_text(strip=True)
                else:
                    theatre = "Unknown"
                
                # Čas představení.
                time_element = row.select_one('td[width="7%"]')
                starting_time = time_element.get_text(strip=True) if time_element else "Unknown"
                
                # Slučuje stejné představení v rámci dne a času.
                key = (name, date_str, starting_time)
                if key in performances_dict:
                    performances_dict[key]['theatre'] += " / " + theatre
                    performances_dict[key]['tip'] = performances_dict[key]['tip'] or tip
                    performances_dict[key]['stars'] = max(performances_dict[key]['stars'], stars)
                else:
                    performances_dict[key] = {
                        'name': name,
                        'theatre': theatre,
                        'starting_time': starting_time,
                        'date': date_str,
                        'tip': tip,
                        'stars': stars,
                        'url': perf_url
                    }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {date_str}: {e}")
            continue
    
    # Zápis do databáze.
    for perf in performances_dict.values():
        cursor.execute('INSERT INTO inscenations (name, theatre, starting_time, date, tip, stars, url) VALUES (?, ?, ?, ?, ?, ?, ?)',
                      (perf['name'], perf['theatre'], perf['starting_time'], perf['date'], 
                       int(perf['tip']), perf['stars'], perf.get('url', '')))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Inserted {len(performances_dict)} unique performances into database")
    return len(performances_dict)


def print_tips():
    """Print all performances with tips"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT name, theatre, starting_time, date, tip, stars FROM inscenations WHERE tip = 1 ORDER BY date, starting_time')
    results = cursor.fetchall()
    
    if not results:
        logger.info("No performances with tips found")
        conn.close()
        return
    
    print("\n=== Performances with Tips ===\n")
    current_date = None
    
    for row in results:
        name, theatre, starting_time, date, tip, stars = row
        
        if current_date is not None and current_date != date:
            print()
        
        inscenation = Inscenation(name, theatre, starting_time, date, bool(tip), stars)
        print(inscenation)
        
        current_date = date
    
    conn.close()


def main():
    """Main orchestration function"""
    logger.info("=== Starting Theatre Scraper ===")
    
    # Inicializace databáze.
    init_database()
    
    # Smazání starých záznamů.
    clean_old_data()
    
    # Získá dny, které je potřeba stáhnout.
    dates_to_fetch = get_dates_to_fetch()
    
    # Stažení a aktualizace dat.
    if dates_to_fetch:
        inserted = fetch_and_update_data(dates_to_fetch)
        logger.info(f"Database update complete. Inserted {inserted} performances")
    else:
        logger.info("Database is up to date")
    
    # Výpis tipů do konzole.
    print_tips()
    
    logger.info("=== Scraper Finished ===\n")


if __name__ == '__main__':
    main()
