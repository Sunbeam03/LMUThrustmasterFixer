# logic.py
import subprocess
import configparser
import os
import time
import pyttsx3
import pythoncom
import ctypes
from PyQt6.QtCore import pyqtSignal, QThread, QMutex

CONFIG_FILE = "settings.ini"

# ── Windows API setup ─────────────────────────────────────────────────────────
hid      = ctypes.WinDLL("hid")
setupapi = ctypes.WinDLL("setupapi")
kernel32 = ctypes.WinDLL("kernel32")

# CRITICAL: every function that accepts or returns a HANDLE must declare
# restype/argtypes as c_void_p. Without this ctypes truncates 64-bit handles
# to 32-bit, causing silent ERROR_INVALID_HANDLE failures on 64-bit Windows.
setupapi.SetupDiGetClassDevsW.restype              = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes             = [ctypes.c_void_p, ctypes.c_wchar_p,
                                                       ctypes.c_void_p, ctypes.c_uint]
setupapi.SetupDiEnumDeviceInterfaces.argtypes      = [ctypes.c_void_p, ctypes.c_void_p,
                                                       ctypes.c_void_p, ctypes.c_uint,
                                                       ctypes.c_void_p]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                       ctypes.c_void_p, ctypes.c_uint,
                                                       ctypes.c_void_p, ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes     = [ctypes.c_void_p]
kernel32.CreateFileW.restype                       = ctypes.c_void_p
kernel32.CloseHandle.argtypes                      = [ctypes.c_void_p]
kernel32.ReadFile.argtypes                         = [ctypes.c_void_p, ctypes.c_void_p,
                                                       ctypes.c_uint, ctypes.c_void_p,
                                                       ctypes.c_void_p]
kernel32.CreateEventW.restype                      = ctypes.c_void_p
kernel32.CreateEventW.argtypes                     = [ctypes.c_void_p, ctypes.c_bool,
                                                       ctypes.c_bool, ctypes.c_wchar_p]
kernel32.WaitForSingleObject.restype               = ctypes.c_uint
kernel32.WaitForSingleObject.argtypes              = [ctypes.c_void_p, ctypes.c_uint]
kernel32.GetOverlappedResult.restype               = ctypes.c_bool
kernel32.GetOverlappedResult.argtypes              = [ctypes.c_void_p, ctypes.c_void_p,
                                                       ctypes.c_void_p, ctypes.c_bool]
kernel32.ResetEvent.argtypes                       = [ctypes.c_void_p]
kernel32.CancelIo.argtypes                         = [ctypes.c_void_p]
hid.HidD_GetHidGuid.argtypes                       = [ctypes.c_void_p]
hid.HidD_GetAttributes.argtypes                    = [ctypes.c_void_p, ctypes.c_void_p]
hid.HidD_GetProductString.argtypes                 = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
hid.HidD_GetPreparsedData.argtypes                 = [ctypes.c_void_p, ctypes.c_void_p]
hid.HidD_FreePreparsedData.argtypes                = [ctypes.c_void_p]
hid.HidP_GetCaps.argtypes                          = [ctypes.c_void_p, ctypes.c_void_p]
hid.HidP_GetUsages.argtypes                        = [ctypes.c_uint, ctypes.c_ushort,
                                                       ctypes.c_ushort, ctypes.c_void_p,
                                                       ctypes.c_void_p, ctypes.c_void_p,
                                                       ctypes.c_void_p, ctypes.c_uint]

GENERIC_READ          = 0x80000000
GENERIC_WRITE         = 0x40000000
FILE_SHARE_READ       = 0x00000001
FILE_SHARE_WRITE      = 0x00000002
FILE_FLAG_OVERLAPPED  = 0x40000000
WAIT_OBJECT_0         = 0x00000000
WAIT_TIMEOUT          = 0x00000102
ERROR_IO_PENDING      = 997
OPEN_EXISTING         = 3
INVALID_HANDLE_VALUE  = ctypes.c_void_p(-1).value
DIGCF_PRESENT         = 0x02
DIGCF_DEVICEINTERFACE = 0x10
THRUSTMASTER_VID      = 0x044F
CB_SIZE               = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6

# HID Usage Page / Usage for a joystick (used to pick the right interface)
HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_JOYSTICK     = 0x04
HID_USAGE_GAMEPAD      = 0x05

class OVERLAPPED(ctypes.Structure):
    class _U(ctypes.Union):
        class _S(ctypes.Structure):
            _fields_ = [("Offset", ctypes.c_uint), ("OffsetHigh", ctypes.c_uint)]
        _fields_ = [("s", _S), ("Pointer", ctypes.c_void_p)]
    _fields_ = [("Internal",     ctypes.c_void_p),
                ("InternalHigh", ctypes.c_void_p),
                ("u",            _U),
                ("hEvent",       ctypes.c_void_p)]

