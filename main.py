import ctypes
import logging
import os
import random
import subprocess
import sys
import time


def _ensure_process_dpi_aware():
    """Align Win32 window rects with screen capture pixels (multi-monitor / scaling)."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except (OSError, AttributeError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (OSError, AttributeError):
            pass


_ensure_process_dpi_aware()

if getattr(sys, "frozen", False):
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir and exe_dir not in sys.path:
        sys.path.insert(0, exe_dir)


def ensure_admin_or_exit():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return

    print("[ERROR] This program requires administrator privileges.")
    print("[INFO] Attempting to relaunch with administrator rights (UAC)...")

    executable = sys.executable
    params = ""
    if not getattr(sys, "frozen", False):
        params = f'"{os.path.abspath(__file__)}"'

    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", executable, params, None, 1
    )
    if result <= 32:
        print("[ERROR] Failed to request administrator privileges.")
        print("[INFO] Please right-click and run as administrator.")
        os.system("pause")
        sys.exit(1)

    sys.exit(0)


ensure_admin_or_exit()

from config import CONFIG
from modules.controller import Controller
from modules.fish_bar import FishBar
from modules.keyboard import Keyboard
from modules.logger import logger, log_kv
from modules.template import BLANK, HOOK, TAKE_BAIT, Template

RECOVERABLE_ERRORS = (TimeoutError,)
TRANSIENT_ERRORS = (RuntimeError,)


def wait_until_appear(controller, template, timeout, should_stop):
    timeout_text = "infinite" if timeout is None or timeout <= 0 else f"{timeout}s"
    logger.debug(f"Waiting for {template} with timeout {timeout_text}...")
    start_time = time.time()
    for frame in controller.loop(should_stop=should_stop):
        if should_stop():
            raise TimeoutError("Shutdown requested.")
        if template.match(frame):
            logger.debug(f"Found {template}.")
            controller.sleep(0.1)
            return time.time() - start_time
        if timeout is not None and timeout > 0 and time.time() - start_time > timeout:
            logger.warning(f"Wait for {template} timeout after {timeout}s.")
            raise TimeoutError(f"Wait for {template} failed after {timeout}s.")
    raise TimeoutError(f"Wait for {template} interrupted.")


def click_blank_after_fishing(controller, should_stop):
    timeout_s = max(0.1, float(CONFIG.timeouts.blank_wait_s))
    logger.debug(f"Fishing ended, waiting for BLANK with timeout {timeout_s:.1f}s.")
    wait_until_appear(controller, BLANK, timeout_s, should_stop)
    controller.ensure_foreground()
    logger.info("starting next fishing round...")
    controller.mouse_click()


def should_stop():
    return Keyboard.is_exit_requested()


def backoff_sleep(attempt):
    wait_seconds = min(
        CONFIG.retry.max_backoff_s,
        CONFIG.retry.base_backoff_s * (2 ** max(0, attempt - 1)),
    )
    jitter = wait_seconds * CONFIG.retry.jitter_ratio * random.random()
    actual_wait = wait_seconds + jitter
    time.sleep(actual_wait)
    return actual_wait


def classify_error(exc):
    if isinstance(exc, RECOVERABLE_ERRORS):
        return "recoverable"
    if isinstance(exc, TRANSIENT_ERRORS):
        return "transient"
    return "fatal"


def log_config_snapshot():
    cfg = CONFIG.as_dict()
    log_kv(
        logging.INFO,
        "config_snapshot",
        window=cfg["window"],
        controller=cfg["controller"],
        timeouts=cfg["timeouts"],
        template=cfg["template"],
        fish_bar=cfg["fish_bar"],
        keyboard=cfg["keyboard"],
        retry=cfg["retry"],
        metrics=cfg["metrics"],
    )


def safe_cleanup(controller, fish_bar):
    try:
        fish_bar._release_all()
    except Exception as e:
        logger.warning(f"Failed to release keys from fish bar: {e}")
    finally:
        for key in CONFIG.keyboard.release_keys:
            Keyboard.release(key)

    try:
        Keyboard.stop_stop_listener()
    except Exception as e:
        logger.warning(f"Failed to stop keyboard listener: {e}")

    try:
        controller.close()
    except Exception as e:
        logger.warning(f"Failed to close controller: {e}")


def execute_target_actions():
    if CONFIG.auto_stop.shutdown_on_target:
        logger.info("Target reached. Shutting down system...")
        delay = max(0, int(CONFIG.auto_stop.shutdown_delay_seconds))
        try:
            subprocess.run(
                ["shutdown", "/s", "/t", str(delay)],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            logger.warning(f"Failed to schedule shutdown: {e}")

    if CONFIG.auto_stop.kill_game_and_exit_process_on_target:
        logger.info("Target reached. Killing game window and exiting current process...")
        title_filter = f"WINDOWTITLE eq {CONFIG.window.name.strip()}*"
        try:
            subprocess.run(
                ["taskkill", "/FI", title_filter, "/F", "/T"],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            logger.warning(f"Failed to kill game window: {e}")
        return "exit_process"


def run():
    logger.info("Initializing controllers...")
    controller = Controller(window_name=CONFIG.window.name)
    fish_bar = FishBar(controller)
    keyboard = Keyboard()
    Keyboard.clear_exit_request()
    keyboard.start_stop_listener()
    log_config_snapshot()
    logger.info("Initialization complete. Starting main loop.")

    rounds = 0
    success_rounds = 0
    total_retries = 0
    consecutive_failures = 0
    target_actions_requested = False

    try:
        while not should_stop():
            rounds += 1
            round_start = time.time()
            retry_count = 0
            while not should_stop():
                stage_times = {}
                try:
                    stage_times["wait_hook_s"] = wait_until_appear(
                        controller, HOOK, CONFIG.timeouts.hook_wait_s, should_stop
                    )
                    controller.ensure_foreground()
                    logger.info("Spinning rod")
                    keyboard.click("f")

                    stage_times["wait_take_bait_s"] = wait_until_appear(
                        controller, TAKE_BAIT, CONFIG.timeouts.take_bait_wait_s, should_stop
                    )
                    controller.ensure_foreground()
                    logger.info("Taking bait")
                    keyboard.click("f")

                    fish_stats = fish_bar.start(should_stop=should_stop)

                    blank_start = time.time()
                    click_blank_after_fishing(controller, should_stop)
                    stage_times["wait_click_blank_s"] = time.time() - blank_start

                    elapsed = time.time() - round_start
                    success_rounds += 1
                    consecutive_failures = 0
                    log_kv(
                        logging.INFO,
                        "round_result: ",
                        round=rounds,
                        result="success",
                        duration_s=round(elapsed, 3),
                    )
                    if (
                        CONFIG.auto_stop.enabled
                        and rounds >= CONFIG.auto_stop.target_count
                    ):
                        target_actions_requested = True
                        logger.info(
                            f"Target success count reached: {rounds}. Preparing stop actions."
                        )
                        break
                    time.sleep(CONFIG.cpu.round_cooldown_s)
                    break
                except Exception as e:
                    error_type = classify_error(e)
                    consecutive_failures += 1
                    if not should_stop():
                        controller.mouse_click()
                    log_kv(
                        logging.WARNING if error_type != "fatal" else logging.ERROR,
                        "round_error",
                        round=rounds,
                        error_type=error_type,
                        exception=repr(e),
                        retry_count=retry_count,
                        consecutive_failures=consecutive_failures,
                    )
                    if error_type == "fatal":
                        raise
                    retry_count += 1
                    total_retries += 1
                    if consecutive_failures >= CONFIG.retry.max_consecutive_failures:
                        raise RuntimeError(
                            f"Reached max consecutive failures: {consecutive_failures}"
                        ) from e
                    waited = backoff_sleep(retry_count)
                    log_kv(
                        logging.INFO,
                        "retry_backoff",
                        round=rounds,
                        retry_count=retry_count,
                        wait_s=round(waited, 3),
                    )

            if rounds % CONFIG.metrics.summary_every_rounds == 0:
                success_rate = (success_rounds / rounds) if rounds else 0.0
                template_rate = (
                    Template.matches / Template.attempts if Template.attempts else 0.0
                )
                log_kv(
                    logging.INFO,
                    "summary",
                    rounds=rounds,
                    success_rounds=success_rounds,
                    success_rate=round(success_rate, 3),
                    total_retries=total_retries,
                    template_attempts=Template.attempts,
                    template_matches=Template.matches,
                    template_success_rate=round(template_rate, 3),
                )
            if target_actions_requested:
                break
    finally:
        logger.info("Shutting down and releasing resources...")
        safe_cleanup(controller, fish_bar)
        if target_actions_requested:
            action = execute_target_actions()
            if action == "exit_process":
                os._exit(0)


if __name__ == "__main__":
    run()