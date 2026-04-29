from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass(frozen=True)
class WindowConfig:
    # 游戏窗口标题。通常保持默认即可。
    # 典型值: "异环"
    # 调整效果: 名称不匹配会导致无法找到窗口。
    name: str = '异环  '


@dataclass(frozen=True)
class ControllerConfig:
    # 截图线程目标 FPS（采样频率上限）。
    # 典型值: 30 / 60 / 120
    # 调大效果: 识别更及时，但 CPU/GPU 占用更高。
    # 调小效果: 资源占用更低，但响应可能变慢。
    fps: int = 30

    # 普通截图循环间隔（秒）。
    # 典型值: 0.005~0.1
    # 调大效果: 降 CPU，占用更稳；调小效果: 响应更快。
    loop_interval: float = 0.1

    # 切前台后等待时间（秒），防止窗口未稳定就截图。
    # 典型值: 0.3~0.8
    foreground_wait_s: float = 0.5

    # 窗口状态检查间隔（秒）。
    # 典型值: 0.3~1.0，越大越省资源。
    window_check_interval_s: float = 0.5

    # 找不到窗口时的初始重试间隔（秒，后续会退避增长）。
    # 典型值: 0.5~2.0
    window_retry_interval_s: float = 1.0

    # 找窗口退避等待的最大值（秒）。
    # 典型值: 3~10
    window_retry_max_s: float = 5.0

    # 自动挪窗到屏幕中间后的稳定等待（秒）。
    # 典型值: 0.1~0.5
    window_move_wait_s: float = 0.2


@dataclass(frozen=True)
class TimeoutsConfig:
    # 等待 HOOK 出现超时（秒）。
    # 典型值: 2~5；调大可减少误超时，调小可更快重试。
    hook_wait_s: float = 3.0

    # 等待 TAKE_BAIT 出现超时（秒）。
    # 典型值: 8~15
    take_bait_wait_s: float = 10.0

    # 溜鱼结束后，点击空白前的固定等待（秒）。
    # 典型值: 0.3~0.8
    # 调大效果: 更稳但每轮稍慢；调小效果: 更快但可能点早了。
    click_blank_delay_s: float = 0.5

    # 鱼条 UI 出现等待超时（秒）。
    # 典型值: 5~12
    fish_ui_wait_s: float = 8.0


@dataclass(frozen=True)
class TemplateConfig:
    # 模板匹配搜索偏移（像素）。
    # 典型值: 6~16
    # 调大效果: 容错更高但更耗时；调小效果: 更快但可能漏检。
    offset: int = 10

    # 模板匹配阈值（0~1）。
    # 典型值: 0.80~0.90
    # 调高效果: 更严格、误识别少；调低效果: 更容易匹配、但误识别风险升高。
    similarity: float = 0.85


@dataclass(frozen=True)
class FishBarConfig:
    # 鱼条 ROI 区域 (x, y, w, h)。
    # 典型值: 保持默认（与当前分辨率/界面对应）。
    rect: tuple[int, int, int, int] = (403, 60, 495, 40)

    # 绿条目标颜色（BGR）。
    # 典型值: 保持默认，除非游戏色彩变化明显。
    green_bar_bgr: tuple[int, int, int] = (173, 202, 42)

    # 黄游标目标颜色（BGR）。
    # 典型值: 保持默认。
    yellow_cursor_bgr: tuple[int, int, int] = (157, 246, 254)

    # 颜色距离阈值（越大越宽松）。
    # 典型值: 8~18
    # 调大效果: 抗颜色波动更好；调小效果: 更精确但更容易漏检。
    color_distance_threshold: int = 10

    # 绿条左侧控制边界比例。
    # 典型值: 0.35~0.45
    green_left_ratio: float = 0.4

    # 绿条右侧控制边界比例。
    # 典型值: 0.55~0.65
    green_right_ratio: float = 0.6

    # 连续丢失绿条多少帧后判定“本次钓鱼结束”。
    # 典型值: 8~15
    # 调大效果: 更稳但结束判定更慢；调小效果: 结束更快但可能误判。
    missing_green_bar_limit: int = 10

    # 鱼条控制循环间隔（秒）。
    # 典型值: 0.0~0.01（通常由 CPU profile 自动覆盖）。
    control_loop_interval: float = 0.0