# ── ctypes structures ─────────────────────────────────────────────────────────

class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong),
                ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8)]

class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize",             ctypes.c_uint),
                ("InterfaceClassGuid", GUID),
                ("Flags",              ctypes.c_uint),
                ("Reserved",           ctypes.POINTER(ctypes.c_ulong))]

class SP_DEVICE_INTERFACE_DETAIL_DATA(ctypes.Structure):
    _fields_ = [("cbSize",     ctypes.c_uint),
                ("DevicePath", ctypes.c_wchar * 256)]

class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size",          ctypes.c_ulong),
                ("VendorID",      ctypes.c_ushort),
                ("ProductID",     ctypes.c_ushort),
                ("VersionNumber", ctypes.c_ushort)]

class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage",                     ctypes.c_ushort),
        ("UsagePage",                 ctypes.c_ushort),
        ("InputReportByteLength",     ctypes.c_ushort),
        ("OutputReportByteLength",    ctypes.c_ushort),
        ("FeatureReportByteLength",   ctypes.c_ushort),
        ("Reserved",                  ctypes.c_ushort * 17),
        ("NumberLinkCollectionNodes", ctypes.c_ushort),
        ("NumberInputButtonCaps",     ctypes.c_ushort),
        ("NumberInputValueCaps",      ctypes.c_ushort),
        ("NumberInputDataIndices",    ctypes.c_ushort),
        ("NumberOutputButtonCaps",    ctypes.c_ushort),
        ("NumberOutputValueCaps",     ctypes.c_ushort),
        ("NumberOutputDataIndices",   ctypes.c_ushort),
        ("NumberFeatureButtonCaps",   ctypes.c_ushort),
        ("NumberFeatureValueCaps",    ctypes.c_ushort),
        ("NumberFeatureDataIndices",  ctypes.c_ushort),
    ]

# ── HID helpers ───────────────────────────────────────────────────────────────

def _open_handle(path, overlapped=False):
    """Try read/write then read-only. Returns handle or None."""
    flags = FILE_FLAG_OVERLAPPED if overlapped else 0
    handle = kernel32.CreateFileW(
        path, GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None, OPEN_EXISTING, flags, None
    )
    if not handle or handle == INVALID_HANDLE_VALUE:
        handle = kernel32.CreateFileW(
            path, GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, flags, None
        )
    if not handle or handle == INVALID_HANDLE_VALUE:
        return None
    return handle


def _get_hid_caps(handle):
    """Returns HIDP_CAPS for an open handle, or None on failure."""
    preparsed = ctypes.c_void_p()
    if not hid.HidD_GetPreparsedData(handle, ctypes.byref(preparsed)):
        return None
    caps = HIDP_CAPS()
    hid.HidP_GetCaps(preparsed, ctypes.byref(caps))
    hid.HidD_FreePreparsedData(preparsed)
    return caps


def find_thrustmaster_devices():
    """
    Returns list of (device_path, product_name) for connected Thrustmaster
    HID interfaces that report as a joystick or gamepad (Usage Page 0x01,
    Usage 0x04 or 0x05). This filters out sub-collection interfaces that
    would cause duplicate button events.
    """
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))

    hdev = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    )
    if not hdev or hdev == INVALID_HANDLE_VALUE:
        return []

    results = []
    iface = SP_DEVICE_INTERFACE_DATA()
    iface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
    index = 0

    while setupapi.SetupDiEnumDeviceInterfaces(
            hdev, None, ctypes.byref(guid), index, ctypes.byref(iface)):
        index += 1

        detail = SP_DEVICE_INTERFACE_DETAIL_DATA()
        detail.cbSize = CB_SIZE
        req = ctypes.c_ulong(0)
        setupapi.SetupDiGetDeviceInterfaceDetailW(
            hdev, ctypes.byref(iface),
            ctypes.byref(detail), ctypes.sizeof(detail),
            ctypes.byref(req), None
        )

        handle = _open_handle(detail.DevicePath)
        if handle is None:
            continue

        attrs = HIDD_ATTRIBUTES()
        attrs.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
        hid.HidD_GetAttributes(handle, ctypes.byref(attrs))

        if attrs.VendorID == THRUSTMASTER_VID:
            # Only keep the top-level joystick/gamepad interface,
            # not sub-collections (keyboard, consumer control, etc.)
            caps = _get_hid_caps(handle)
            if caps and caps.UsagePage == HID_USAGE_PAGE_GENERIC and \
               caps.Usage in (HID_USAGE_JOYSTICK, HID_USAGE_GAMEPAD):
                buf = ctypes.create_unicode_buffer(128)
                hid.HidD_GetProductString(handle, buf, ctypes.sizeof(buf))
                results.append((detail.DevicePath, buf.value or "Thrustmaster Device"))

        kernel32.CloseHandle(handle)

    setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return results


