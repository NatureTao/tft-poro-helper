"""
TFT-OCR-BOT 统一入口
- 启动 PySide6 主窗口
- 初始化 BotController
- 连接 logger、overlay、HomeConsole
"""
import sys
from pathlib import Path
import multiprocessing
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import logger, Logger, LogSignal
from ui.app import Window


def main():
    multiprocessing.freeze_support()
    # 先启动 Qt，让窗口尽快显示
    app = QApplication(sys.argv)
    Logger.signal = LogSignal()
    logger._ensure_signal()

    # 延迟导入 Controller（掩盖加载耗时）
    from bot_controller import BotController
    controller = BotController()
    # logger 信号 → overlay
    logger.signal.info.connect(lambda msg: controller.send_log(msg))
    logger.signal.warning.connect(lambda msg: controller.send_log(f"[!] {msg}"))
    logger.signal.error.connect(lambda msg: controller.send_log(f"[X] {msg}"))

    # 创建主窗口
    window = Window()
    window.homeInterface.set_controller(controller)
    window.show()

    app.aboutToQuit.connect(controller.cleanup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
