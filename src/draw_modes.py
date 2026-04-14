from PIL import Image, ImageDraw, ImageFont
import logging
import datetime
import requests
import os
import random
from io import BytesIO
from inscenation_info_scraper import scrape_inscenation_info

HEADER_HEIGHT = 30

# Cache dat počasí
last_weather_time = None
cached_weather = {}

# Cache náhodného pořadí divadel, aby stránkování mezi překresleními neskákalo.
_theatre_order_signature = None
_theatre_order_cache = []
_menu_icon_cache = {}


def _convert_weather_icon(icon_img, size=(30, 30)):
    if icon_img.mode in ('RGBA', 'LA', 'P'):
        icon_img = icon_img.convert('RGBA')
        bg = Image.new('RGBA', icon_img.size, (255, 255, 255, 255))
        icon_img = Image.alpha_composite(bg, icon_img)

    icon_img = icon_img.convert('RGB').resize(size, Image.LANCZOS)
    pixels = []
    for r, g, b in icon_img.getdata():
        pixels.append(0 if (r < 245 or g < 245 or b < 245) else 255)

    mono = Image.new('1', icon_img.size)
    mono.putdata(pixels)
    return mono


def _load_menu_icon(icon_name, size=(76, 76)):
    """Load and cache monochrome menu icons from pic/icons."""
    key = (icon_name, size)
    if key in _menu_icon_cache:
        return _menu_icon_cache[key]

    icon_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pic', 'icons')
    icon_path = os.path.join(icon_dir, icon_name)
    try:
        icon = Image.open(icon_path)
        if icon.mode in ('RGBA', 'LA', 'P'):
            icon = icon.convert('RGBA')
            bg = Image.new('RGBA', icon.size, (255, 255, 255, 255))
            icon = Image.alpha_composite(bg, icon)

        icon = icon.convert('L').resize(size, Image.LANCZOS)
        mono = icon.point(lambda p: 0 if p < 170 else 255, mode='1')
        _menu_icon_cache[key] = mono
        return mono
    except Exception:
        logging.exception('Failed to load menu icon: %s', icon_path)
        _menu_icon_cache[key] = None
        return None


def _menu_title_font(base_font, size=36):
    """Try to build a larger font from the active base font path."""
    try:
        font_path = getattr(base_font, 'path', None)
        if font_path:
            return ImageFont.truetype(font_path, size)
    except Exception:
        pass
    return base_font

