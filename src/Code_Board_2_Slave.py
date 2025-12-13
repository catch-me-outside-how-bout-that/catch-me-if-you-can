from time import sleep, time
from machine import Pin, ADC
import neopixel
import network
import espnow
import ujson

def jetzt_ms():
    return int(time() * 1000)

# ---- Joystick ----
vrx = ADC(Pin(3), atten=ADC.ATTN_11DB)
vry = ADC(Pin(4), atten=ADC.ATTN_11DB)

CENTER_X = 1940
CENTER_Y = 1895
DEADZONE = 200
MOVE_DELAY_MS = 120

# ---- Maps ----
maps = [
    b"\x00\x66\x42\x58\x0b\x20\x6e\x00",
    b"\x00\x6e\x42\x10\x70\x06\x22\x30",
    b"\x10\x18\x4a\x63\x32\x00\x2c\x20",
    b"\x00\x46\x6c\x20\x22\x0a\x7a\x00"
]

# ---- Buttons ----
button_red = Pin("A0", Pin.IN, Pin.PULL_UP)
button_blue = Pin("A1", Pin.IN, Pin.PULL_UP)

# ---------------------------------------------------------
# NEOPIXEL 8x8 MATRIX (wie Master)
# ---------------------------------------------------------

class NeoPixelMatrix8x8:
    def __init__(self, pin_name="D5", width=8, height=8, base_brightness=0.25):
        self.width = width
        self.height = height
        self.base_brightness = base_brightness
        pin = Pin(pin_name, Pin.OUT)
        self.np = neopixel.NeoPixel(pin, width * height)
        self.buffer = [(0, 0, 0)] * (width * height)

    def _index(self, x, y):
        """
        Logische Koordinaten:
        x: 0..7 (links -> rechts)
        y: 0..7 (oben -> unten)

        Hardware-Layout:
        - Index 0 unten links
        - läuft Reihe für Reihe von unten nach oben
        - jeweils von links nach rechts
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            return None
        row_from_bottom = 7 - y   # y=7 -> row 0 (unten)
        col_from_left = x        # x=0 -> links
        return row_from_bottom * self.width + col_from_left

    def clear(self):
        for i in range(self.width * self.height):
            self.buffer[i] = (0, 0, 0)

    def draw(self):
        """
        Schreibt den Buffer auf die Matrix.
        Limitiert die Gesamthelligkeit so, dass effektiv
        max. ~15 LEDs auf Vollgas entsprechen.
        """
        lit = 0
        for (r, g, b) in self.buffer:
            if r or g or b:
                lit += 1

        scale_lit = 1.0
        if lit > 15:
            scale_lit = 15.0 / float(lit)

        for i, (r, g, b) in enumerate(self.buffer):
            br = self.base_brightness * scale_lit
            self.np[i] = (int(r * br), int(g * br), int(b * br))
        self.np.write()

    def plot(self, x, y, val=1, color=(40, 40, 40)):
        idx = self._index(x, y)
        if idx is None:
            return
        if val:
            self.buffer[idx] = color
        else:
            self.buffer[idx] = (0, 0, 0)

    def set_icon(self, map_bytes, color=(20, 20, 0)):
        """
        Zeichnet die Wände analog zu kollision_wand().
        """
        self.clear()
        for x in range(8):
            for y in range(8):
                if not (0 <= x <= 7 and 0 <= y <= 7):
                    continue
                if kollision_wand(x, y, map_bytes):
                    self.plot(x, y, 1, color)
        return self

    def fill(self, color):
        for i in range(self.width * self.height):
            self.buffer[i] = color

# ---- 5V-Levelshift für G0-Port aktivieren ----
level_shift = Pin("D4", Pin.OUT)
level_shift.on()

# ---- Display-Instanz ----
display = NeoPixelMatrix8x8(pin_name="D5")

# ---------------------------------------------------------
# ESP-NOW CLIENT SETUP
# ---------------------------------------------------------
w = network.WLAN(network.STA_IF)
w.active(True)

e = espnow.ESPNow()
e.active(True)

# MAC VON BOARD 1 EINTRAGEN!
peer_mac_master = b'\xec\xda;a\\\xa4'
try:
    e.add_peer(peer_mac_master)
except OSError:
    pass  # immer ignorieren

# ---------------------------------------------------------
# HELFER: Kollision / Spiral / Joystick
# ---------------------------------------------------------

def kollision_wand(x, y, map_bytes):
    if x < 0 or x > 7 or y < 0 or y > 7:
        return True
    log_x = 7 - y
    log_y = x
    bit_mask = 1 << (7 - log_x)
    return (map_bytes[log_y] & bit_mask) != 0

def spiral_close(display_obj):
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
    display_obj.clear()
    for x, y in coords:
        display_obj.plot(x, y, 1, color=(0, 40, 0))
        display_obj.draw()
        sleep(0.03)

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

# ---------------------------------------------------------
# SPIEL-STATE CLIENT
# ---------------------------------------------------------

rolle = "Warte..."
map_index = 0
karte = maps[0]

p1_x = p1_y = 0
p2_x = p2_y = 0
remaining_ms = 120000
p1_visible = True
p2_visible = True

# ---------------------------------------------------------
# STARTSCREEN
# ---------------------------------------------------------

def warte_auf_start():
    global rolle, map_index, karte

    # "Warte auf Start" → pulsierender Rahmen
    display.clear()
    display.draw()

    last_blink = 0
    frame_on = False

    while True:
        # kleine Rahmenanimation
        jetzt = jetzt_ms()
        if jetzt - last_blink > 250:
            last_blink = jetzt
            frame_on = not frame_on
            display.clear()
            if frame_on:
                col = (8, 8, 8)
                for x in range(8):
                    display.plot(x, 0, 1, col)
                    display.plot(x, 7, 1, col)
                for y in range(1, 7):
                    display.plot(0, y, 1, col)
                    display.plot(7, y, 1, col)
            display.draw()

        recv = e.recv()
        if not recv:
            sleep(0.05)
            continue

        mac, msg = recv
        if not msg:
            continue

        try:
            data = ujson.loads(msg.decode())
        except:
            continue

        if data.get("type") == "start":
            rolle = data["role_for_peer"]
            map_index = data["map_index"]
            karte = maps[map_index]
          
            display.clear()
            # Fänger = blau, Wegrenner = rot
            color = (0, 0, 80) if rolle == "Faenger" else (80, 0, 0)

            for phase in range(4):
                display.clear()
                for x in range(8):
                    for y in range(8):
                        if (x + y + phase) % 2 == 0:
                            display.plot(x, y, 1, color)
                display.draw()
                sleep(0.12)

            # Kurz Startposition anzeigen
            display.clear()
            if rolle == "Faenger":
                display.plot(7, 7, 1, color)
            else:
                display.plot(0, 0, 1, color)
            display.draw()
            sleep(0.5)

            display.clear()
            display.draw()
            return

# ---------------------------------------------------------
# MAIN GAME LOOP
# ---------------------------------------------------------

def starte_client_game():
    global p1_x, p1_y, p2_x, p2_y, rolle, map_index, karte, remaining_ms, p1_visible, p2_visible
  
    p1_visible = True #reset zu beginn der runde
    p2_visible = True

    while True:

        # --- Eingaben senden ---
        dir_str = read_joystick_direction()
        red_button = button_red.value()
        blue_button = button_blue.value()
      
        use_red = 1 if red_button == 0 else 0
        use_blue = 1 if blue_button == 0 else 0

        packet = {
          "type": "input", 
          "dir": dir_str, 
          "red": red_button,
          "blue": blue_button,
          "use_red": use_red,
          "use_blue": use_blue
        }
        try:
            e.send(peer_mac_master, ujson.dumps(packet))
        except:
            pass

        # --- Pakete vom Master empfangen ---
        recv = e.recv()
        if recv:
            mac, msg = recv
            if msg:
                try:
                    data = ujson.loads(msg.decode())
                except:
                    data = {}

                # ---------- STATE UPDATE ----------
                if data.get("type") == "state":
                    p1_x = data["p1_x"]
                    p1_y = data["p1_y"]
                    p2_x = data["p2_x"]
                    p2_y = data["p2_y"]
                    rolle = data["role_for_peer"]
                    map_index = data["map_index"]
                    karte = maps[map_index]
                    remaining_ms = data["remaining_ms"]
                    p1_visible = data.get("p1_visible", True)
                    p2_visible = data.get("p2_visible", True)

                # ---------- GAME OVER ----------
                if data.get("type") == "game_over":

                    display.clear()
                    display.draw()
                    sleep(0.1)

                    # Spiral-Animation wie Board 1
                    spiral_close(display)

                    # Master teilt mit, ob ER gewonnen hat.
                    master_won = bool(data.get("won"))
                    client_won = not master_won  # Client (dieses Board) hat gewonnen, wenn Master verloren hat

                    col = (0, 60, 0) if client_won else (60, 0, 0)

                    for _ in range(4):
                        display.fill(col)
                        display.draw()
                        sleep(0.25)
                        display.clear()
                        display.draw()
                        sleep(0.2)

                    sleep(0.5)
                    return   # zurück in Warte-Menü

                # --- Render Frame ---
        display.set_icon(karte, color=(15, 15, 0))  # Wände

        if rolle == "Faenger":
            color_self  = (0, 0, 60)
            color_other = (60, 0, 0)
        else:
            color_self  = (60, 0, 0)
            color_other = (0, 0, 60)

        if p1_visible:
            display.plot(p1_x, p1_y, 1, color=color_other)
        if p2_visible:
            display.plot(p2_x, p2_y, 1, color=color_self)

        display.draw()
        sleep(0.02)

# ---------------------------------------------------------
# PROGRAM FLOW
# ---------------------------------------------------------

while True:
    warte_auf_start()
    starte_client_game()
