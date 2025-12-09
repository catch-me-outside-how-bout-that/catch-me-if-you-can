# “Catch Me If You Can” – ESP32 Retro Chase Game

## Project Overview
**Catch Me If You Can** is a self-built 2D chase game inspired by the classic playground game *Fangis*.  
It runs on an **ESP32 microcontroller** using **MicroPython** and is displayed on an **8×8 LED matrix** (HT16K33 or NeoPixel version).

Players move their character via a **joystick** and activate special abilities using a **dual-button module**.  
The game is fully portable thanks to a **3.7V Li-Ion battery** and a **custom 3D-printed enclosure**.

---

## Gameplay Overview

The game takes place on a **top-down 8×8 arena** where two players compete as:

- **Hunter (Fänger)** → tries to catch the Runner  
- **Runner (Wegrenner)** → tries to escape until the timer expires  

Movement is pixel-based and controlled using the joystick.  
Random obstacles add strategic depth, and special abilities such as **Speed Boost** and **Invisibility** make each round dynamic and competitive.

---

## Hardware Components

- **ESP32 Dev Board** (MicroPython compatible)  
- **8×8 LED Matrix** (HT16K33 or WS2812 NeoPixel version)  
- **Joystick A06-05 TZT** for directional control  
- **M5Stack Dual-Button Unit** (red + blue) for abilities  
- **DFPlayer Mini + speaker** for background music & sound effects  
- **3.7V Li-Ion 500 mAh battery** for mobile power  
- **Custom PLA 3D-printed enclosure**  
- Optional: **ESP-NOW wireless communication** for 2-player mode  

---

## How to Play

### 1. Starting the Game
To begin a new round:

**Press and hold both buttons (red + blue) for 3 seconds.**  
This triggers the start sequence.

### 2. Role Assignment
The LED matrix will display your assigned role:

- 🔴 **Red icon → Hunter**  
- 🔵 **Blue icon → Runner**

### 3. Objectives
#### If you are the Hunter:
- Reach the **exact same position** as the Runner.  
- If you catch the Runner → **Hunter wins**.

#### If you are the Runner:
- Avoid the Hunter until the **2-minute timer** expires.  
- If time runs out → **Runner wins**.

Special abilities (Speed Boost & Invisibility) can be activated with the dual-button module and are shown on the display.

---

# How to Build
## Hardware Wiring

![bildneuneu](https://github.com/user-attachments/assets/e0bd7616-38f6-4fc3-8fda-9cf41c8ec317)

### Main Wiring Summary

| Component | Pins / Connection |
|----------|-------------------|
| **HT16K33 LED Matrix** | SDA → GPIO 21, SCL → GPIO 22, VCC 5V, GND |
| **Joystick A06-05** | VRX → GPIO 3, VRY → GPIO 4, VCC 3.3V, GND |
| **Red Button** | Connected to Modulino **A0** |
| **Blue Button** | Connected to Modulino **A1** |
| **DFPlayer Mini** | RX → ESP32 TX, TX → ESP32 RX, VCC 5V, GND |
| **Speaker** | SPK+ / SPK− on DFPlayer |
| **Battery** | 3.7V → boost to 5V (optional), or USB power |

---

## Uploading the Code

1. Install **MicroPython** on the ESP32.  
2. Connect the ESP32 via USB.  
3. Copy all files from the `src/` folder to the board.  
4. Make sure the following libraries are present on the device:  
   - `dfplayer.py`  
   - `ht16k33.py`  
   - `espnow` (built-in on ESP32 MicroPython)  
5. Reset the board — the game starts automatically.

---
# Code



