# logic.py
import pygame
import subprocess
import configparser
import os
import time
from PyQt6.QtCore import pyqtSignal, QThread, QMutex, QWaitCondition

CONFIG_FILE = "settings.ini"


class ConfigManager:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.bound_button = None
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            self.config.read(CONFIG_FILE)
            if self.config.has_option("BINDING", "button"):
                try:
                    self.bound_button = self.config.getint("BINDING", "button")
                except ValueError:
                    self.bound_button = None

    def save(self, button_index):
        if not self.config.has_section("BINDING"):
            self.config.add_section("BINDING")
        self.config.set("BINDING", "button", str(button_index))
        with open(CONFIG_FILE, "w") as f:
            self.config.write(f)
        self.bound_button = button_index


class ResetWorker(QThread):
    finished = pyqtSignal(str)

    def run(self):
        # 1. Wait a tiny bit to ensure Pygame has released the handle
        time.sleep(0.5)

        ps_script = r'''
        $d = Get-PnpDevice | Where-Object {
            $_.FriendlyName -like "*Thrustmaster*" -or
            $_.FriendlyName -like "*T150*" -or
            $_.FriendlyName -like "*T300*" -or
            $_.FriendlyName -like "*TS-PC*" -or
            $_.FriendlyName -like "*T-GT*"
        }
        if ($d) {
            Disable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false
            Start-Sleep -Seconds 1
            Enable-PnpDevice  -InstanceId $d.InstanceId -Confirm:$false
        }
        '''
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.finished.emit("✅ Device Reset Complete")
        except Exception as e:
            self.finished.emit(f"❌ Reset Failed: {str(e)}")


class JoystickMonitor(QThread):
    status_update = pyqtSignal(str)
    button_triggered = pyqtSignal()
    binding_complete = pyqtSignal(int)

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.running = True
        self.paused = False
        self.binding_mode = False
        self.joy = None
        self.button_was_pressed = False
        self.mutex = QMutex()

    def stop(self):
        self.running = False
        self.wait()

    def set_binding_mode(self, active: bool):
        self.mutex.lock()
        self.binding_mode = active
        self.mutex.unlock()

    def pause(self):
        """Releases the joystick handle safely."""
        self.mutex.lock()
        self.paused = True
        self.mutex.unlock()
        # We wait briefly to ensure the loop cycle finishes
        time.sleep(0.2)

    def resume(self):
        """Re-enables joystick monitoring."""
        self.mutex.lock()
        self.paused = False
        self.mutex.unlock()

    def _close_joystick(self):
        """Helper to fully quit pygame joystick subsystem."""
        if pygame.joystick.get_init():
            pygame.joystick.quit()
        self.joy = None

    def _init_joystick(self):
        """Helper to init pygame joystick subsystem."""
        try:
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            if not pygame.display.get_init():
                pygame.display.init()  # Sometimes needed for event pumping

            if pygame.joystick.get_count() > 0:
                self.joy = pygame.joystick.Joystick(0)
                self.joy.init()
                return True
        except Exception:
            pass
        return False

    def run(self):
        # Initial Init
        pygame.init()
        if self._init_joystick():
            self.status_update.emit(f"🎮 Connected: {self.joy.get_name()}")
        else:
            self.status_update.emit("⚠️ No Wheel Detected")

        while self.running:
            self.mutex.lock()
            is_paused = self.paused
            self.mutex.unlock()

            # --- PAUSED STATE (During Reset) ---
            if is_paused:
                # If we are paused, we must ensure Pygame is CLOSED
                # so PowerShell can touch the driver.
                if pygame.joystick.get_init():
                    self._close_joystick()
                    self.status_update.emit("⏸️ Monitor Paused (Resetting...)")

                time.sleep(0.5)
                continue

            # --- ACTIVE STATE ---
            # Try to reconnect if joy is None
            if self.joy is None or not pygame.joystick.get_init():
                if self._init_joystick():
                    self.status_update.emit(f"🎮 Reconnected: {self.joy.get_name()}")
                    time.sleep(1)
                else:
                    # Keep trying slowly
                    time.sleep(1)
                    continue

            # Event Pump
            try:
                pygame.event.pump()
            except Exception:
                # If pump fails, device might be lost
                self._close_joystick()
                continue

            # --- Binding Logic ---
            if self.binding_mode:
                for i in range(self.joy.get_numbuttons()):
                    if self.joy.get_button(i):
                        self.config_manager.save(i)
                        self.binding_complete.emit(i)
                        self.set_binding_mode(False)
                        break
                time.sleep(0.05)
                continue

            # --- Monitoring Logic ---
            bound_btn = self.config_manager.bound_button
            if bound_btn is not None and bound_btn < self.joy.get_numbuttons():
                try:
                    pressed = self.joy.get_button(bound_btn)

                    if pressed and not self.button_was_pressed:
                        self.button_triggered.emit()
                        self.button_was_pressed = True

                    if not pressed:
                        self.button_was_pressed = False
                except:
                    # Button read failed
                    self._close_joystick()

            time.sleep(0.01)

        pygame.quit()