import tkinter as tk
import pygame
import threading
import subprocess
import ctypes
import sys
import time
import configparser
import os

# =========================
# ADMIN CHECK
# =========================
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, __file__, None, 1
    )
    sys.exit(0)

# =========================
# CONFIG (INI)
# =========================
CONFIG_FILE = "settings.ini"
config = configparser.ConfigParser()

bound_button = None

def load_config():
    global bound_button
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        if config.has_option("BINDING", "button"):
            bound_button = config.getint("BINDING", "button")

def save_config():
    if not config.has_section("BINDING"):
        config.add_section("BINDING")
    config.set("BINDING", "button", str(bound_button))
    with open(CONFIG_FILE, "w") as f:
        config.write(f)

# =========================
# GLOBAL STATE
# =========================
joy = None
listening = False
button_was_pressed = False
resetting = False
running = True

# =========================
# JOYSTICK INIT / REINIT
# =========================
def init_joystick():
    global joy
    try:
        pygame.joystick.quit()
        pygame.joystick.init()

        if pygame.joystick.get_count() == 0:
            joy = None
            status.set("❌ No wheel detected")
            return

        joy = pygame.joystick.Joystick(0)
        joy.init()
        status.set("🎮 Wheel active")
    except Exception:
        joy = None
        status.set("❌ Wheel initialization error")

# =========================
# USB RESET (FAST)
# =========================
def reset_wheel():
    global resetting
    if resetting:
        return

    resetting = True
    status.set("🔄 Resetting wheel...")

    ps = r'''
    $d = Get-PnpDevice | Where-Object {
        $_.FriendlyName -like "*Thrustmaster*" -or
        $_.FriendlyName -like "*T150*"
    }
    if ($d) {
        Disable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false
        Enable-PnpDevice  -InstanceId $d.InstanceId -Confirm:$false
    }
    '''

    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    init_joystick()
    status.set("✅ Reset complete")
    resetting = False

def reset_thread():
    threading.Thread(target=reset_wheel, daemon=True).start()

# =========================
# JOYSTICK LOOP (SAFE)
# =========================
def joystick_loop():
    global listening, button_was_pressed

    while running:
        if resetting or joy is None or not joy.get_init():
            pygame.event.pump()
            time.sleep(0.01)
            continue

        pygame.event.pump()

        # BIND MODE
        if listening:
            for i in range(joy.get_numbuttons()):
                if joy.get_button(i):
                    bind_button(i)
            time.sleep(0.01)
            continue

        # NORMAL MODE
        if bound_button is not None:
            pressed = joy.get_button(bound_button)

            if pressed and not button_was_pressed:
                reset_thread()
                button_was_pressed = True

            if not pressed:
                button_was_pressed = False

        time.sleep(0.005)

# =========================
# BIND HANDLING
# =========================
def bind_button(index):
    global bound_button, listening, button_was_pressed
    bound_button = index
    listening = False
    button_was_pressed = True
    save_config()
    status.set(f"🎯 Bound to wheel button #{index}")

def start_bind():
    global listening
    listening = True
    status.set("👉 Press the wheel button to bind")

# =========================
# UI / CLEAN EXIT
# =========================
def on_close():
    global running
    running = False
    root.destroy()

# =========================
# INIT
# =========================
pygame.init()
load_config()

root = tk.Tk()
root.title("LMU Thrustmaster Wheel Reset")
root.geometry("380x200")
root.resizable(False, False)
root.protocol("WM_DELETE_WINDOW", on_close)

tk.Button(
    root,
    text="🔄 Reset Wheel",
    height=2,
    command=reset_thread
).pack(pady=10)

tk.Button(
    root,
    text="🎮 Bind Wheel Button",
    command=start_bind
).pack()

status = tk.StringVar()

if bound_button is not None:
    status.set(f"🎯 Loaded binding: button #{bound_button}")
else:
    status.set("No button bound")

tk.Label(root, textvariable=status).pack(pady=12)

init_joystick()
threading.Thread(target=joystick_loop, daemon=True).start()

root.mainloop()
