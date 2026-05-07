"""
日志系统
- 普通模式：仅输出到 HomeConsole（通过信号）
- DEBUG 模式：同时保存到 logs/ 目录
"""
import logging
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QObject, Signal


class LogSignal(QObject):
    """日志信号，用于跨线程传递到 UI"""
    info = Signal(str)
    warning = Signal(str)
    error = Signal(str)


class Logger:
    """全局日志管理器"""
    _instance = None
    signal = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.debug_mode = False
        self.file_logger = None

    def _ensure_signal(self):
        """确保 signal 已初始化"""
        if Logger.signal is None:
            Logger.signal = LogSignal()

    def enable_debug(self):
        """开启 DEBUG 模式，开始记录日志到文件"""
        if self.debug_mode:
            return

        self.debug_mode = True

        self.log_dir = Path(__file__).parent.parent / "logs"
        self.log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = self.log_dir / f"{timestamp}.log"

        self.file_logger = logging.getLogger("TFT_BOT_DEBUG")
        self.file_logger.setLevel(logging.DEBUG)
        self.file_logger.handlers.clear()

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        fh = logging.FileHandler(self.log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        self.file_logger.addHandler(fh)

        self._ensure_signal()
        self.signal.info.emit("DEBUG 模式已开启，日志将保存到文件")

    def disable_debug(self):
        """关闭 DEBUG 模式"""
        self.debug_mode = False
        if self.file_logger:
            self.file_logger.handlers.clear()
            self.file_logger = None
        self._ensure_signal()
        self.signal.info.emit("DEBUG 模式已关闭")

    def info(self, msg: str):
        """信息日志 → UI 控制台"""
        print(f"[INFO] {msg}", flush=True)
        self._ensure_signal()
        self.signal.info.emit(msg)
        if self.debug_mode and self.file_logger:
            self.file_logger.info(msg)

    def warning(self, msg: str):
        """警告日志 → UI 控制台"""
        print(f"[WARN] {msg}", flush=True)
        self._ensure_signal()
        self.signal.warning.emit(msg)
        if self.debug_mode and self.file_logger:
            self.file_logger.warning(msg)

    def error(self, msg: str):
        """错误日志 → UI 控制台"""
        print(f"[ERROR] {msg}", flush=True)
        self._ensure_signal()
        self.signal.error.emit(msg)
        if self.debug_mode and self.file_logger:
            self.file_logger.error(msg)


# 全局单例
logger = Logger()