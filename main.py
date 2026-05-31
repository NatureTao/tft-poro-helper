"""
TFT-PORO-HELPER 统一入口
- 注册字体 → 全局默认 MiSans Regular
- 启动 PySide6 主窗口
- 后台预加载 YOLO + OCR + 游戏数据（不阻塞 UI）
- 加载完成后初始化 BotController
"""
import sys
import threading
from pathlib import Path
import multiprocessing

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import logger, Logger, LogSignal
from ui.app import Window


class Preloader:
    """后台预加载器：加载 YOLO + OCR + 游戏数据"""

    def __init__(self):
        self.yolo_ready = False
        self.ocr_ready = False
        self.game_data_ready = False

    @property
    def all_ready(self) -> bool:
        return self.yolo_ready and self.ocr_ready and self.game_data_ready

    def load_all(self, on_done=None):
        def _load():
            import os
            os.environ["ULTRALYTICS_AUTO_UPDATE"] = "false"

            logger.info("[预加载] 开始后台加载...")

            # 1. YOLO
            try:
                from ultralytics import YOLO
                _yolo = YOLO("models/tft_yolo_v5.onnx", task="detect", verbose=False)
                self.yolo_ready = True
                # 注入给 game_functions，避免游戏中重复加载
                from game_functions import set_yolo_model
                set_yolo_model(_yolo)
                logger.info("[预加载] YOLO 就绪")
            except Exception as e:
                logger.error(f"[预加载] YOLO 失败: {e}")

            # 2. OCR
            try:
                from ocr import reader
                self.ocr_ready = True
                logger.info("[预加载] OCR 就绪")
            except Exception as e:
                logger.error(f"[预加载] OCR 失败: {e}")

            # 3. 游戏数据
            try:
                from services.game_data_update import GameDataUpdate
                gd = GameDataUpdate(origin="META_TFT", language="CN")
                gd.pull_latest_data()
                self.game_data_ready = True
                logger.info("[预加载] 游戏数据就绪")
            except Exception as e:
                logger.error(f"[预加载] 游戏数据失败: {e}")

            if self.all_ready:
                logger.info("[预加载] 全部就绪")
            if on_done:
                on_done()

        threading.Thread(target=_load, daemon=True).start()


def main():
    multiprocessing.freeze_support()

    # ==================================================================
    # 1. 启动 Qt 应用
    # ==================================================================
    app = QApplication(sys.argv)

    # ==================================================================
    # 2. 注册所有字体
    # ==================================================================
    fonts_dir = Path(__file__).parent / "fonts"
    for f in fonts_dir.glob("*"):
        if f.suffix in (".ttf", ".otf"):
            QFontDatabase.addApplicationFont(str(f))

    # ==================================================================
    # 3. 设置全局默认字体
    # ==================================================================
    font = QFont("MiSans", 12, QFont.Weight.Normal)
    app.setFont(font)

    # ==================================================================
    # 4. 初始化日志信号
    # ==================================================================
    Logger.signal = LogSignal()
    logger._ensure_signal()

    # ==================================================================
    # 5. 创建窗口
    # ==================================================================
    window = Window()

    # ==================================================================
    # 6. 后台预加载 YOLO + OCR + 游戏数据
    # ==================================================================
    preloader = Preloader()
    _initialized = False

    def init_controller():
        nonlocal _initialized
        if _initialized:
            return
        _initialized = True
        from bot_controller import BotController
        controller = BotController()
        logger.signal.info.connect(lambda msg: controller.send_log(msg))
        logger.signal.warning.connect(lambda msg: controller.send_log(f"[!] {msg}"))
        logger.signal.error.connect(lambda msg: controller.send_log(f"[X] {msg}"))
        window.homeInterface.set_controller(controller)
        app.aboutToQuit.connect(controller.cleanup)

    def check_ready():
        if preloader.all_ready:
            init_controller()
        else:
            QTimer.singleShot(1000, check_ready)

    preloader.load_all(on_done=check_ready)
    check_ready()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()