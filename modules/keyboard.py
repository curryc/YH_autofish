import ctypes
import time
import threading
from modules.logger import logger
from config import CONFIG

# 硬件扫描码表 (Scan Codes)
SCAN_CODES = {
    'a': 0x1E,
    'd': 0x20,
    'f': 0x21,
    'w': 0x11,
    's': 0x1F,
    'esc': 0x01,
}

SendInput = ctypes.windll.user32.SendInput

# C struct definitions for SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)
class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]

class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

def press_key(key):
    if key not in SCAN_CODES:
        return
    hex_code = SCAN_CODES[key]
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, hex_code, 0x0008, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def release_key(key):
    if key not in SCAN_CODES:
        return
    hex_code = SCAN_CODES[key]
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, hex_code, 0x0008 | 0x0002, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

class Keyboard:
    _exit_requested = threading.Event()
    _listener_stop = threading.Event()
    _listener_thread = None

    @staticmethod
    def press(key):
        press_key(key)

    @staticmethod
    def release(key):
        release_key(key)

    @staticmethod
    def click(key, duration=None):
        if duration is None:
            duration = CONFIG.keyboard.click_duration_s
        press_key(key)
        time.sleep(duration)
        release_key(key)

    @staticmethod
    def start_stop_listener():
        if Keyboard._listener_thread and Keyboard._listener_thread.is_alive():
            return

        Keyboard._listener_stop.clear()

        def listen():
            VK_BACKTICK = 0xC0
            while not Keyboard._listener_stop.is_set():
                if ctypes.windll.user32.GetAsyncKeyState(VK_BACKTICK) & 0x8000:
                    if not Keyboard._exit_requested.is_set():
                        logger.info("'`' key detected. Graceful shutdown requested.")
                    Keyboard._exit_requested.set()
                    time.sleep(0.2)
                time.sleep(CONFIG.keyboard.stop_listen_interval_s)

        Keyboard._listener_thread = threading.Thread(target=listen, daemon=True)
        Keyboard._listener_thread.start()

    @staticmethod
    def stop_stop_listener():
        Keyboard._listener_stop.set()
        thread = Keyboard._listener_thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        Keyboard._listener_thread = None

    @staticmethod
    def is_exit_requested():
        return Keyboard._exit_requested.is_set()

    @staticmethod
    def clear_exit_request():
        Keyboard._exit_requested.clear()
