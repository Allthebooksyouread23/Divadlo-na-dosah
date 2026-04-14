import re
from bs4 import BeautifulSoup
import requests

class InscenationInfo:
    def __init__(self, author, premiere, creators, actors, description, duration, dates, logo_url=None, editor_rating=None, user_rating=None):
        self.author = author
        self.premiere = premiere
        self.creators = creators  # seznam řetězců
        self.actors = actors  # řetězec nebo seznam
        self.description = description
        self.duration = duration
        self.dates = dates  # seznam termínů představení (datum/čas)
        self.logo_url = logo_url  # URL loga divadla
        self.editor_rating = editor_rating  # hodnocení redakce, např. "73 %"
        self.user_rating = user_rating  # hodnocení uživatelů, např. "81 %"

    def __repr__(self):
        desc = self.description if self.description is not None else ''
        if len(desc) > 120:
            desc = desc[:117] + '...'
        return f"InscenationInfo(author={self.author}, premiere={self.premiere}, creators={self.creators}, actors={self.actors}, description={desc}, duration={self.duration}, dates={self.dates}, logo_url={self.logo_url}, editor_rating={self.editor_rating}, user_rating={self.user_rating})"

def scrape_inscenation_info(url):
    """
    Scrape information about a single inscenation from the provided URL.
    """
    response = requests.get(url)
    response.raise_for_status()  # Vyhodí chybu pro neúspěšné HTTP kódy.
    soup = BeautifulSoup(response.text, 'html.parser')

    # Autor
    author_elem = soup.find('h2', {'itemprop': 'author', 'class': 'hra_autori'})
    author = author_elem.get_text(strip=True) if author_elem else None

    # Datum premiéry
    premiere_elem = soup.find('div', class_='hra_tvurci', string=lambda text: text and 'Premiéra:' in text)
    premiere = None
    if premiere_elem:
        premiere_text = premiere_elem.get_text(strip=True)
        premiere = premiere_text.replace('Premiéra:', '').strip()

    # Tvůrci (ostatní prvky hra_tvurci)
    creators_elems = soup.find_all('div', class_='hra_tvurci')
    creators = []
    for elem in creators_elems:
        text = elem.get_text(strip=True)
        if 'Premiéra:' not in text:
            creators.append(text)

    # Herci
    actors_elem = soup.find('div', class_='hra_herci')
    actors = actors_elem.get_text(strip=True) if actors_elem else None

    # Popis
    desc_elem = soup.find('div', {'itemprop': 'description', 'class': 'hra_popis'})
    description = desc_elem.get_text(strip=True) if desc_elem else None

    # Délka představení
    duration = None
    duration_icon = soup.find('i', {'class': 'fas fa-clock', 'title': 'orientační délka představení'})
    if duration_icon:
        # Délka bývá v rodičovském elementu nebo sourozenci.
        parent = duration_icon.parent
        if parent:
            text = parent.get_text(strip=True)
            # Odstraní prefix "D:".
            duration = text.replace('D:', '').strip()

    # Termíny představení z řádků programu
    dates = []
    seen_dates = set()
    program_rows = soup.find_all('tr', class_=['hra_program_sudy', 'hra_program_lichy'])
    for row in program_rows:
        date_elem = row.find('big') or row.select_one('td > b')
        time_elem = row.select_one('td[width="20px"] i')
        date_text = date_elem.get_text(strip=True) if date_elem else None
        time_text = time_elem.get_text(strip=True) if time_elem else None

        if not time_text:
            # Mobilní layout mívá čas jako prostý text ve třetí buňce.
            tds = [td for td in row.find_all('td') if td.get_text(strip=True)]
            if len(tds) >= 3:
                possible_time = tds[2].get_text(strip=True)
                if re.match(r'^\d{1,2}:\d{2}$', possible_time):
                    time_text = possible_time

        if date_text and time_text:
            date_time = f"{date_text} {time_text}"
            if date_time not in seen_dates:
                dates.append(date_time)
                seen_dates.add(date_time)

    # URL loga divadla
    logo_url = None
    logo_div = soup.find('div', class_='logo_div')
    if logo_div:
        img = logo_div.find('img')
        if img and img.get('src'):
            src = img['src']
            if src.startswith('/'):
                logo_url = f"https://www.i-divadlo.cz{src}"
            else:
                logo_url = src

    # Hodnocení (redakce a uživatelé)
    editor_rating = None
    user_rating = None
    rating_div = soup.find('div', class_='hra_hodnoc_prum')
    if rating_div:
        rating_columns = rating_div.find_all('div', class_='hra_hodnoc_prum_sloupec')
        for col in rating_columns:
            # get_text(strip=True) slepí popisek a hodnotu (např. "Redakce73 %").
            # Proto vezmeme stripped strings a první token použijeme jako popisek.
            parts = list(col.stripped_strings)
            label = parts[0] if parts else ''
            label_norm = label.lower().strip(':')
            rating_elem = col.find('div', class_='hra_hodnoc_prum_cislo')
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                if label_norm == 'redakce':
                    editor_rating = rating_text
                elif label_norm == 'uživatelé':
                    user_rating = rating_text

    return InscenationInfo(author, premiere, creators, actors, description, duration, dates, logo_url, editor_rating, user_rating)