# ── ThrustmasterHID ───────────────────────────────────────────────────────────

class ThrustmasterHID:
    """
    Opens a Thrustmaster HID joystick interface with FILE_FLAG_OVERLAPPED so
    that read_buttons() can time out and return None instead of blocking forever.
    This allows the monitor thread to check self.running and exit cleanly.
    """

    def __init__(self, path):
        self.path      = path
        self.handle    = None
        self.event     = None   # manual-reset event for OVERLAPPED reads
        self.name      = "Thrustmaster Wheel"
        self.preparsed = None
        self.report_len = 0
        self._connect()

    def _connect(self):
        # Open with FILE_FLAG_OVERLAPPED so ReadFile never blocks permanently
        self.handle = _open_handle(self.path, overlapped=True)
        if not self.handle:
            return

        # Create a manual-reset event for overlapped I/O
        self.event = kernel32.CreateEventW(None, True, False, None)
        if not self.event:
            self.close()
            return

        # Cache preparsed data and report length up front
        preparsed = ctypes.c_void_p()
        if hid.HidD_GetPreparsedData(self.handle, ctypes.byref(preparsed)):
            caps = HIDP_CAPS()
            hid.HidP_GetCaps(preparsed, ctypes.byref(caps))
            self.report_len = caps.InputReportByteLength
            self.preparsed  = preparsed
        else:
            self.close()
            return

        buf = ctypes.create_unicode_buffer(128)
        hid.HidD_GetProductString(self.handle, buf, ctypes.sizeof(buf))
        if buf.value:
            self.name = buf.value

    def close(self):
        if self.handle:
            kernel32.CancelIo(self.handle)
            kernel32.CloseHandle(self.handle)
            self.handle = None
        if self.event:
            kernel32.CloseHandle(self.event)
            self.event = None
        if self.preparsed:
            hid.HidD_FreePreparsedData(self.preparsed)
            self.preparsed = None

    def is_open(self):
        return self.handle is not None

    def read_buttons(self, timeout_ms=200):
        """
        Reads one HID input report using overlapped I/O with a timeout.
        Returns a button bitmask, 0 if no buttons pressed, or None on failure.
        Returning None means the device is gone or the handle was closed.
        """
        if not self.is_open():
            return None

        buf       = ctypes.create_string_buffer(self.report_len)
        ov        = OVERLAPPED()
        ov.hEvent = self.event
        kernel32.ResetEvent(self.event)

        bytes_read = ctypes.c_ulong(0)
        ok = kernel32.ReadFile(self.handle, buf, self.report_len, None, ctypes.byref(ov))
        err = ctypes.GetLastError()

        if not ok and err != ERROR_IO_PENDING:
            # Real error — device gone
            return None

        # Wait up to timeout_ms for data to arrive
        wait = kernel32.WaitForSingleObject(self.event, timeout_ms)

        if wait == WAIT_TIMEOUT:
            # No data yet — cancel and return empty (not an error)
            kernel32.CancelIo(self.handle)
            return 0

        if wait != WAIT_OBJECT_0:
            return None

        if not kernel32.GetOverlappedResult(self.handle, ctypes.byref(ov),
                                             ctypes.byref(bytes_read), False):
            return None

        HIDP_INPUT            = 0
        HID_USAGE_PAGE_BUTTON = 0x09
        usage_len = ctypes.c_ulong(128)
        usages    = (ctypes.c_ushort * 128)()

        ret = hid.HidP_GetUsages(
            HIDP_INPUT, HID_USAGE_PAGE_BUTTON, 0,
            usages, ctypes.byref(usage_len),
            self.preparsed, buf, bytes_read.value
        )

        HIDP_STATUS_SUCCESS = 0x00110000
        if ret != HIDP_STATUS_SUCCESS:
            return 0

        bitmask = 0
        for i in range(usage_len.value):
            btn = usages[i]
            if btn > 0:
                bitmask |= (1 << (btn - 1))
        return bitmask


# ── SpeakerThread ─────────────────────────────────────────────────────────────

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
        except Exception:
            pass
        finally:
            pythoncom.CoUninitialize()


# ── ConfigManager ─────────────────────────────────────────────────────────────

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


# ── DeviceFinder ──────────────────────────────────────────────────────────────