def draw_status_bar(image, font, output_mode):
    """Draw a persistent status bar at the top-left corner with weather info."""
    global last_weather_time, cached_weather
    
    # Načtení počasí přes API 2.5 (free tier)
    now = datetime.datetime.now()
    if last_weather_time is None or (now - last_weather_time).total_seconds() > 1800:  # 30 minut
        api_key = "297cd6a25f06ffc34a2540053e57a964"  # Nahraď vlastním API klíčem.
        location = "Prague,CZ"
        url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=metric"
        temp = "N/A"
        weather_desc = "N/A"
        icon_code = None
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                temp = f"{data['main']['temp']:.1f}"
                weather_desc = data['weather'][0]['description'].capitalize()
                icon_code = data['weather'][0]['icon']
            else:
                logging.warning(f"Weather API error: {response.status_code} - {response.text}")
                temp = "API Error"
                weather_desc = "Check Key"
                icon_code = None
        except Exception as e:
            logging.warning(f"Failed to fetch weather: {e}")
            temp = "N/A"
            weather_desc = "N/A"
            icon_code = None
        cached_weather = {'temp': temp, 'weather_desc': weather_desc, 'icon_code': icon_code}
        last_weather_time = now
    else:
        temp = cached_weather.get('temp', 'N/A')
        weather_desc = cached_weather.get('weather_desc', 'N/A')
        icon_code = cached_weather.get('icon_code', None)

    # Ikona počasí: nejdřív lokální cache, pak stažení a uložení.
    icon_img = None
    if icon_code:
        pic_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pic')
        weather_dir = os.path.join(pic_dir, 'weather')
        os.makedirs(weather_dir, exist_ok=True)
        icon_path = os.path.join(weather_dir, f"{icon_code}.png")
        try:
            icon_img = Image.open(icon_path)
            icon_img = _convert_weather_icon(icon_img, size=(30, 30))
        except Exception:
            try:
                # Záloha na oficiální OpenWeatherMap ikony.
                url = f"http://openweathermap.org/img/wn/{icon_code}@2x.png"
                response = requests.get(url, timeout=5)
                # Uložení originální ikony do lokální cache.
                with open(icon_path, 'wb') as f:
                    f.write(response.content)
                icon_img = Image.open(BytesIO(response.content))
                icon_img = _convert_weather_icon(icon_img, size=(30, 30))
            except Exception as e:
                logging.warning(f"Failed to load weather icon {icon_code}: {e}")

    draw = ImageDraw.Draw(image)
    prefix = f"{datetime.datetime.now():%d.%m.%Y %H:%M} | Mode: {output_mode} | "
    temp_part = f"{temp}°C    "
    desc_part = weather_desc
    status_text = prefix + temp_part + desc_part
    try:
        bbox = draw.textbbox((0, 0), status_text, font=font)
        text_h = bbox[3] - bbox[1]
        prefix_temp_bbox = draw.textbbox((0, 0), prefix + temp_part, font=font)
        prefix_temp_w = prefix_temp_bbox[2] - prefix_temp_bbox[0]
    except Exception:
        _, text_h = font.getsize(status_text)
        prefix_temp_w = font.getsize(prefix + temp_part)[0]
    bar_height = HEADER_HEIGHT
    draw.rectangle((0, 0, image.width, bar_height), fill=255)
    text_y = max((bar_height - text_h) // 2, 0)
    draw.text((4, text_y), status_text, font=font, fill=0)
    # Vložení ikony, pokud je dostupná.
    if icon_img:
        icon_x = 4 + prefix_temp_w - 30  # Zarovnání ikony přes rezervovanou mezeru (cca 30 px).
        icon_y = max((bar_height - icon_img.height) // 2, 0)
        image.paste(icon_img, (icon_x, icon_y))
    draw.line((0, bar_height, image.width, bar_height), fill=0)
    return bar_height


def draw_mode_menu(epd, font, selected_index=0):
    """Draw a simple center menu with three mode options."""
    image = Image.new('1', (epd.width, epd.height), 255)
    draw = ImageDraw.Draw(image)

    options = [
        ("Dle data", "by date.jpg"),
        ("Dle divadla", "by theatre.jpg"),
        ("Idle", "idle icon.png"),
    ]

    title_font = _menu_title_font(font, size=44)
    subtitle_font = _menu_title_font(font, size=24)

    title = "Divadlo na dosah"
    subtitle = "Jan Dašek 2026"
    try:
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_w = title_bbox[2] - title_bbox[0]
        title_h = title_bbox[3] - title_bbox[1]
        subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
        subtitle_w = subtitle_bbox[2] - subtitle_bbox[0]
        subtitle_h = subtitle_bbox[3] - subtitle_bbox[1]
    except Exception:
        title_w, title_h = title_font.getsize(title)
        subtitle_w, subtitle_h = subtitle_font.getsize(subtitle)

    title_x = (epd.width - title_w) // 2
    title_y = HEADER_HEIGHT + 12
    subtitle_x = (epd.width - subtitle_w) // 2
    subtitle_y = title_y + title_h + 6

    draw.text((title_x, title_y), title, font=title_font, fill=0)
    draw.text((subtitle_x, subtitle_y), subtitle, font=subtitle_font, fill=0)

    title_block_bottom = subtitle_y + subtitle_h + 12
    draw.line((40, title_block_bottom, epd.width - 40, title_block_bottom), fill=0)

    box_w = 220
    box_h = 200
    gap = 18
    total_w = (box_w * 3) + (gap * 2)
    start_x = max((epd.width - total_w) // 2, 8)
    box_y = max(title_block_bottom + 14, HEADER_HEIGHT + 82)

    for i, (label, icon_name) in enumerate(options):
        x0 = start_x + i * (box_w + gap)
        y0 = box_y
        x1 = x0 + box_w
        y1 = y0 + box_h

        if i == selected_index:
            draw.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=255, outline=0, width=4)
            draw.rounded_rectangle((x0 + 8, y0 + 8, x1 - 8, y1 - 8), radius=14, fill=255, outline=0, width=1)
            draw.rectangle((x0 + 10, y1 - 52, x1 - 10, y1 - 12), fill=0, outline=0)
            text_fill = 255
        else:
            draw.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=255, outline=0, width=2)
            draw.rounded_rectangle((x0 + 8, y0 + 8, x1 - 8, y1 - 8), radius=14, fill=255, outline=0, width=1)
            text_fill = 0

        icon = _load_menu_icon(icon_name, size=(78, 78))
        if icon:
            icon_x = x0 + (box_w - icon.width) // 2
            icon_y = y0 + 26
            image.paste(icon, (icon_x, icon_y))

        try:
            bbox = draw.textbbox((0, 0), label, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except Exception:
            text_w, text_h = font.getsize(label)

        text_x = x0 + (box_w - text_w) // 2
        text_y = y1 - 42
        draw.text((text_x, text_y), label, font=font, fill=text_fill)

    hint = "Knob: move | Press: select"
    draw.text((10, epd.height - 24), hint, font=font, fill=0)
    return image


def _theatre_rows_per_page(epd, font, selectable=False):
    tmp = Image.new('1', (epd.width, epd.height), 255)
    draw = ImageDraw.Draw(tmp)
    try:
        bbox = draw.textbbox((0, 0), '0', font=font)
        char_h = bbox[3] - bbox[1]
    except Exception:
        try:
            _, char_h = font.getsize('0')
        except Exception:
            char_h = font.getmask('0').size[1]

    row_h = char_h + 6
    top = HEADER_HEIGHT + 28
    if selectable:
        top += (2 * row_h)
    bottom = epd.height - 28
    return max(1, (bottom - top) // row_h)


def draw_by_theatre(epd, theatres, page_index, total_pages, font, font1=None, selected_index=None, selectable=False):
    """Render the 'by theatre' view and return a PIL Image."""
    image = Image.new('1', (epd.width, epd.height), 255)
    draw = ImageDraw.Draw(image)

    try:
        bbox = draw.textbbox((0, 0), '0', font=font)
        char_h = bbox[3] - bbox[1]
    except Exception:
        try:
            _, char_h = font.getsize('0')
        except Exception:
            char_h = font.getmask('0').size[1]
    row_h = char_h + 6

    header_y = HEADER_HEIGHT + 6
    draw.text((10, header_y), "Theatre", font=font, fill=0)
    page_label = f"Page {page_index + 1}/{max(1, total_pages)}"
    draw.text((epd.width - 180, header_y), page_label, font=font, fill=0)

    row_start_y = HEADER_HEIGHT + 28
    if selectable:
        menu_back_y = row_start_y
        if selected_index is not None and selected_index == 0:
            draw.rectangle((4, menu_back_y - 2, epd.width - 5, menu_back_y + row_h - 2), outline=0, width=2)
        draw.text((10, menu_back_y), "<- Zpet do menu", font=font, fill=0)

        back_y = row_start_y + row_h
        if selected_index is not None and selected_index == 1:
            draw.rectangle((4, back_y - 2, epd.width - 5, back_y + row_h - 2), outline=0, width=2)
        draw.text((10, back_y), "<- Zpet", font=font, fill=0)
        row_start_y += (2 * row_h)

    for i, theatre in enumerate(theatres):
        y = row_start_y + (i * row_h)
        if selectable and selected_index is not None and i == (selected_index - 2):
            draw.rectangle((4, y - 2, epd.width - 5, y + row_h - 2), outline=0, width=2)

        text = theatre
        max_chars = 64
        if len(text) > max_chars:
            text = text[:max_chars - 1] + '…'
        draw.text((10, y), text, font=font, fill=0)

    if selectable:
        footer = "Knob: vybrat položku | Stisk: otevřít"
    else:
        footer = "Knob: stránka | Stisk: režim výběru"
    draw.text((10, epd.height - 24), footer, font=font, fill=0)
    return image


def render_by_theatre(epd, current_value, last_displayed_value, current_page_index, cursor, font, font1=None, selected_index=None, selectable=False):
    """Render by-theatre paginated list and return image/state data."""
    global _theatre_order_signature, _theatre_order_cache

    cursor.execute('''
        SELECT theatre, MAX(COALESCE(tip, 0)) AS has_tip
        FROM inscenations
        WHERE theatre IS NOT NULL AND theatre != ''
        GROUP BY theatre
    ''')
    rows = cursor.fetchall()

    signature = tuple(sorted((row[0], int(row[1] or 0)) for row in rows))
    if signature != _theatre_order_signature:
        tip_theatres = [row[0] for row in rows if int(row[1] or 0) > 0]
        non_tip_theatres = [row[0] for row in rows if int(row[1] or 0) == 0]
        random.shuffle(tip_theatres)
        random.shuffle(non_tip_theatres)
        _theatre_order_cache = tip_theatres + non_tip_theatres
        _theatre_order_signature = signature

    theatres = _theatre_order_cache

    rows_per_page = max(1, _theatre_rows_per_page(epd, font, selectable=False) - 1)
    total_pages = max(1, (len(theatres) + rows_per_page - 1) // rows_per_page)

    if current_page_index is None:
        current_page_index = 0

    try:
        if last_displayed_value is None:
            delta_pages = 0
        elif current_value is None or current_value == '':
            delta_pages = 0
        else:
            delta_pages = int(current_value) - int(last_displayed_value)
    except Exception:
        logging.exception("Failed to compute delta_pages in render_by_theatre")
        delta_pages = 0

    new_page_index = (current_page_index + delta_pages) % total_pages
    start = new_page_index * rows_per_page
    end = start + rows_per_page
    page_theatres = theatres[start:end]

    image = draw_by_theatre(
        epd,
        page_theatres,
        new_page_index,
        total_pages,
        font,
        font1,
        selected_index=selected_index,
        selectable=selectable,
    )
    return image, new_page_index, current_value, page_theatres


def render_theatre_page(epd, theatre_name, font, font1=None):
    """Render placeholder theatre page with theatre name only."""
    image = Image.new('1', (epd.width, epd.height), 255)
    draw = ImageDraw.Draw(image)
    title_font = font1 or font
    draw.text((20, HEADER_HEIGHT + 24), theatre_name, font=title_font, fill=0)
    draw.text((20, HEADER_HEIGHT + 74), "(stránka divadla - připravuje se)", font=font, fill=0)
    draw.text((20, HEADER_HEIGHT + 104), "Stisk: zpět na výběr", font=font, fill=0)
    return image


def _theatre_performance_rows_per_page(epd, font, selectable=False):
    tmp = Image.new('1', (epd.width, epd.height), 255)
    draw = ImageDraw.Draw(tmp)
    try:
        bbox = draw.textbbox((0, 0), '0', font=font)
        char_h = bbox[3] - bbox[1]
    except Exception:
        try:
            _, char_h = font.getsize('0')
        except Exception:
            char_h = font.getmask('0').size[1]

    row_h = char_h + 6
    top = HEADER_HEIGHT + 40
    if selectable:
        top += (2 * row_h)
    bottom = epd.height - 28
    return max(1, (bottom - top) // row_h)


def draw_theatre_page_list(epd, theatre_name, performances, page_index, total_pages, font, font1=None, selected_index=None, selectable=False):
    """Render theatre page with grouped performance names."""
    image = Image.new('1', (epd.width, epd.height), 255)
    draw = ImageDraw.Draw(image)

    try:
        bbox = draw.textbbox((0, 0), '0', font=font)
        char_h = bbox[3] - bbox[1]
    except Exception:
        try:
            _, char_h = font.getsize('0')
        except Exception:
            char_h = font.getmask('0').size[1]
    row_h = char_h + 6

    header_y = HEADER_HEIGHT + 4
    title_font = font1 or font
    title = theatre_name or "(Bez názvu divadla)"
    if len(title) > 26:
        title = title[:25] + '…'
    draw.text((10, header_y), title, font=title_font, fill=0)
    page_label = f"Page {page_index + 1}/{max(1, total_pages)}"
    draw.text((epd.width - 180, header_y), page_label, font=font, fill=0)

    row_start_y = HEADER_HEIGHT + 40
    if selectable:
        menu_back_y = row_start_y
        if selected_index is not None and selected_index == 0:
            draw.rectangle((4, menu_back_y - 2, epd.width - 5, menu_back_y + row_h - 2), outline=0, width=2)
        draw.text((10, menu_back_y), "<- Zpet do menu", font=font, fill=0)

        back_y = row_start_y + row_h
        if selected_index is not None and selected_index == 1:
            draw.rectangle((4, back_y - 2, epd.width - 5, back_y + row_h - 2), outline=0, width=2)
        draw.text((10, back_y), "<- Zpet", font=font, fill=0)
        row_start_y += (2 * row_h)

    for i, perf in enumerate(performances):
        perf_name = perf[1]
        y = row_start_y + (i * row_h)
        if selectable and selected_index is not None and i == (selected_index - 2):
            draw.rectangle((4, y - 2, epd.width - 5, y + row_h - 2), outline=0, width=2)

        text = perf_name
        max_chars = 64
        if len(text) > max_chars:
            text = text[:max_chars - 1] + '…'
        draw.text((10, y), text, font=font, fill=0)

    if selectable:
        footer = "Knob: vybrat položku | Stisk: otevřít detail"
    else:
        footer = "Knob: stránka | Stisk: režim výběru"
    draw.text((10, epd.height - 24), footer, font=font, fill=0)
    return image


def render_theatre_page_list(epd, current_value, last_displayed_value, current_page_index, cursor, theatre_name, font, font1=None, selected_index=None, selectable=False):
    """Render paged theatre page with grouped performance names by theatre."""
    query = '''
        SELECT MIN(id) AS id, name
        FROM inscenations
        WHERE theatre = ? AND name IS NOT NULL AND name != ''
        GROUP BY name
        ORDER BY name
    '''
    cursor.execute(query, (theatre_name,))
    all_rows = cursor.fetchall()

    rows_per_page = max(1, _theatre_performance_rows_per_page(epd, font, selectable=False) - 1)
    total_pages = max(1, (len(all_rows) + rows_per_page - 1) // rows_per_page)

    if current_page_index is None:
        current_page_index = 0

    try:
        if last_displayed_value is None:
            delta_pages = 0
        elif current_value is None or current_value == '':
            delta_pages = 0
        else:
            delta_pages = int(current_value) - int(last_displayed_value)
    except Exception:
        logging.exception("Failed to compute delta_pages in render_theatre_page_list")
        delta_pages = 0

    new_page_index = (current_page_index + delta_pages) % total_pages
    start = new_page_index * rows_per_page
    end = start + rows_per_page
    page_rows = all_rows[start:end]

    image = draw_theatre_page_list(
        epd,
        theatre_name,
        page_rows,
        new_page_index,
        total_pages,
        font,
        font1,
        selected_index=selected_index,
        selectable=selectable,
    )
    return image, new_page_index, current_value, page_rows


def draw_by_date(epd, results, target_date, font, font1=None, selected_index=None, selectable=False):
    """Render the 'by date' view and return a PIL Image.

    - `epd` is used for width/height information.
    - `results` is an iterable of rows: (name, theatre, starting_time, date, tip, stars)
    - `target_date` is a string to display as header.
    - `font` is the primary PIL ImageFont to use.
    """
    Himage = Image.new('1', (epd.width, epd.height), 255)
    draw = ImageDraw.Draw(Himage)

    # Column layout (widths are in characters for monospace font)
    columns = [
        ("name", 30),
        ("theatre", 20),
        ("time", 6),
    ]

    # compute x positions based on character width using textbbox with fallbacks
    try:
        bbox = draw.textbbox((0, 0), '0', font=font)
        char_w = bbox[2] - bbox[0]
        char_h = bbox[3] - bbox[1]
    except Exception:
        try:
            char_w, char_h = font.getsize('0')
        except Exception:
            mask = font.getmask('0')
            char_w, char_h = mask.size

    padding = 8
    x_positions = []
    x = 10
    for _, w in columns:
        x_positions.append(x)
        x += (w * char_w) + padding

    # Draw header row with column titles and the target date
    header_y = HEADER_HEIGHT + 6
    for idx, (colname, w) in enumerate(columns):
        title = colname.capitalize()
        draw.text((x_positions[idx], header_y), title, font=font, fill=0)
    draw.text((x, header_y), target_date, font=font, fill=0)

    # Draw each inscenation in its column
    row_start_y = HEADER_HEIGHT + 28
    row_h = char_h + 6

    if selectable:
        menu_back_y = row_start_y
        if selected_index is not None and selected_index == 0:
            draw.rectangle((4, menu_back_y - 2, epd.width - 5, menu_back_y + row_h - 2), outline=0, width=2)
        draw.text((10, menu_back_y), "<- Zpet do menu", font=font, fill=0)

        back_y = row_start_y + row_h
        if selected_index is not None and selected_index == 1:
            draw.rectangle((4, back_y - 2, epd.width - 5, back_y + row_h - 2), outline=0, width=2)
        draw.text((10, back_y), "<- Zpet", font=font, fill=0)

        row_start_y += row_h
        row_start_y += row_h

    for i, row in enumerate(results):
        _, name, theatre, starting_time, date, tip, stars = row
        vals = {
            'name': name,
            'theatre': theatre,
            'time': starting_time,
        }
        y = row_start_y + (i * row_h)

        if selectable and selected_index is not None and i == (selected_index - 2):
            draw.rectangle((4, y - 2, epd.width - 5, y + row_h - 2), outline=0, width=2)

        for idx, (colname, width_chars) in enumerate(columns):
            text = vals.get(colname, '')
            if len(text) > width_chars:
                text = text[:max(0, width_chars-1)] + '…'
            draw.text((x_positions[idx], y), text, font=font, fill=0)

    if selectable:
        footer = "Knob: vybrat položku | Stisk: otevřít detail"
    else:
        footer = "Stisk: režim výběru položky"
    draw.text((10, epd.height - 24), footer, font=font, fill=0)

    return Himage


def render_by_date(epd, current_value, last_displayed_value, current_displayed_date, cursor, font, font1=None, selected_index=None, selectable=False):
    """Compute target date from counter, query DB using provided cursor, render and return
    (PIL.Image, new_current_displayed_date, new_last_displayed_value).
    """
    # Initialize base date
    if current_displayed_date is None:
        current_displayed_date = datetime.date.today()

    # compute delta days from counter values
    try:
        if last_displayed_value is None:
            delta_days = 0
        else:
            # guard against None/empty
            if current_value is None or current_value == '':
                delta_days = 0
            else:
                delta_days = int(current_value) - int(last_displayed_value)
    except Exception:
        logging.exception("Failed to compute delta_days in render_by_date")
        delta_days = 0

    target_date_dt = current_displayed_date + datetime.timedelta(days=delta_days)
    new_current_displayed_date = target_date_dt
    target_date = target_date_dt.strftime('%d.%m.%Y')

    # Query DB for tip performances on target date
    query = '''
        SELECT id, name, theatre, starting_time, date, tip, stars 
        FROM inscenations 
        WHERE tip = 1 AND date = ? 
        ORDER BY starting_time
    '''
    cursor.execute(query, (target_date,))
    results = cursor.fetchall()

    img = draw_by_date(epd, results, target_date, font, font1, selected_index, selectable)

    # update last_displayed_value to the current counter value (string or None)
    new_last_displayed_value = current_value
    return img, new_current_displayed_date, new_last_displayed_value, results


def _wrap_text(text, font, max_width, draw):
    if not text:
        return []

    lines = []
    for paragraph in text.splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append('')
            continue

        words = paragraph.split()
        line = words[0]
        for word in words[1:]:
            test_line = f"{line} {word}"
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] <= max_width:
                line = test_line
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def _render_inscenation_detail(epd, name, theatre, starting_time, date, url, font, font1=None):
    """Render a single inscenation detail view with optional scraped metadata."""
    chosen_id = None
    info = None
    if url:
        try:
            info = scrape_inscenation_info(url)
        except Exception:
            logging.exception('Failed to scrape inscenation info for detail view')

    if info is None:
        # Fallback to database values if scraping fails or URL is unavailable.
        info = type('FallbackInfo', (), {})()
        info.author = None
        info.premiere = None
        info.creators = []
        info.actors = None
        info.description = None
        info.duration = None
        info.dates = [f"{date} {starting_time}"]
        info.logo_url = None
        info.editor_rating = None
        info.user_rating = None

    title_font = font1 or font
    image = Image.new('1', (epd.width, epd.height), 255)
    draw = ImageDraw.Draw(image)

    # Load and prepare theatre logo if available
    logo_img = None
    max_logo_width = 200
    max_logo_height = 200
    logo_x = epd.width - max_logo_width
    logo_y = HEADER_HEIGHT + 8
    if info.logo_url:
        try:
            response = requests.get(info.logo_url, timeout=5)
            if response.status_code == 200:
                logo_img = Image.open(BytesIO(response.content))
                # Convert to RGB if needed
                if logo_img.mode in ('RGBA', 'LA', 'P'):
                    logo_img = logo_img.convert('RGBA')
                    bg = Image.new('RGBA', logo_img.size, (255, 255, 255, 255))
                    logo_img = Image.alpha_composite(bg, logo_img)
                logo_img = logo_img.convert('RGB')
                # Resize maintaining aspect ratio, constrained by max width (200) and max height (200)
                aspect = logo_img.height / logo_img.width
                width_based_height = int(max_logo_width * aspect)
                if width_based_height > max_logo_height:
                    # Height constraint is active
                    final_height = max_logo_height
                    final_width = int(max_logo_height / aspect)
                else:
                    # Width constraint is active
                    final_width = max_logo_width
                    final_height = width_based_height
                logo_img = logo_img.resize((final_width, final_height), Image.LANCZOS)
                # Adjust logo_x based on actual width to right-align it
                logo_x = epd.width - final_width
                # Convert to monochrome
                logo_img = logo_img.convert('L').point(lambda p: 0 if p < 128 else 255, mode='1')
        except Exception:
            logging.exception('Failed to load theatre logo')

    x = 10
    y = HEADER_HEIGHT + 8
    # Calculate logo boundaries for text avoidance
    logo_bottom = (logo_y + logo_img.height) if logo_img else 0

    def get_max_width_for_y(y_pos):
        """Determine max text width based on vertical position relative to logo."""
        if logo_img and logo_y <= y_pos < logo_bottom:
            return logo_x - 20
        else:
            return epd.width - 20

    title = name
    title_max_width = get_max_width_for_y(y)
    for line in _wrap_text(title, title_font, title_max_width, draw):
        draw.text((x, y), line, font=title_font, fill=0)
        bbox = draw.textbbox((0, 0), line, font=title_font)
        y += (bbox[3] - bbox[1]) + 4

    # Format dates from scraper (first 3, with "..." if more)
    if info.dates:
        dates_display = ', '.join(info.dates[:3])
        if len(info.dates) > 3:
            dates_display += ' ...'
    else:
        # Fallback to database date/time if no dates from scraper
        dates_display = f"{date} {starting_time}"

    info_lines = [
        f"Divadlo: {theatre}",
        f"Datum: {dates_display}",
    ]
    if info.duration:
        info_lines.append(f"Délka: {info.duration}")
    if info.premiere:
        info_lines.append(f"Premiéra: {info.premiere}")
    # Add ratings if available
    if hasattr(info, 'editor_rating') and hasattr(info, 'user_rating'):
        ratings_parts = []
        if info.editor_rating:
            ratings_parts.append(f"Redakce: {info.editor_rating}")
        if info.user_rating:
            ratings_parts.append(f"Uživatelé: {info.user_rating}")
        if ratings_parts:
            info_lines.append(" | ".join(ratings_parts))
    if info.author:
        author = info.author
        author_words = author.split()
        if len(author_words) > 8:
            author = ' '.join(author_words[:8]) + '...'
        info_lines.append(f"Autor: {author}")
    if info.creators:
        creators = ', '.join(info.creators) if isinstance(info.creators, (list, tuple)) else str(info.creators)
        if creators:
            creators_words = creators.split()
            if len(creators_words) > 8:
                creators = ' '.join(creators_words[:8]) + '...'
            info_lines.append(f"Tvůrci: {creators}")
    if info.actors:
        actors = info.actors
        actors_words = actors.split()
        if len(actors_words) > 8:
            actors = ' '.join(actors_words[:8]) + '...'
        info_lines.append(f"Herci: {actors}")

    for line in info_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        if y + (bbox[3] - bbox[1]) > epd.height - 20:
            break
        line_max_width = get_max_width_for_y(y)
        wrapped_lines = _wrap_text(line, font, line_max_width, draw)
        is_first_wrapped = True
        for wrapped_line in wrapped_lines:
            bbox = draw.textbbox((0, 0), wrapped_line, font=font)
            if y + (bbox[3] - bbox[1]) > epd.height - 20:
                break
            draw.text((x, y), wrapped_line, font=font, fill=0)
            # Underline label only on first wrapped line
            if is_first_wrapped and ':' in wrapped_line:
                label_part = wrapped_line.split(':')[0] + ':'
                label_bbox = draw.textbbox((x, y), label_part, font=font)
                underline_y = label_bbox[3] + 1
                draw.line((label_bbox[0], underline_y, label_bbox[2], underline_y), fill=0)
                is_first_wrapped = False
            y += (bbox[3] - bbox[1]) + 4

    y += 6
    description = info.description or 'Bez popisu.'
    draw.text((x, y), 'Popis:', font=font, fill=0)
    bbox = draw.textbbox((x, y), 'Popis:', font=font)
    underline_y = bbox[3] + 1
    draw.line((bbox[0], underline_y, bbox[2], underline_y), fill=0)
    y += (bbox[3] - bbox[1]) + 4

    for line in _wrap_text(description, font, get_max_width_for_y(y), draw):
        bbox = draw.textbbox((0, 0), line, font=font)
        if y + (bbox[3] - bbox[1]) > epd.height - 10:
            break
        draw.text((x, y), line, font=font, fill=0)
        y += (bbox[3] - bbox[1]) + 3

    # Paste logo if available
    if logo_img:
        image.paste(logo_img, (logo_x, logo_y))

    return image, chosen_id


def render_idle(epd, cursor, font, font1=None, last_displayed_id=None):
    """Render a single random tip performance with full inscenation info."""
    cursor.execute('PRAGMA table_info(inscenations)')
    columns = [row[1] for row in cursor.fetchall()]
    has_url = 'url' in columns

    if has_url:
        cursor.execute('SELECT id, name, theatre, starting_time, date, url FROM inscenations WHERE tip = 1')
    else:
        cursor.execute('SELECT id, name, theatre, starting_time, date, NULL FROM inscenations WHERE tip = 1')

    candidates = cursor.fetchall()
    if not candidates:
        img = Image.new('1', (epd.width, epd.height), 255)
        draw = ImageDraw.Draw(img)
        draw.text((10, HEADER_HEIGHT + 8), 'Žádné představení k dispozici.', font=font, fill=0)
        return img, None

    if last_displayed_id is not None and len(candidates) > 1:
        candidate = random.choice(candidates)
        while candidate[0] == last_displayed_id:
            candidate = random.choice(candidates)
    else:
        candidate = random.choice(candidates)

    chosen_id, name, theatre, starting_time, date, url = candidate
    image, _ = _render_inscenation_detail(epd, name, theatre, starting_time, date, url, font, font1)
    return image, chosen_id


def render_inscenation_detail_by_id(epd, cursor, inscenation_id, font, font1=None):
    """Render inscenation detail by id using the same layout as idle mode."""
    cursor.execute('PRAGMA table_info(inscenations)')
    columns = [row[1] for row in cursor.fetchall()]
    has_url = 'url' in columns

    if has_url:
        cursor.execute(
            'SELECT id, name, theatre, starting_time, date, url FROM inscenations WHERE id = ?',
            (inscenation_id,),
        )
    else:
        cursor.execute(
            'SELECT id, name, theatre, starting_time, date, NULL FROM inscenations WHERE id = ?',
            (inscenation_id,),
        )

    row = cursor.fetchone()
    if not row:
        img = Image.new('1', (epd.width, epd.height), 255)
        draw = ImageDraw.Draw(img)
        draw.text((10, HEADER_HEIGHT + 8), 'Představení nebylo nalezeno.', font=font, fill=0)
        return img, None

    chosen_id, name, theatre, starting_time, date, url = row
    image, _ = _render_inscenation_detail(epd, name, theatre, starting_time, date, url, font, font1)
    return image, chosen_id
