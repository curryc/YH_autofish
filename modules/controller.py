import bettercam
import win32api
import win32gui
import win32con
import time
import random
from modules.logger import logger
from config import CONFIG


def _cpu_profile_overrides():
    profile = (CONFIG.cpu.profile or "balanced").lower()
    if profile == "performance":
        return {"fps": 120, "loop_interval": 0.0}
    if profile == "low":
        return {"fps": 45, "loop_interval": 0.03}
    return {"fps": 75, "loop_interval": 0.01}


class Controller:
    def __init__(self, window_name=None):
        if window_name is None:
            window_name = CONFIG.window.name
        profile = _cpu_profile_overrides()
        self.camera = bettercam.create(output_color="BGR")
        self.camera.start(target_fps=profile["fps"], video_mode=True)
        self.window_name = window_name
        self.last_check_time = 0
        self.rect = None
        self.closed = False
        self._resolution_warning_shown = False
        self._focus_warning_last_ts = 0.0
        self._ensure_hwnd()

    def _try_activate_window(self):
        if win32gui.GetForegroundWindow() == self.hwnd:
            return True
        try:
            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.hwnd)
            time.sleep(CONFIG.controller.foreground_wait_s)
        except Exception as e:
            now = time.time()
            # Throttle noisy foreground errors to keep logs readable.
            if now - self._focus_warning_last_ts >= 1.0:
                logger.warning(f"Failed to focus window, continue with current foreground: {e}")
                self._focus_warning_last_ts = now
            return False
        return win32gui.GetForegroundWindow() == self.hwnd

    def ensure_foreground(self):
        if not win32gui.IsWindow(self.hwnd):
            self._ensure_hwnd()
        return self._try_activate_window()

    def _ensure_hwnd(self):
        attempts = 0
        while True:
            attempts += 1
            self.hwnd = win32gui.FindWindow(None, self.window_name)
            if self.hwnd:
                logger.debug(f"Found window '{self.window_name}' with hwnd {self.hwnd}.")
                break
            else:
                logger.warning(f"Window '{self.window_name}' not found, waiting...")
                wait_s = min(
                    CONFIG.controller.window_retry_max_s,
                    CONFIG.controller.window_retry_interval_s * (2 ** min(attempts - 1, 4)),
                )
                time.sleep(wait_s)

    def screenshot(self, should_stop=None):
        current_time = time.time()
        
        # Limit expensive win32gui calls to every 0.5s for extreme speed
        if current_time - self.last_check_time > CONFIG.controller.window_check_interval_s or self.rect is None:
            if not win32gui.IsWindow(self.hwnd):
                self._ensure_hwnd()

            self._try_activate_window()

            # 只记录窗口矩形，不强制移动窗口。此前在“超出 camera 范围”时会把窗口挪到屏幕正中，
            # 导致用户无法自由摆放；且部分在屏外时与下方裁剪叠加，会把宽度裁成非 1280 触发误报。
            rect = win32gui.GetWindowRect(self.hwnd)
            self.rect = rect
            self.last_check_time = time.time()

        # Fetch frame from background thread instead of blocking synchronous grab
        frame = self.camera.get_latest_frame()
        if frame is None:
            frame = self.camera.grab()
            if frame is None:
                return None
                
        left, top, right, bottom = self.rect
        screen_h, screen_w = frame.shape[:2]
        
        # Ensure crop bounds are valid
        left = max(0, min(left, screen_w))
        right = max(0, min(right, screen_w))
        top = max(0, min(top, screen_h))
        bottom = max(0, min(bottom, screen_h))

        cropped = frame[top:bottom, left:right]
        if 1290 <= cropped.shape[1] <= 1310:
            self._resolution_warning_shown = False
            return cropped

        if not self._resolution_warning_shown:
            logger.warning("当前窗口必须调整为 1280x720。请调整后等待自动继续。")
            self._resolution_warning_shown = True

        while True:
            if should_stop and should_stop():
                return None

            time.sleep(1.0)
            if not win32gui.IsWindow(self.hwnd):
                self._ensure_hwnd()

            rect = win32gui.GetWindowRect(self.hwnd)
            self.rect = rect

            frame = self.camera.get_latest_frame()
            if frame is None:
                frame = self.camera.grab()
                if frame is None:
                    continue

            left, top, right, bottom = self.rect
            screen_h, screen_w = frame.shape[:2]
            left = max(0, min(left, screen_w))
            right = max(0, min(right, screen_w))
            top = max(0, min(top, screen_h))
            bottom = max(0, min(bottom, screen_h))
            cropped = frame[top:bottom, left:right]
            if 1290 <= cropped.shape[1] <= 1310:
                self._resolution_warning_shown = False
                return cropped

    def loop(self, interval=None, should_stop=None):
        if interval is None:
            interval = _cpu_profile_overrides()["loop_interval"]
        while True:
            if should_stop and should_stop():
                return
            try:
                s = self.screenshot(should_stop=should_stop)
            except Exception as e:
                logger.error(f"Error during screenshot: {e}")
            else:
                if s is not None:
                    yield s
            time.sleep(interval)

    def mouse_click(self, pos=(650, 700)):
        if not win32gui.IsWindow(self.hwnd):
            self._ensure_hwnd()

        self._try_activate_window()

        x, y = win32gui.ClientToScreen(self.hwnd, pos)
        logger.debug(f"Mouse click at client pos {pos} (screen pos {x}, {y}).")
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def sleep(self, seconds, variance=0.2):
        low = seconds * (1 - variance)
        high = seconds * (1 + variance)
        t = sum(random.uniform(low, high) for _ in range(3)) / 3
        logger.debug(f"Sleeping for {t:.3f}s (target: {seconds}s).")
        time.sleep(t)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.camera.stop()
        except Exception as e:
            logger.warning(f"Error while stopping camera: {e}")