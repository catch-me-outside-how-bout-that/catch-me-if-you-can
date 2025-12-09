from time import sleep, time
from machine import I2C, Pin, ADC, UART
from ht16k33 import HT16K33Matrix
import random
import network
import espnow
import ujson

# --------------------------------------------
# DFPLAYER (UART0 → Pins "TX" / "RX")
# --------------------------------------------
from dfplayer import DFPlayer   # dozenten-version
uart = UART(0, tx=Pin("TX"), rx=Pin("RX"))
mp3 = DFPlayer(uart)
mp3.volume = 30   # 0–30


def jetzt_ms():
    return int(time() * 1000)


# ---- SPIEL-DAUER ----
GAME_DURATION_MS = 120000   # 2 Minuten


# ---- Joystick ----
vrx = ADC(Pin(3), atten=ADC.ATTN_11DB)
vry = ADC(Pin(4), atten=ADC.ATTN_11DB)

# ---- JOYSTICK AUTOKALIBRATION ----
sleep(0.5)
samples_x = []
samples_y = []
for _ in range(20):
    samples_x.append(vrx.read())
    samples_y.append(vry.read())
    sleep(0.02)

CENTER_X = sum(samples_x) // len(samples_x)
CENTER_Y = sum(samples_y) // len(samples_y)

DEADZONE = 150
MOVE_DELAY_MS = 120
SPEED_BOOST_DELAY_MS = 70


#----Display----
display = HT16K33Matrix(I2C(0))
display.set_angle(270)


#----Maps----
maps = [
    b"\x00\x66\x42\x58\x0b\x20\x6e\x00",
    b"\x00\x6e\x42\x10\x70\x06\x22\x30",
    b"\x10\x18\x4a\x63\x32\x00\x2c\x20",
    b"\x00\x46\x6c\x20\x22\x0a\x7a\x00"
]


#----Buttons----
button_red = Pin("A0", Pin.IN, Pin.PULL_UP)
button_blue = Pin("A1", Pin.IN, Pin.PULL_UP)


# ---------------------------------------------------------
# ESP-NOW SETUP (MASTER)
# ---------------------------------------------------------
w = network.WLAN(network.STA_IF)
w.active(True)

e = espnow.ESPNow()
e.active(True)

# MAC-ADRESSE DES SLAVE
peer_mac = b'H\xcaC/\x08\x14'
try:
    e.add_peer(peer_mac)
except Exception as err:
    print("add_peer:", err)

p2_dir = None
p2_red = 0
p2_blue = 0


# ---------------------------------------------------------
# HILFSFUNKTIONEN
# ---------------------------------------------------------
def zufaelliger_spieler():
    return "Faenger" if random.random() < 0.5 else "Wegrenner"

def zufaellige_map_index():
    return random.randrange(len(maps))

def zeige_startsequenz(rolle):
    display.clear()
    display.scroll_text(f"Du bist: {rolle}")
    sleep(0.6)
    display.scroll_text("Timer: 2.00min")
    sleep(0.4)
    display.clear()


def kollision_wand(x, y, map_bytes):
    if x < 0 or x > 7 or y < 0 or y > 7:
        return True
    log_x = 7 - y
    log_y = x
    bit_mask = 1 << (7 - log_x)
    return (map_bytes[log_y] & bit_mask) != 0


def read_joystick_direction():
    x_raw = vrx.read()
    y_raw = vry.read()
    x_pos = x_raw - CENTER_X
    y_pos = y_raw - CENTER_Y

    if abs(x_pos) < DEADZONE and abs(y_pos) < DEADZONE:
        return None

    if abs(x_pos) > abs(y_pos):
        return "RIGHT" if x_pos > 0 else "LEFT"
    else:
        return "DOWN" if y_pos > 0 else "UP"


def spiral_close(display):
    coords = [
        (0,0),(1,0),(2,0),(3,0),(4,0),(5,0),(6,0),(7,0),
        (7,1),(7,2),(7,3),(7,4),(7,5),(7,6),(7,7),
        (6,7),(5,7),(4,7),(3,7),(2,7),(1,7),(0,7),
        (0,6),(0,5),(0,4),(0,3),(0,2),(0,1),
        (1,1),(2,1),(3,1),(4,1),(5,1),(6,1),
        (6,2),(6,3),(6,4),(6,5),(6,6),
        (5,6),(4,6),(3,6),(2,6),(1,6),
        (1,5),(1,4),(1,3),(1,2),
        (2,2),(3,2),(4,2),(5,2),
        (5,3),(5,4),(5,5),
        (4,5),(3,5),(2,5),
        (2,4),(2,3),
        (3,3),(4,3),
        (4,4),(3,4)
    ]
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
    sleep(0.2)
    display.scroll_text("3s halten")
    sleep(0.2)

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
# ESP-NOW INPUT (SLAVE → MASTER)
# ---------------------------------------------------------
def handle_incoming():
    global p2_dir, p2_red, p2_blue
    try:
        mac, msg = e.recv(0)
    except OSError:
        return
    if not msg:
        return
    try:
        data = ujson.loads(msg.decode())
    except:
        return

    if data.get("type") == "input":
        p2_dir = data.get("dir", None)
        p2_red = data.get("red", 0)
        p2_blue = data.get("blue", 0)


# ---------------------------------------------------------
# SEND STATE TO SLAVE
# ---------------------------------------------------------
def send_state(p1_x, p1_y, p2_x, p2_y, rolle, map_index, remaining_ms):
    payload = {
        "type": "state",
        "p1_x": p1_x,
        "p1_y": p1_y,
        "p2_x": p2_x,
        "p2_y": p2_y,
        "role_for_peer": "Faenger" if rolle == "Wegrenner" else "Wegrenner",
        "map_index": map_index,
        "remaining_ms": remaining_ms
    }
    try:
        e.send(peer_mac, ujson.dumps(payload))
    except:
        pass