@dataclass(frozen=True)
class KeyboardConfig:
    # 单击按键按下持续时间（秒）。
    # 典型值: 0.06~0.15
    click_duration_s: float = 0.1

    # 退出监听轮询间隔（秒）。
    # 典型值: 0.05~0.2；越小响应越快但略增 CPU。
    stop_listen_interval_s: float = 0.1

    # 退出时强制释放的按键列表。
    # 典型值: 包含所有脚本可能按下的按键。
    release_keys: tuple[str, ...] = ("a", "d", "f", "w", "s")


@dataclass(frozen=True)
class RetryConfig:
    # 连续失败上限，达到后终止自动重试。
    # 典型值: 3~10
    max_consecutive_failures: int = 5

    # 退避基准等待（秒）。
    # 典型值: 0.3~1.0
    base_backoff_s: float = 0.5

    # 退避等待上限（秒）。
    # 典型值: 5~15
    max_backoff_s: float = 8.0

    # 抖动比例（0~1），用于打散重试节奏。
    # 典型值: 0.1~0.3
    jitter_ratio: float = 0.2


@dataclass(frozen=True)
class MetricsConfig:
    # 每多少轮输出一次汇总指标。
    # 典型值: 10~50；调大可减少日志量。
    summary_every_rounds: int = 50

    # 识别分数采样日志间隔（预留项，后续可扩展）。
    # 典型值: 20~100
    score_log_sample_interval: int = 30


@dataclass(frozen=True)
class CpuConfig:
    # CPU 策略档位（会影响内部 FPS 与循环间隔）。
    # 可选: "performance" / "balanced" / "low"
    # 典型值: "balanced"
    # 调整效果:
    # - performance: 响应最快，CPU 占用最高
    # - balanced:   速度与占用折中
    # - low:        CPU 更低，反应稍慢
    profile: str = "balanced"

    # 每轮成功后的冷却时间（秒）。
    # 典型值: 0.01~0.08
    # 调大效果: 降 CPU；调小效果: 更快进入下一轮。
    round_cooldown_s: float = 0.02


@dataclass(frozen=True)
class AutoStopConfig:
    # 是否启用“达到次数后自动收尾动作”。
    # 建议: 首次测试先设 False，验证无误后再开启。
    enabled: bool = False

    # 目标钓鱼次数（达到后触发动作）。
    # 典型值: 30 / 50 / 99
    target_count: int = 200

    # 达标后是否“杀游戏并结束当前进程”。
    # 典型值: True
    kill_game_and_exit_process_on_target: bool = True

    # 达标后是否执行关机（独立开关，谨慎）。
    # 典型值: False / True
    shutdown_on_target: bool = False

    # 关机延迟（秒）。
    # 典型值: 0 / 30 / 60
    # 调整效果: >0 可给你留出取消关机的时间。
    shutdown_delay_seconds: int = 10


@dataclass(frozen=True)
class AppConfig:
    # 全局配置聚合。通常只改各子配置，不改这里的结构。
    window: WindowConfig = WindowConfig()
    controller: ControllerConfig = ControllerConfig()
    timeouts: TimeoutsConfig = TimeoutsConfig()
    template: TemplateConfig = TemplateConfig()
    fish_bar: FishBarConfig = FishBarConfig()
    keyboard: KeyboardConfig = KeyboardConfig()
    retry: RetryConfig = RetryConfig()
    metrics: MetricsConfig = MetricsConfig()
    cpu: CpuConfig = CpuConfig()
    auto_stop: AutoStopConfig = AutoStopConfig()

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


CONFIG = AppConfig()
