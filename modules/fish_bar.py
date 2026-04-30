import numpy as np
import time
from dataclasses import dataclass

from modules.controller import Controller
from modules.keyboard import Keyboard
from modules.logger import logger
from config import CONFIG


def _fish_loop_interval():
    profile = (CONFIG.cpu.profile or "balanced").lower()
    if profile == "performance":
        return 0.0
    if profile == "low":
        return 0.01
    return 0.003


@dataclass
class FishBarStats:
    frames: int = 0
    missing_green_peak: int = 0
    cursor_missing: int = 0
    ui_wait_seconds: float = 0.0
    success: bool = False

class FishBar:
    RECT = CONFIG.fish_bar.rect
    GREEN_BAR = CONFIG.fish_bar.green_bar_bgr
    YELLOW_CURSOR = CONFIG.fish_bar.yellow_cursor_bgr

    def __init__(self, controller: Controller):
        self.controller = controller
        self.keyboard = Keyboard()
        self.current_key = None
        self.in_center_zone = False
        self.pulse_until = 0.0
        self.pulse_ready_at = 0.0
    
    def _get_green_bar(self, screenshot):
        x, y, w, h = self.RECT
        roi = screenshot[y:y+h, x:x+w]
        
        target = np.array(self.GREEN_BAR, dtype=np.int16)
        dist = np.sum(np.abs(roi.astype(np.int16) - target), axis=2)
        
        threshold = CONFIG.fish_bar.color_distance_threshold
        mask = dist < threshold
        cols = np.where(np.any(mask, axis=0))[0]
        if cols.size > 0:
            left, right = cols[0] + x, cols[-1] + x
            width = right - left
            return (
                int(left + width * CONFIG.fish_bar.green_left_ratio),
                int(left + width * CONFIG.fish_bar.green_right_ratio),
            )
        return None

    def _get_yellow_cursor(self, screenshot):
        x, y, w, h = self.RECT
        roi = screenshot[y:y+h, x:x+w]
        
        target = np.array(self.YELLOW_CURSOR, dtype=np.int16)
        dist = np.sum(np.abs(roi.astype(np.int16) - target), axis=2)
        
        threshold = CONFIG.fish_bar.color_distance_threshold
        mask = dist < threshold
        cols = np.where(np.any(mask, axis=0))[0]
        if cols.size > 0:
            return int((cols[0] + cols[-1]) // 2 + x)
        return None

    def _press(self, key):
        if self.current_key == key:
            return
        
        self._release_all()
        if key:
            logger.debug(f"Pressing '{key}'")
            self.keyboard.press(key)
            self.current_key = key

    def _release_all(self):
        if self.current_key:
            logger.debug(f"Releasing '{self.current_key}'")
            self.keyboard.release(self.current_key)
            self.current_key = None

    def _control_track_center(self, left, right, cursor):
        target = (left + right) / 2.0
        err = cursor - target
        abs_err = abs(err)

        enter_deadzone = max(0, int(CONFIG.fish_bar.center_deadzone_enter_px))
        exit_deadzone = max(enter_deadzone, int(CONFIG.fish_bar.center_deadzone_exit_px))
        medium_err = max(exit_deadzone + 1, int(CONFIG.fish_bar.medium_error_px))
        large_err = max(medium_err + 1, int(CONFIG.fish_bar.large_error_px))

        # 滞回：进入中心区后，误差需超过更大的退出阈值才恢复控制。
        if self.in_center_zone:
            if abs_err <= exit_deadzone:
                self._release_all()
                return
            self.in_center_zone = False
        elif abs_err <= enter_deadzone:
            self.in_center_zone = True
            self._release_all()
            return

        target_key = "d" if err < 0 else "a"

        if abs_err >= large_err:
            self._press(target_key)
            self.pulse_until = 0.0
            self.pulse_ready_at = 0.0
            return

        now = time.time()
        if abs_err >= medium_err:
            if self.current_key == target_key:
                if now >= self.pulse_until:
                    self._release_all()
                    self.pulse_ready_at = now + max(0.0, float(CONFIG.fish_bar.pulse_release_s))
                return

            if now >= self.pulse_ready_at:
                self._press(target_key)
                self.pulse_until = now + max(0.0, float(CONFIG.fish_bar.pulse_press_s))
            return

        self._release_all()

    def wait_until_ui_appear(self, timeout=None, should_stop=None):
        if timeout is None:
            timeout = CONFIG.timeouts.fish_ui_wait_s
        logger.debug("Waiting for fish bar UI to appear...")
        start = time.time()
        for frame in self.controller.loop(should_stop=should_stop):
            if should_stop and should_stop():
                raise TimeoutError("Fish bar interrupted by exit request.")
            if self._get_green_bar(frame) is not None and self._get_yellow_cursor(frame) is not None:
                logger.debug("Fish bar UI appeared.")
                return time.time() - start
            if time.time() - start > timeout:
                raise TimeoutError(f"Fish bar UI timeout after {timeout}s.")
        raise TimeoutError("Fish bar UI loop interrupted.")

    def start(self, should_stop=None):
        logger.info("Fishing...")
        stats = FishBarStats()
        stats.ui_wait_seconds = self.wait_until_ui_appear(should_stop=should_stop)
        
        missing_green_bar_count = 0
        for frame in self.controller.loop(
            interval=_fish_loop_interval(), should_stop=should_stop
        ):
            if should_stop and should_stop():
                break
            stats.frames += 1
            green_bar = self._get_green_bar(frame)
            
            if green_bar is None:
                missing_green_bar_count += 1
                stats.missing_green_peak = max(stats.missing_green_peak, missing_green_bar_count)
                if missing_green_bar_count > CONFIG.fish_bar.missing_green_bar_limit:
                    logger.info("Fishing ended.")
                    stats.success = True
                    break
                continue
            
            missing_green_bar_count = 0
            left, right = green_bar
            cursor = self._get_yellow_cursor(frame)

            if cursor is None:
                stats.cursor_missing += 1
                continue
            self._control_track_center(left, right, cursor)

        self._release_all()
        return stats
            

        