def send_start(map_index, rolle_peer):
    payload = {
        "type": "start",
        "role_for_peer": rolle_peer,
        "map_index": map_index,
        "start_ts": jetzt_ms()
    }
    try:
        e.send(peer_mac, ujson.dumps(payload))
    except:
        pass


# ---------------------------------------------------------
# HAUPT-SPIEL
# ---------------------------------------------------------
def starte_spiel():
    global p2_dir

    # ----------------------------------------
    # 🔊 1. Hintergrundmusik starten
    # ----------------------------------------
    mp3.pause()
    sleep(0.2)
    mp3.play_track(1, 1)   # Track 1 = Hintergrundmusik

    p1_x, p1_y = 7, 7
    p2_x, p2_y = 0, 0

    rolle = zufaelliger_spieler()
    map_index = zufaellige_map_index()
    karte = maps[map_index]

    used_red = 0
    used_blue = 0
    last_red = 1
    last_blue = 1
    invis = 0
    speed = 0

    p2_dir = None
    last_move_p1 = 0
    last_move_p2 = 0

    zeige_startsequenz(rolle)

    rolle_peer = "Faenger" if rolle == "Wegrenner" else "Wegrenner"
    send_start(map_index, rolle_peer)

    game_start = jetzt_ms()
    last_state_send = 0

    while True:
        jetzt = jetzt_ms()

        # ----------------------------------------
        # ⏳ TIMEOUT
        # ----------------------------------------
        if jetzt - game_start >= GAME_DURATION_MS:

            mp3.pause()
            sleep(0.2)
            mp3.play_track(1, 2)   # Game Over Sound

            won = False if rolle == "Faenger" else True
            e.send(peer_mac, ujson.dumps({"type": "game_over", "won": won}))

            spiral_close(display)
            zeige_ergebnis(rolle, gefangen=False)
            return

        remaining = GAME_DURATION_MS - (jetzt - game_start)

        handle_incoming()

        # POWERUPS
        red = button_red.value()
        blue = button_blue.value()

        if last_red == 1 and red == 0 and used_red < 2:
            used_red += 1
            invis = jetzt + 3000

        if last_blue == 1 and blue == 0 and used_blue < 2:
            used_blue += 1
            speed = jetzt + 3000

        last_red = red
        last_blue = blue

        # ----------------------------------------
        # BEWEGUNG P1
        # ----------------------------------------
        delay_p1 = SPEED_BOOST_DELAY_MS if jetzt < speed else MOVE_DELAY_MS
        richtung_p1 = read_joystick_direction()

        if richtung_p1 and (jetzt - last_move_p1) >= delay_p1:
            nx, ny = p1_x, p1_y

            if richtung_p1 == "UP": ny -= 1
            if richtung_p1 == "DOWN": ny += 1
            if richtung_p1 == "LEFT": nx -= 1
            if richtung_p1 == "RIGHT": nx += 1

            if not kollision_wand(nx, ny, karte):
                p1_x, p1_y = nx, ny

                # SpeedBoost zweiter Schritt
                if jetzt < speed:
                    nx2, ny2 = p1_x, p1_y
                    if richtung_p1 == "UP": ny2 -= 1
                    if richtung_p1 == "DOWN": ny2 += 1
                    if richtung_p1 == "LEFT": nx2 -= 1
                    if richtung_p1 == "RIGHT": nx2 += 1
                    if not kollision_wand(nx2, ny2, karte):
                        p1_x, p1_y = nx2, ny2

            last_move_p1 = jetzt

        # ----------------------------------------
        # BEWEGUNG P2
        # ----------------------------------------
        if p2_dir and (jetzt - last_move_p2) >= MOVE_DELAY_MS:
            nx2, ny2 = p2_x, p2_y

            if p2_dir == "UP": ny2 -= 1
            if p2_dir == "DOWN": ny2 += 1
            if p2_dir == "LEFT": nx2 -= 1
            if p2_dir == "RIGHT": nx2 += 1

            if not kollision_wand(nx2, ny2, karte):
                p2_x, p2_y = nx2, ny2

            last_move_p2 = jetzt

        # ----------------------------------------
        # 🎯 FANG?
        # ----------------------------------------
        if p1_x == p2_x and p1_y == p2_y:

            mp3.pause()
            sleep(0.2)
            mp3.play_track(1, 2)

            won = True if rolle == "Faenger" else False
            e.send(peer_mac, ujson.dumps({"type":"game_over","won":won}))

            spiral_close(display)
            zeige_ergebnis(rolle, gefangen=True)
            return

        # ----------------------------------------
        # RENDER
        # ----------------------------------------
        display.clear()
        display.set_icon(karte).draw()
        display.plot(p2_x, p2_y, 1)

        if jetzt >= invis:
            display.plot(p1_x, p1_y, 1)

        display.draw()

        # ----------------------------------------
        # STATE AN SLAVE SENDEN
        # ----------------------------------------
        if jetzt - last_state_send >= 150:
            send_state(p1_x, p1_y, p2_x, p2_y, rolle, map_index, remaining)
            last_state_send = jetzt

        sleep(0.02)



# ---------------------------------------------------------
# ENDLOSER GAME LOOP
# ---------------------------------------------------------
while True:
    starte_spiel()
    warte_auf_restart()
