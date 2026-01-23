# logic.py
import pygame
import subprocess
import configparser
import os
import time
import pyttsx3
import pythoncom
from PyQt6.QtCore import pyqtSignal, QThread, QMutex

CONFIG_FILE = "settings.ini"


class SpeakerThread(QThread):
    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        pythoncom.CoInitialize()
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 160)
            engine.setProperty('volume', 1.0)
            engine.say(self.text)
            engine.runAndWait()
        except:
            pass
        pythoncom.CoUninitialize()


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


class DeviceFinder:
    @staticmethod
    def get_thrustmaster_id():
        ps_find = r'''
        $d = Get-PnpDevice | Where-Object {
            ($_.FriendlyName -like "*Thrustmaster*" -or
             $_.FriendlyName -like "*T150*" -or
             $_.FriendlyName -like "*T300*" -or
             $_.FriendlyName -like "*TS-PC*" -or
             $_.FriendlyName -like "*T-GT*") -and 
             $_.Status -eq "OK"
        } | Select-Object -First 1
        if ($d) { Write-Output $d.InstanceId }
        '''
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_find],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            device_id = result.stdout.strip()
            return device_id if device_id else None
        except:
            return None


class ResetWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, device_id=None):
        super().__init__()
        self.device_id = device_id
        self.speaker = None

    def run(self):
        self.speaker = SpeakerThread("Resetting hardware")
        self.speaker.start()
        self.speaker.wait()

        target_id = self.device_id
        if not target_id:
            target_id = DeviceFinder.get_thrustmaster_id()

        if not target_id:
            self.finished.emit("❌ Error: Wheel not found")
            return

        time.sleep(0.3)
        ps_script = f'''
        Disable-PnpDevice -InstanceId "{target_id}" -Confirm:$false
        Start-Sleep -Milliseconds 200
        Enable-PnpDevice  -InstanceId "{target_id}" -Confirm:$false
        '''
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.finished.emit("✅ USB Cycle Done. Waiting for signal...")
        except Exception as e:
            self.finished.emit(f"❌ PowerShell Error: {str(e)}")


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
        self.cached_device_id = None

        self.waiting_for_reconnect = False
        self.speaker_thread = None

    def stop(self):
        self.running = False
        self.wait()

    def set_binding_mode(self, active: bool):
        self.mutex.lock()
        self.binding_mode = active
        self.mutex.unlock()

    def pause(self):
        self.mutex.lock()
        self.paused = True
        self.mutex.unlock()
        time.sleep(0.2)

    def resume(self):
        self.mutex.lock()
        self.paused = False

        self.waiting_for_reconnect = True
        self.mutex.unlock()

    def get_device_id(self):
        return self.cached_device_id

    def _close_joystick(self):
        if pygame.joystick.get_init():
            pygame.joystick.quit()
        self.joy = None

    def _init_joystick(self):
        try:
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            if not pygame.display.get_init():
                pygame.display.init()

            if pygame.joystick.get_count() > 0:
                self.joy = pygame.joystick.Joystick(0)
                self.joy.init()
                return True
        except Exception:
            pass
        return False

    def run(self):
        pygame.init()
        self.cached_device_id = DeviceFinder.get_thrustmaster_id()

        if self._init_joystick():
            self.status_update.emit(f"🎮 Ready: {self.joy.get_name()}")
        else:
            self.status_update.emit("⚠️ No Wheel Detected")

        while self.running:
            self.mutex.lock()
            is_paused = self.paused
            self.mutex.unlock()

            if is_paused:
                if pygame.joystick.get_init():
                    self._close_joystick()
                    self.status_update.emit("⏸️ Waiting for USB...")
                time.sleep(0.1)
                continue

            if self.joy is None or not pygame.joystick.get_init():
                if self._init_joystick():
                    dev_name = self.joy.get_name()
                    self.status_update.emit(f"🎮 Reconnected: {dev_name}")

                    if self.waiting_for_reconnect:
                        self.waiting_for_reconnect = False  # Reset flag

                        msg = "Reset Complete. Press FFB Reset in LMU now."
                        self.speaker_thread = SpeakerThread(msg)
                        self.speaker_thread.start()

                    if not self.cached_device_id:
                        self.cached_device_id = DeviceFinder.get_thrustmaster_id()

                    time.sleep(1)
                else:
                    time.sleep(0.5)
                    continue

            # Input Loop
            try:
                pygame.event.pump()
            except:
                self._close_joystick()
                continue

            if self.binding_mode:
                for i in range(self.joy.get_numbuttons()):
                    if self.joy.get_button(i):
                        self.config_manager.save(i)
                        self.binding_complete.emit(i)
                        self.set_binding_mode(False)
                        break
                time.sleep(0.05)
                continue

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
                    self._close_joystick()

            time.sleep(0.01)

        pygame.quit()