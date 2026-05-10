"""
TFT-PORO-HELPER 统一入口
- 注册字体 → 全局默认 MiSans Regular
- 启动 PySide6 主窗口
- 初始化 BotController
- 连接 logger → overlay / HomeConsole
"""
import sys
from pathlib import Path
import multiprocessing

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import logger, Logger, LogSignal
from ui.app import Window


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
    # 5. 创建机器人控制器
    # ==================================================================
    from bot_controller import BotController
    controller = BotController()

    # 日志信号 → overlay
    logger.signal.info.connect(lambda msg: controller.send_log(msg))
    logger.signal.warning.connect(lambda msg: controller.send_log(f"[!] {msg}"))
    logger.signal.error.connect(lambda msg: controller.send_log(f"[X] {msg}"))

    # ==================================================================
    # 6. 创建主窗口并注入控制器
    # ==================================================================
    window = Window()
    window.homeInterface.set_controller(controller)
    window.show()

    # ==================================================================
    # 7. 退出清理
    # ==================================================================
    app.aboutToQuit.connect(controller.cleanup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()