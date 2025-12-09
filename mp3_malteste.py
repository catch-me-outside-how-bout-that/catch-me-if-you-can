from time import sleep, time
from machine import I2C, Pin, ADC, UART
from ht16k33 import HT16K33Matrix
import random
from dfplayer import DFPlayer

def jetzt_ms():
    return int(time() * 1000)

GAME_DURATION_MS = 120000  # 2 Minuten

# Joystick
vrx = ADC(Pin(3), atten=ADC.ATTN_11DB)
vry = ADC(Pin(4), atten=ADC.ATTN_11DB)

CENTER_X = 1940
CENTER_Y = 1895
DEADZONE = 200
MOVE_DELAY_MS = 120
SPEED_BOOST_DELAY_MS = 70

# HT16K33 Display
display = HT16K33Matrix(I2C(0))
display.set_angle(270)

# Spielfeld-Maps
maps = [
    b"\x00\x66\x42\x58\x0b\x20\x6e\x00",
    b"\x00\x6e\x42\x10\x70\x06\x22\x30",
    b"\x10\x18\x4a\x63\x32\x00\x2c\x20",
    b"\x00\x46\x6c\x20\x22\x0a\x7a\x00"
]

# Buttons
button_red = Pin("A0", Pin.IN, Pin.PULL_UP)
button_blue = Pin("A1", Pin.IN, Pin.PULL_UP)

# DFPLAYER → UART0 über GROVE-Port
uart = UART(0, tx=Pin("TX"), rx=Pin("RX"))
mp3 = DFPlayer(uart)
mp3.volume = 25  # Lautstärke 0–100


# ---------------------------------------------------------
# Funktionen
# ---------------------------------------------------------

def kollision_wand(x, y, map_bytes):
    if x < 0 or x > 7 or y < 0 or y > 7:
        return True
    phys_x = x
    phys_y = y
    byte = map_bytes[phys_y]
    bit = 1 << (7 - phys_x)
    return (byte & bit) != 0

def read_joystick_direction():
    x_raw = vrx.read()
    y_raw = vry.read()

    x_pos = x_raw - CENTER_X
    y_pos = y_raw - CENTER_Y

    if abs(x_pos) < DEADZONE and abs(y_pos) < DEADZONE:
        return None

    if abs(x_pos) > abs(y_pos):
        return "RIGHT" if x_pos > 0 else "LEFT"
    return "DOWN" if y_pos > 0 else "UP"

def spiral_close(display):
    coords = []
    x0, y0, x1, y1 = 0, 0, 7, 7
    while x0 <= x1 and y0 <= y1:
        for x in range(x0, x1+1):
            coords.append((x, y0))
        for y in range(y0+1, y1+1):
            coords.append((x1, y))
        if y0 != y1:
            for x in range(x1-1, x0-1, -1):
                coords.append((x, y1))
        if x0 != x1:
            for y in range(y1-1, y0, -1):
                coords.append((x0, y))

        x0 += 1
        y0 += 1
        x1 -= 1
        y1 -= 1

    for x, y in coords:
        display.plot(x, y, 1)
        display.draw()
        sleep(0.03)

def zeige_ergebnis(rolle, gefangen):
    display.clear()
    sleep(0.2)
    if rolle == "Wegrenner":
        text = "Verloren" if gefangen else "Gewonnen!"
    else:
        text = "Gewonnen!" if gefangen else "Verloren"
    display.scroll_text(text)
    sleep(0.8)

def warte_auf_restart():
    display.clear()
    display.scroll_text("Beide Tasten")
    display.scroll_text("3s halten")
    timer = 0
    while True:
        if button_red.value() == 0 and button_blue.value() == 0:
            if timer == 0:
                timer = jetzt_ms()
            if jetzt_ms() - timer >= 3000:
                return
        else:
            timer = 0
        sleep(0.05)


# ---------------------------------------------------------
# Hauptspiel
# ---------------------------------------------------------

def starte_spiel():
    global last_move_ms

    # Hintergrundmusik starten
    mp3.pause()
    sleep(0.1)
    mp3.play_track(1, 1)   # Track 1 im Ordner 01
    last_move_ms = 0

    p1_x, p1_y = 7, 7
    p2_x, p2_y = 0, 0

    karte = random.choice(maps)

    used_red = used_blue = 0
    last_red = last_blue = 1
    invis = speed = 0

    game_start = jetzt_ms()

    while True:
        jetzt = jetzt_ms()

        # Timeout = Game Over
        if jetzt - game_start >= GAME_DURATION_MS:
            mp3.pause()
            sleep(0.1)
            mp3.play_track(1, 2)  # Track 2 - GameOver
            spiral_close(display)
            zeige_ergebnis("Wegrenner", gefangen=False)
            return

        # Buttons
        red = button_red.value()
        blue = button_blue.value()

        if last_red == 1 and red == 0 and used_red < 2:
            invis = jetzt + 3000
            used_red += 1

        if last_blue == 1 and blue == 0 and used_blue < 2:
            speed = jetzt + 3000
            used_blue += 1

        last_red = red
        last_blue = blue

        # Bewegung
        delay = SPEED_BOOST_DELAY_MS if jetzt < speed else MOVE_DELAY_MS
        richtung = read_joystick_direction()

        if richtung and (jetzt - last_move_ms) >= delay:
            nx, ny = p1_x, p1_y

            if richtung == "UP": ny -= 1
            elif richtung == "DOWN": ny += 1
            elif richtung == "LEFT": nx -= 1
            elif richtung == "RIGHT": nx += 1

            if not kollision_wand(nx, ny, karte):
                p1_x, p1_y = nx, ny
            last_move_ms = jetzt

        # Fang?
        if p1_x == p2_x and p1_y == p2_y:
            mp3.pause()
            sleep(0.1)
            mp3.play_track(1, 2)
            spiral_close(display)
            zeige_ergebnis("Faenger", gefangen=True)
            return

        # Render
        display.clear()
        display.set_icon(karte).draw()
        display.plot(p2_x, p2_y, 1)

        if jetzt >= invis:
            display.plot(p1_x, p1_y, 1)

        display.draw()
        sleep(0.02)


# ---------------------------------------------------------
# Loop
# ---------------------------------------------------------

while True:
    starte_spiel()
    warte_auf_restart()
