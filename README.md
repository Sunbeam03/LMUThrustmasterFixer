# 🏎️ LMU Thrustmaster FFB Resetter

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg) ![Python](https://img.shields.io/badge/python-3.9+-yellow.svg) ![Platform](https://img.shields.io/badge/platform-Windows-0078D6.svg)

A modern, standalone utility designed to fix **Force Feedback (FFB) loss** in **Le Mans Ultimate (LMU)** and other sim-racing titles for Thrustmaster wheels. 

It works by programmatically resetting the USB driver stack for the wheel without physically unplugging it, allowing the game to regain control.

---

## 🧐 The Problem
In *Le Mans Ultimate*, a known bug causes the Force Feedback to completely cut out during a race. This usually happens when the USB communication hangs.
- **Simply resetting FFB in-game often fails** because the driver itself is unresponsive.
- **Unplugging the USB** works, but is dangerous and slow mid-race.

## 💡 The Solution (The 2-Step Fix)
This tool enables a safe, two-step recovery process that takes less than 5 seconds while driving.

### ⚠️ IMPORTANT: The Workflow
To successfully restore FFB, you must perform these two steps in order:

1.  **Step 1: Hardware Reset (THIS APP)**
    * Press the button you bound on your wheel using this app.
    * *Result:* The USB device restarts. You will hear the Windows disconnect/connect sound. The wheel may auto-calibrate briefly.
    
2.  **Step 2: Software Reset (IN-GAME)**
    * Go to **Le Mans Ultimate Settings → Controls**.
    * Bind a button (keyboard or a different wheel button) to **"Reset FFB"**.
    * Press this button **AFTER** Step 1 is complete.
    * *Result:* The game detects the re-connected wheel and re-initializes the physics.

---

## 🛠️ Requirements

* **OS:** Windows 10 or 11 (Administrator privileges required)
* **Hardware:** Thrustmaster Wheel (T150, T300, T-GT, TS-PC, TS-XW)
* **Software:** Python 3.x

## 📦 Installation

1.  **Clone or Download** this repository.
2.  Open a terminal in the folder.
3.  Install the required dependencies:

```bash
pip install PyQt6 pygame