import RPi.GPIO as GPIO # type: ignore
from time import sleep
import threading
import logging
import time
CLK = 5
DT = 6
BTN = 26
counter = 0
counter_lock = threading.Lock()

GPIO.setmode(GPIO.BCM)
GPIO.setup(CLK, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(DT, GPIO.IN, pull_up_down=GPIO.PUD_UP) 
GPIO.setup(BTN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
logging.basicConfig(level=logging.DEBUG)

def update_file():
    # Uloží aktuální pozici enkodéru pro proces displeje.
    with open("/tmp/counter.txt", "w") as f:
        f.write(str(int(counter)))
    print(f"Value saved: {counter}")


def write_button_event():
    # Zapíše monotónní token, aby displej rozpoznal každý stisk.
    with open("/tmp/knob_press.txt", "w") as f:
        f.write(str(time.time_ns()))

def button_pressed():
    print("Button Clicked!")
    write_button_event()
clkLastState = GPIO.input(CLK)
last_button_state = GPIO.input(BTN)
last_button_event_time = 0.0

print("System Active. Use GPIO 5, 6, and 26.")
try:
    while True:
        clkState = GPIO.input(CLK)
        if clkState != clkLastState:
            # Enkodér se pohnul, DT určí směr.
            dtState = GPIO.input(DT)
            if dtState != clkState:
                with counter_lock:
                    counter += 1
            else:
                with counter_lock:
                    counter -= 1
            with counter_lock:
                print(f"Position: {counter}")
            update_file()

        button_state = GPIO.input(BTN)
        # Tlačítko je active-low: přechod 1 -> 0 znamená stisk.
        if button_state == GPIO.LOW and last_button_state == GPIO.HIGH:
            now = time.time()
            if (now - last_button_event_time) >= 0.2:
                button_pressed()
                last_button_event_time = now

        last_button_state = button_state
        clkLastState = clkState
        sleep(0.01)  # Krátké zpoždění kvůli odrušení a menšímu zatížení CPU.
except KeyboardInterrupt:
    logging.info("Keyboard Interrupt detected. Stopping encoder...")
finally:
    GPIO.cleanup()