class DeviceFinder:
    @staticmethod
    def get_thrustmaster_id():
        ps_find = r'''
        $d = Get-PnpDevice | Where-Object {
            ($_.FriendlyName -like "*Thrustmaster*" -or
             $_.FriendlyName -like "*TMX*" -or
             $_.FriendlyName -like "*T150*" -or
             $_.FriendlyName -like "*T300*" -or
             $_.FriendlyName -like "*TS-PC*" -or
             $_.FriendlyName -like "*T-GT*" -or
             ($_.InstanceId -like "USB\VID_044F*")) -and
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
        except Exception:
            return None


# ── ResetWorker ───────────────────────────────────────────────────────────────

class ResetWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, device_id=None):
        super().__init__()
        self.device_id = device_id

    def run(self):
        speaker = SpeakerThread("Resetting hardware")
        speaker.start()
        speaker.wait()

        target_id = self.device_id or DeviceFinder.get_thrustmaster_id()
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


# ── JoystickMonitor ───────────────────────────────────────────────────────────

class JoystickMonitor(QThread):
    status_update    = pyqtSignal(str)
    button_triggered = pyqtSignal()
    binding_complete = pyqtSignal(int)

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager        = config_manager
        self.running               = True
        self.paused                = False
        self.binding_mode          = False
        self.button_was_pressed    = False
        self.mutex                 = QMutex()
        self.cached_device_id      = None
        self.waiting_for_reconnect = False
        self.speaker_thread        = None
        self.device                = None

    def stop(self):
        """Signal the thread to stop and unblock any pending ReadFile by closing the handle."""
        self.running = False
        if self.device:
            self.device.close()
        self.wait()

    def set_binding_mode(self, active: bool):
        self.mutex.lock()
        self.binding_mode = active
        self.mutex.unlock()

    def pause(self):
        """
        Called from the GUI thread before a USB reset.
        Just sets the flag and closes the handle — does NOT sleep or block.
        The monitor thread will notice is_open()==False and stop reading on its own.
        """
        self.mutex.lock()
        self.paused = True
        self.mutex.unlock()
        if self.device:
            self.device.close()

    def resume(self):
        self.mutex.lock()
        self.paused = False
        self.waiting_for_reconnect = True
        self.mutex.unlock()

    def get_device_id(self):
        return self.cached_device_id

    def _try_connect(self):
        devices = find_thrustmaster_devices()
        if not devices:
            return False
        path, _ = devices[0]
        self.device = ThrustmasterHID(path)
        if self.device.is_open():
            return True
        self.device = None
        return False

    def run(self):
        self.cached_device_id = DeviceFinder.get_thrustmaster_id()

        if self._try_connect():
            self.status_update.emit(f"🎮 Ready: {self.device.name}")
        else:
            self.status_update.emit("⚠️ No Wheel Detected")

        while self.running:
            self.mutex.lock()
            is_paused = self.paused
            self.mutex.unlock()

            if is_paused:
                # Emit once then just sleep — don't spam the status label
                time.sleep(0.1)
                continue

            # Reconnect if needed
            if self.device is None or not self.device.is_open():
                if self._try_connect():
                    self.status_update.emit(f"🎮 Reconnected: {self.device.name}")
                    if self.waiting_for_reconnect:
                        self.waiting_for_reconnect = False
                        if not self.cached_device_id:
                            self.cached_device_id = DeviceFinder.get_thrustmaster_id()
                        self.speaker_thread = SpeakerThread(
                            "Reset Complete. Press FFB Reset in LMU now.")
                        self.speaker_thread.start()
                    time.sleep(1)
                else:
                    time.sleep(0.5)
                continue

            # read_buttons() blocks until a report arrives or the handle is closed
            buttons = self.device.read_buttons()

            if buttons is None:
                # Handle was closed (pause/stop) or device disconnected
                if not self.paused:
                    self.device = None
                    self.status_update.emit("⚠️ No Wheel Detected")
                    time.sleep(0.5)
                continue

            self.mutex.lock()
            in_binding = self.binding_mode
            self.mutex.unlock()

            if in_binding:
                if buttons != 0:
                    btn_index = (buttons & -buttons).bit_length() - 1
                    self.config_manager.save(btn_index)
                    self.binding_complete.emit(btn_index)
                    self.set_binding_mode(False)
                continue

            bound_btn = self.config_manager.bound_button
            if bound_btn is not None:
                pressed = bool(buttons & (1 << bound_btn))
                if pressed and not self.button_was_pressed:
                    self.button_triggered.emit()
                    self.button_was_pressed = True
                if not pressed:
                    self.button_was_pressed = False