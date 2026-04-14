import sys
import os
import sqlite3
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

import logging
from waveshare_epd import epd7in5_V2 # type: ignore
import time
from PIL import ImageFont
import draw_modes
logging.basicConfig(level=logging.DEBUG)

script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'theatre.db')

def get_stored_counter():
    try:
        with open("/tmp/counter.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        logging.info("File not found.")
        return None


def get_knob_press_token():
    try:
        with open("/tmp/knob_press.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default
last_displayed_value = None
last_change_time = 0
is_sleeping = True
current_displayed_date = None
partial_refresh_count = 0
partial_refresh_limit = 10
conn = None

try:
    epd = epd7in5_V2.EPD()   
    logging.info("init and Clear")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    epd.init()
    epd.Clear()
    epd.sleep()
    font = ImageFont.truetype("unispace bd.ttf", 18)
    font1 = ImageFont.truetype("unispace bd.ttf", 30)
    output_mode = 'idle'
    idle_interval = 60
    screen_inactivity_timeout = 300
    last_render_time = 0
    last_displayed_tip_id = None
    last_user_activity = time.time()
    observed_counter_value = get_stored_counter()
    observed_knob_press_token = get_knob_press_token()
    by_date_last_activity = 0
    by_date_results = []
    by_date_selection_mode = False
    by_date_detail_mode = False
    selected_result_index = 0
    selection_last_counter_value = observed_counter_value
    selected_inscenation_id = None
    last_knob_press_handled_time = 0.0
    menu_options = ['by_date', 'by_theatre', 'idle']
    menu_open = False
    menu_selected_index = 0
    menu_last_counter_value = observed_counter_value
    by_theatre_last_activity = 0
    by_theatre_last_displayed_value = observed_counter_value
    current_theatre_page_index = 0
    by_theatre_page_theatres = []
    by_theatre_selection_mode = False
    by_theatre_detail_mode = False
    selected_theatre_index = 0
    theatre_selection_last_counter_value = observed_counter_value
    selected_theatre_name = None
    theatre_page_selection_mode = False
    theatre_page_last_displayed_value = observed_counter_value
    current_theatre_detail_page_index = 0
    theatre_page_rows = []
    selected_theatre_performance_index = 0
    theatre_page_selection_last_counter_value = observed_counter_value
    theatre_performance_detail_mode = False
    selected_theatre_performance_id = None

    while True:
        current_value = get_stored_counter()
        current_knob_press_token = get_knob_press_token()
        current_time = time.time()

        if current_value != observed_counter_value:
            observed_counter_value = current_value
            last_user_activity = current_time

        if current_knob_press_token != observed_knob_press_token:
            now = current_time
            if (now - last_knob_press_handled_time) < 0.35:
                observed_knob_press_token = current_knob_press_token
                continue

            logging.info("Knob press detected")
            observed_knob_press_token = current_knob_press_token
            last_knob_press_handled_time = now
            last_user_activity = current_time
            by_date_last_activity = current_time
            by_theatre_last_activity = current_time

            # Akce po stisku vždy dělají plné překreslení (nikoli partial).
            if partial_refresh_count > 0:
                epd.init_fast()
                partial_refresh_count = 0
                is_sleeping = False

            if menu_open:
                chosen_mode = menu_options[menu_selected_index]
                menu_open = False

                if chosen_mode == 'by_date':
                    output_mode = 'by_date'
                    by_date_selection_mode = False
                    by_date_detail_mode = False
                    selected_result_index = 0
                    by_date_last_activity = current_time
                    try:
                        if is_sleeping:
                            epd.init_fast()
                            is_sleeping = False

                        Himage, new_current_displayed_date, new_last_displayed_value, new_results = draw_modes.render_by_date(
                            epd,
                            current_value,
                            current_value,
                            current_displayed_date,
                            cursor,
                            font,
                            font1,
                            selected_index=None,
                            selectable=False,
                        )
                        draw_modes.draw_status_bar(Himage, font, output_mode)
                        epd.display(epd.getbuffer(Himage))
                        current_displayed_date = new_current_displayed_date
                        last_displayed_value = new_last_displayed_value
                        by_date_results = new_results
                        last_change_time = current_time
                    except Exception:
                        logging.exception("Failed to render by-date after menu selection")

                elif chosen_mode == 'by_theatre':
                    output_mode = 'by_theatre'
                    by_theatre_selection_mode = False
                    by_theatre_detail_mode = False
                    selected_theatre_index = 0
                    theatre_page_selection_mode = False
                    theatre_performance_detail_mode = False
                    selected_theatre_performance_index = 0
                    selected_theatre_name = None
                    by_theatre_last_activity = current_time
                    try:
                        if is_sleeping:
                            epd.init_fast()
                            is_sleeping = False

                        Himage, new_page_index, new_last_value, page_theatres = draw_modes.render_by_theatre(
                            epd,
                            current_value,
                            current_value,
                            current_theatre_page_index,
                            cursor,
                            font,
                            font1,
                            selected_index=None,
                            selectable=False,
                        )
                        draw_modes.draw_status_bar(Himage, font, output_mode)
                        epd.display(epd.getbuffer(Himage))
                        current_theatre_page_index = new_page_index
                        by_theatre_last_displayed_value = new_last_value
                        by_theatre_page_theatres = page_theatres
                        last_change_time = current_time
                    except Exception:
                        logging.exception("Failed to render by-theatre after menu selection")

                else:
                    output_mode = 'idle'
                    last_render_time = 0

                continue

            # V idle režimu otevře menu stisk tlačítka.
            if output_mode == 'idle':
                menu_open = True
                if output_mode == 'by_date':
                    menu_selected_index = 0
                elif output_mode == 'by_theatre':
                    menu_selected_index = 1
                else:
                    menu_selected_index = 2
                menu_last_counter_value = current_value
                try:
                    if is_sleeping:
                        epd.init_fast()
                        is_sleeping = False
                    Himage = draw_modes.draw_mode_menu(epd, font, menu_selected_index)
                    draw_modes.draw_status_bar(Himage, font, 'menu')
                    epd.display(epd.getbuffer(Himage))
                    last_change_time = current_time
                except Exception:
                    logging.exception("Failed to open mode menu")
                continue

            if output_mode == 'by_date':
                if not by_date_selection_mode and not by_date_detail_mode:
                    by_date_selection_mode = True
                    by_date_detail_mode = False
                    selected_result_index = 0
                    selection_last_counter_value = current_value
                    if by_date_results:
                        try:
                            if is_sleeping:
                                epd.init_fast()
                                is_sleeping = False

                            Himage, new_current_displayed_date, new_last_displayed_value, new_results = draw_modes.render_by_date(
                                epd,
                                current_value,
                                current_value,
                                current_displayed_date,
                                cursor,
                                font,
                                font1,
                                selected_index=selected_result_index,
                                selectable=True,
                            )
                            draw_modes.draw_status_bar(Himage, font, output_mode)
                            epd.display(epd.getbuffer(Himage))
                            current_displayed_date = new_current_displayed_date
                            last_displayed_value = new_last_displayed_value
                            by_date_results = new_results
                            last_change_time = current_time
                        except Exception:
                            logging.exception("Failed to enter by-date selection mode")

                elif by_date_selection_mode and not by_date_detail_mode:
                    if selected_result_index == 0:
                        # Vybraný řádek Menu: návrat do menu režimů.
                        menu_open = True
                        menu_selected_index = 0
                        menu_last_counter_value = current_value
                        by_date_selection_mode = False
                        by_date_detail_mode = False
                        try:
                            if is_sleeping:
                                epd.init_fast()
                                is_sleeping = False
                            Himage = draw_modes.draw_mode_menu(epd, font, menu_selected_index)
                            draw_modes.draw_status_bar(Himage, font, 'menu')
                            epd.display(epd.getbuffer(Himage))
                            last_change_time = current_time
                        except Exception:
                            logging.exception("Failed to open mode menu from by-date selection")
                    elif selected_result_index == 1:
                        # Vybraný řádek Zpět: návrat do prohlížení dle data.
                        by_date_selection_mode = False
                        by_date_detail_mode = False
                        try:
                            if is_sleeping:
                                epd.init_fast()
                                is_sleeping = False

                            Himage, new_current_displayed_date, new_last_displayed_value, new_results = draw_modes.render_by_date(
                                epd,
                                current_value,
                                current_value,
                                current_displayed_date,
                                cursor,
                                font,
                                font1,
                                selected_index=None,
                                selectable=False,
                            )
                            draw_modes.draw_status_bar(Himage, font, output_mode)
                            epd.display(epd.getbuffer(Himage))
                            current_displayed_date = new_current_displayed_date
                            last_displayed_value = new_last_displayed_value
                            by_date_results = new_results
                            last_change_time = current_time
                        except Exception:
                            logging.exception("Failed to leave by-date selection mode via Back row")
                    elif by_date_results and selected_result_index > 1:
                        selected_inscenation_id = by_date_results[selected_result_index - 2][0]
                        try:
                            if is_sleeping:
                                epd.init_fast()
                                is_sleeping = False

                            Himage, _ = draw_modes.render_inscenation_detail_by_id(
                                epd,
                                cursor,
                                selected_inscenation_id,
                                font,
                                font1,
                            )
                            draw_modes.draw_status_bar(Himage, font, 'by_date_detail')
                            epd.display(epd.getbuffer(Himage))
                            by_date_detail_mode = True
                            last_change_time = current_time
                        except Exception:
                            logging.exception("Failed to render selected inscenation detail")

                elif by_date_detail_mode:
                    by_date_detail_mode = False
                    by_date_selection_mode = True
                    selection_last_counter_value = current_value
                    try:
                        if is_sleeping:
                            epd.init_fast()
                            is_sleeping = False

                        Himage, new_current_displayed_date, new_last_displayed_value, new_results = draw_modes.render_by_date(
                            epd,
                            current_value,
                            current_value,
                            current_displayed_date,
                            cursor,
                            font,
                            font1,
                            selected_index=selected_result_index,
                            selectable=True,
                        )
                        draw_modes.draw_status_bar(Himage, font, output_mode)
                        epd.display(epd.getbuffer(Himage))
                        current_displayed_date = new_current_displayed_date
                        last_displayed_value = new_last_displayed_value
                        by_date_results = new_results
                        last_change_time = current_time
                    except Exception:
                        logging.exception("Failed to return from detail to by-date selection")

            elif output_mode == 'by_theatre':
                if not by_theatre_selection_mode and not by_theatre_detail_mode:
                    by_theatre_selection_mode = True
                    by_theatre_detail_mode = False
                    selected_theatre_index = 0
                    theatre_selection_last_counter_value = current_value
                    try:
                        if is_sleeping:
                            epd.init_fast()
                            is_sleeping = False

                        Himage, new_page_index, new_last_value, page_theatres = draw_modes.render_by_theatre(
                            epd,
                            current_value,
                            current_value,
                            current_theatre_page_index,
                            cursor,
                            font,
                            font1,
                            selected_index=selected_theatre_index,
                            selectable=True,
                        )
                        draw_modes.draw_status_bar(Himage, font, output_mode)
                        epd.display(epd.getbuffer(Himage))
                        current_theatre_page_index = new_page_index
                        by_theatre_last_displayed_value = new_last_value
                        by_theatre_page_theatres = page_theatres
                        last_change_time = current_time
                    except Exception:
                        logging.exception("Failed to enter by-theatre selection mode")

                elif by_theatre_selection_mode and not by_theatre_detail_mode:
                    if selected_theatre_index == 0:
                        menu_open = True
                        menu_selected_index = 1
                        menu_last_counter_value = current_value
                        by_theatre_selection_mode = False
                        by_theatre_detail_mode = False
                        try:
                            if is_sleeping:
                                epd.init_fast()
                                is_sleeping = False
                            Himage = draw_modes.draw_mode_menu(epd, font, menu_selected_index)
                            draw_modes.draw_status_bar(Himage, font, 'menu')
                            epd.display(epd.getbuffer(Himage))
                            last_change_time = current_time
                        except Exception:
                            logging.exception("Failed to open mode menu from by-theatre selection")
                    elif selected_theatre_index == 1:
                        by_theatre_selection_mode = False
                        by_theatre_detail_mode = False
                        try:
                            if is_sleeping:
                                epd.init_fast()
                                is_sleeping = False

                            Himage, new_page_index, new_last_value, page_theatres = draw_modes.render_by_theatre(
                                epd,
                                current_value,
                                current_value,
                                current_theatre_page_index,
                                cursor,
                                font,
                                font1,
                                selected_index=None,
                                selectable=False,
                            )
                            draw_modes.draw_status_bar(Himage, font, output_mode)
                            epd.display(epd.getbuffer(Himage))
                            current_theatre_page_index = new_page_index
                            by_theatre_last_displayed_value = new_last_value
                            by_theatre_page_theatres = page_theatres
                            last_change_time = current_time
                        except Exception:
                            logging.exception("Failed to leave by-theatre selection mode via Back row")
                    elif by_theatre_page_theatres and selected_theatre_index > 1:
                        selected_theatre_name = by_theatre_page_theatres[selected_theatre_index - 2]
                        try:
                            if is_sleeping:
                                epd.init_fast()
                                is_sleeping = False
                            elif partial_refresh_count > 0:
                                epd.init_fast()
                                partial_refresh_count = 0

                            theatre_page_selection_mode = False
                            theatre_performance_detail_mode = False
                            selected_theatre_performance_index = 0
                            theatre_page_selection_last_counter_value = current_value

                            Himage, new_page_index, new_last_value, page_rows = draw_modes.render_theatre_page_list(
                                epd,
                                current_value,
                                current_value,
                                current_theatre_detail_page_index,
                                cursor,
                                selected_theatre_name,
                                font,
                                font1,
                                selected_index=None,
                                selectable=False,
                            )
                            draw_modes.draw_status_bar(Himage, font, 'theatre_page')
                            epd.display(epd.getbuffer(Himage))
                            by_theatre_detail_mode = True
                            current_theatre_detail_page_index = new_page_index
                            theatre_page_last_displayed_value = new_last_value
                            theatre_page_rows = page_rows
                            last_change_time = current_time
                        except Exception:
                            logging.exception("Failed to render theatre page")

                elif by_theatre_detail_mode:
                    if theatre_performance_detail_mode:
                        theatre_performance_detail_mode = False
                        theatre_page_selection_mode = True
                        theatre_page_selection_last_counter_value = current_value
                        try:
                            if is_sleeping:
                                epd.init_fast()
                                is_sleeping = False
                            elif partial_refresh_count > 0:
                                epd.init_fast()
                                partial_refresh_count = 0

                            Himage, new_page_index, new_last_value, page_rows = draw_modes.render_theatre_page_list(
                                epd,
                                current_value,
                                current_value,
                                current_theatre_detail_page_index,
                                cursor,
                                selected_theatre_name,
                                font,
                                font1,
                                selected_index=selected_theatre_performance_index,
                                selectable=True,
                            )
                            draw_modes.draw_status_bar(Himage, font, 'theatre_page')
                            epd.display(epd.getbuffer(Himage))
                            current_theatre_detail_page_index = new_page_index
                            theatre_page_last_displayed_value = new_last_value
                            theatre_page_rows = page_rows
                            last_change_time = current_time
                        except Exception:
                            logging.exception("Failed to return from performance detail to theatre page selection")
                    elif not theatre_page_selection_mode:
                        theatre_page_selection_mode = True
                        selected_theatre_performance_index = 0
                        theatre_page_selection_last_counter_value = current_value
                        try:
                            if is_sleeping:
                                epd.init_fast()
                                is_sleeping = False
                            elif partial_refresh_count > 0:
                                epd.init_fast()
                                partial_refresh_count = 0

                            Himage, new_page_index, new_last_value, page_rows = draw_modes.render_theatre_page_list(
                                epd,
                                current_value,
                                current_value,
                                current_theatre_detail_page_index,
                                cursor,
                                selected_theatre_name,
                                font,
                                font1,
                                selected_index=selected_theatre_performance_index,
                                selectable=True,
                            )
                            draw_modes.draw_status_bar(Himage, font, 'theatre_page')
                            epd.display(epd.getbuffer(Himage))
                            current_theatre_detail_page_index = new_page_index
                            theatre_page_last_displayed_value = new_last_value
                            theatre_page_rows = page_rows
                            last_change_time = current_time
                        except Exception:
                            logging.exception("Failed to enter theatre page selection mode")
                    else:
                        if selected_theatre_performance_index == 0:
                            # Zpět do menu: návrat na výběr divadel.
                            by_theatre_detail_mode = False
                            theatre_page_selection_mode = False
                            theatre_performance_detail_mode = False
                            by_theatre_selection_mode = False
                            try:
                                if is_sleeping:
                                    epd.init_fast()
                                    is_sleeping = False
                                elif partial_refresh_count > 0:
                                    epd.init_fast()
                                    partial_refresh_count = 0

                                Himage, new_page_index, new_last_value, page_theatres = draw_modes.render_by_theatre(
                                    epd,
                                    current_value,
                                    current_value,
                                    current_theatre_page_index,
                                    cursor,
                                    font,
                                    font1,
                                    selected_index=None,
                                    selectable=False,
                                )
                                draw_modes.draw_status_bar(Himage, font, output_mode)
                                epd.display(epd.getbuffer(Himage))
                                current_theatre_page_index = new_page_index
                                by_theatre_last_displayed_value = new_last_value
                                by_theatre_page_theatres = page_theatres
                                last_change_time = current_time
                            except Exception:
                                logging.exception("Failed to return to theatre selection screen")
                        elif selected_theatre_performance_index == 1:
                            theatre_page_selection_mode = False
                            try:
                                if is_sleeping:
                                    epd.init_fast()
                                    is_sleeping = False
                                elif partial_refresh_count > 0:
                                    epd.init_fast()
                                    partial_refresh_count = 0

                                Himage, new_page_index, new_last_value, page_rows = draw_modes.render_theatre_page_list(
                                    epd,
                                    current_value,
                                    current_value,
                                    current_theatre_detail_page_index,
                                    cursor,
                                    selected_theatre_name,
                                    font,
                                    font1,
                                    selected_index=None,
                                    selectable=False,
                                )
                                draw_modes.draw_status_bar(Himage, font, 'theatre_page')
                                epd.display(epd.getbuffer(Himage))
                                current_theatre_detail_page_index = new_page_index
                                theatre_page_last_displayed_value = new_last_value
                                theatre_page_rows = page_rows
                                last_change_time = current_time
                            except Exception:
                                logging.exception("Failed to leave theatre page selection mode via Back row")
                        elif theatre_page_rows and selected_theatre_performance_index > 1:
                            selected_theatre_performance_id = theatre_page_rows[selected_theatre_performance_index - 2][0]
                            try:
                                if is_sleeping:
                                    epd.init_fast()
                                    is_sleeping = False
                                elif partial_refresh_count > 0:
                                    epd.init_fast()
                                    partial_refresh_count = 0

                                Himage, _ = draw_modes.render_inscenation_detail_by_id(
                                    epd,
                                    cursor,
                                    selected_theatre_performance_id,
                                    font,
                                    font1,
                                )
                                draw_modes.draw_status_bar(Himage, font, 'by_theatre_detail')
                                epd.display(epd.getbuffer(Himage))
                                theatre_performance_detail_mode = True
                                last_change_time = current_time
                            except Exception:
                                logging.exception("Failed to render selected theatre performance detail")

        if menu_open and current_value != menu_last_counter_value:
            current_int = _safe_int(current_value)
            previous_int = _safe_int(menu_last_counter_value)
            delta = current_int - previous_int
            if delta != 0:
                menu_selected_index = (menu_selected_index + delta) % len(menu_options)
            menu_last_counter_value = current_value

            try:
                if is_sleeping:
                    epd.init_fast()
                    is_sleeping = False
                Himage = draw_modes.draw_mode_menu(epd, font, menu_selected_index)
                draw_modes.draw_status_bar(Himage, font, 'menu')
                if partial_refresh_count >= partial_refresh_limit:
                    epd.init()
                    epd.display(epd.getbuffer(Himage))
                    partial_refresh_count = 0
                else:
                    epd.init_part()
                    epd.display_Partial(epd.getbuffer(Himage), 0, 0, epd.width, epd.height)
                    partial_refresh_count += 1
                is_sleeping = False
                last_change_time = current_time
            except Exception:
                logging.exception("Failed to update mode menu selection")

        # Dokud je otevřené menu, nevykresluje se podkladový režim.
        if menu_open:
            time.sleep(0.1)
            continue

        # Globální timeout: po neaktivitě mimo idle přejde zařízení do idle.
        if output_mode != 'idle' and not menu_open and (current_time - last_user_activity) >= screen_inactivity_timeout:
            logging.info("No user activity for 5 minutes. Returning to idle mode.")
            output_mode = 'idle'
            by_date_selection_mode = False
            by_date_detail_mode = False
            selected_result_index = 0
            by_theatre_selection_mode = False
            by_theatre_detail_mode = False
            selected_theatre_index = 0
            theatre_page_selection_mode = False
            theatre_performance_detail_mode = False
            selected_theatre_performance_index = 0
            selected_theatre_name = None
            # Vynutí okamžité překreslení idle po přepnutí režimu.
            last_render_time = 0

        if output_mode == 'idle':
            if menu_open:
                time.sleep(0.1)
                continue

            if (current_time - last_render_time) >= idle_interval:
                if is_sleeping:
                    epd.init_fast()
                    is_sleeping = False
                elif partial_refresh_count > 0:
                    epd.init_fast()
                    partial_refresh_count = 0
                try:
                    Himage, last_displayed_tip_id = draw_modes.render_idle(
                        epd,
                        cursor,
                        font,
                        font1,
                        last_displayed_tip_id,
                    )
                    draw_modes.draw_status_bar(Himage, font, output_mode)
                    epd.display(epd.getbuffer(Himage))
                except Exception:
                    logging.exception("Failed to render idle view via draw_modes.render_idle")
                last_render_time = current_time
                last_change_time = current_time

            if not menu_open and not is_sleeping and (current_time - last_change_time) > 6:
                logging.info("6 seconds idle. Putting display to sleep...")
                epd.sleep()
                is_sleeping = True
        else:
            if output_mode == 'by_theatre':
                if by_theatre_detail_mode:
                    if theatre_performance_detail_mode:
                        pass
                    elif theatre_page_selection_mode:
                        selectable_count = len(theatre_page_rows) + 2  # +2 řádky pro "Zpět do menu" a "Zpět"
                        if current_value != theatre_page_selection_last_counter_value and selectable_count > 0:
                            current_int = _safe_int(current_value)
                            previous_int = _safe_int(theatre_page_selection_last_counter_value)
                            delta = current_int - previous_int
                            if delta != 0:
                                selected_theatre_performance_index = (selected_theatre_performance_index + delta) % selectable_count
                            theatre_page_selection_last_counter_value = current_value

                            if is_sleeping:
                                epd.init_fast()
                                is_sleeping = False
                            try:
                                Himage, new_page_index, new_last_value, page_rows = draw_modes.render_theatre_page_list(
                                    epd,
                                    current_value,
                                    current_value,
                                    current_theatre_detail_page_index,
                                    cursor,
                                    selected_theatre_name,
                                    font,
                                    font1,
                                    selected_index=selected_theatre_performance_index,
                                    selectable=True,
                                )
                                draw_modes.draw_status_bar(Himage, font, 'theatre_page')
                                if partial_refresh_count >= partial_refresh_limit:
                                    epd.init()
                                    epd.display(epd.getbuffer(Himage))
                                    partial_refresh_count = 0
                                else:
                                    epd.init_part()
                                    epd.display_Partial(epd.getbuffer(Himage), 0, 0, epd.width, epd.height)
                                    partial_refresh_count += 1
                                is_sleeping = False
                                current_theatre_detail_page_index = new_page_index
                                theatre_page_last_displayed_value = new_last_value
                                theatre_page_rows = page_rows
                                by_theatre_last_activity = current_time
                                last_change_time = current_time
                            except Exception:
                                logging.exception("Failed to update theatre page selection cursor")
                    elif current_value != theatre_page_last_displayed_value:
                        if is_sleeping:
                            epd.init_fast()
                            is_sleeping = False
                        elif partial_refresh_count > 0:
                            epd.init_fast()
                            partial_refresh_count = 0
                        try:
                            Himage, new_page_index, new_last_value, page_rows = draw_modes.render_theatre_page_list(
                                epd,
                                current_value,
                                theatre_page_last_displayed_value,
                                current_theatre_detail_page_index,
                                cursor,
                                selected_theatre_name,
                                font,
                                font1,
                                selected_index=None,
                                selectable=False,
                            )
                            draw_modes.draw_status_bar(Himage, font, 'theatre_page')
                            epd.display(epd.getbuffer(Himage))
                            current_theatre_detail_page_index = new_page_index
                            theatre_page_last_displayed_value = new_last_value
                            theatre_page_rows = page_rows
                            by_theatre_last_activity = current_time
                            last_change_time = current_time
                        except Exception:
                            logging.exception("Failed to render theatre page list")
                elif by_theatre_selection_mode:
                    selectable_count = len(by_theatre_page_theatres) + 2  # +2 řádky pro "Zpět do menu" a "Zpět"
                    if current_value != theatre_selection_last_counter_value and selectable_count > 0:
                        current_int = _safe_int(current_value)
                        previous_int = _safe_int(theatre_selection_last_counter_value)
                        delta = current_int - previous_int
                        if delta != 0:
                            selected_theatre_index = (selected_theatre_index + delta) % selectable_count
                        theatre_selection_last_counter_value = current_value

                        if is_sleeping:
                            epd.init_fast()
                            is_sleeping = False
                        try:
                            Himage, new_page_index, new_last_value, page_theatres = draw_modes.render_by_theatre(
                                epd,
                                current_value,
                                current_value,
                                current_theatre_page_index,
                                cursor,
                                font,
                                font1,
                                selected_index=selected_theatre_index,
                                selectable=True,
                            )
                            draw_modes.draw_status_bar(Himage, font, output_mode)
                            if partial_refresh_count >= partial_refresh_limit:
                                epd.init()
                                epd.display(epd.getbuffer(Himage))
                                partial_refresh_count = 0
                            else:
                                epd.init_part()
                                epd.display_Partial(epd.getbuffer(Himage), 0, 0, epd.width, epd.height)
                                partial_refresh_count += 1
                            is_sleeping = False
                            current_theatre_page_index = new_page_index
                            by_theatre_last_displayed_value = new_last_value
                            by_theatre_page_theatres = page_theatres
                            by_theatre_last_activity = current_time
                            last_change_time = current_time
                        except Exception:
                            logging.exception("Failed to update by-theatre selection cursor")
                elif current_value != by_theatre_last_displayed_value:
                    if is_sleeping:
                        epd.init_fast()
                        is_sleeping = False
                    elif partial_refresh_count > 0:
                        epd.init_fast()
                        partial_refresh_count = 0
                    try:
                        Himage, new_page_index, new_last_value, page_theatres = draw_modes.render_by_theatre(
                            epd,
                            current_value,
                            by_theatre_last_displayed_value,
                            current_theatre_page_index,
                            cursor,
                            font,
                            font1,
                            selected_index=None,
                            selectable=False,
                        )
                        draw_modes.draw_status_bar(Himage, font, output_mode)
                        epd.display(epd.getbuffer(Himage))
                        current_theatre_page_index = new_page_index
                        by_theatre_last_displayed_value = new_last_value
                        by_theatre_page_theatres = page_theatres
                        by_theatre_last_activity = current_time
                        last_change_time = current_time
                    except Exception:
                        logging.exception("Failed to render by-theatre view")
            elif by_date_detail_mode:
                pass
            elif by_date_selection_mode:
                selectable_count = len(by_date_results) + 2  # +2 řádky pro "Zpět do menu" a "Zpět"
                if current_value != selection_last_counter_value and selectable_count > 0:
                    current_int = _safe_int(current_value)
                    previous_int = _safe_int(selection_last_counter_value)
                    delta = current_int - previous_int
                    if delta != 0:
                        selected_result_index = (selected_result_index + delta) % selectable_count
                    selection_last_counter_value = current_value

                    if is_sleeping:
                        epd.init_fast()
                        is_sleeping = False

                    try:
                        Himage, new_current_displayed_date, new_last_displayed_value, new_results = draw_modes.render_by_date(
                            epd,
                            current_value,
                            current_value,
                            current_displayed_date,
                            cursor,
                            font,
                            font1,
                            selected_index=selected_result_index,
                            selectable=True,
                        )
                        draw_modes.draw_status_bar(Himage, font, output_mode)
                        if partial_refresh_count >= partial_refresh_limit:
                            epd.init()
                            epd.display(epd.getbuffer(Himage))
                            partial_refresh_count = 0
                        else:
                            epd.init_part()
                            epd.display_Partial(epd.getbuffer(Himage), 0, 0, epd.width, epd.height)
                            partial_refresh_count += 1
                        is_sleeping = False
                        current_displayed_date = new_current_displayed_date
                        last_displayed_value = new_last_displayed_value
                        by_date_results = new_results
                        last_change_time = current_time
                    except Exception:
                        logging.exception("Failed to update by-date selection cursor")
            elif current_value != last_displayed_value:
                logging.info(f"Counter change detected: current_value={current_value!r}, last_displayed_value={last_displayed_value!r}")
                if is_sleeping:
                    epd.init_fast()
                    is_sleeping = False
                elif partial_refresh_count > 0:
                    epd.init_fast()
                    partial_refresh_count = 0

                # Veškerou logiku a vykreslení pro datum řeší draw_modes.render_by_date.
                try:
                    Himage, new_current_displayed_date, new_last_displayed_value, new_results = draw_modes.render_by_date(
                        epd,
                        current_value,
                        last_displayed_value,
                        current_displayed_date,
                        cursor,
                        font,
                        font1,
                        selected_index=None,
                        selectable=False,
                    )
                    draw_modes.draw_status_bar(Himage, font, output_mode)
                    epd.display(epd.getbuffer(Himage))
                    current_displayed_date = new_current_displayed_date
                    last_displayed_value = new_last_displayed_value
                    by_date_results = new_results
                except Exception:
                    logging.exception("Failed to render by-date view via draw_modes.render_by_date")
                last_change_time = current_time

            # V režimu podle data nechává obraz aktivní, bez automatického uspání.
        time.sleep(0.1)

except KeyboardInterrupt:
    logging.info("Keyboard Interrupt detected. Shutting down display...")

finally:
    epd7in5_V2.epdconfig.module_exit(cleanup=True)
    if conn is not None:
        conn.close()
    exit()