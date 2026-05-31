"""
全屏透明覆盖层
- 左侧：游戏实时日志（底部往上滚动，最新在底部）
- 右侧：状态摘要（底部对齐，紧凑行显示）
- 棋盘上方：英雄名称标签
- 鼠标穿透，始终置顶，无背景无圆角
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout


class Overlay(QWidget):
    """全屏透明覆盖层"""

    def __init__(self, message_queue):
        super().__init__()
        self.message_queue = message_queue
        self.hero_labels = []
        self.setup_window()
        self.setup_left_log()
        self.setup_right_status()
        self.setup_timer()

    def setup_window(self):
        """窗口基础设置：全屏、透明、置顶、鼠标穿透"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        screen = self.screen()
        self.resize(screen.size())
        self.setStyleSheet("background: transparent;")

    def setup_left_log(self):
        """左侧：游戏实时日志，底部往上滚动，最多 15 条"""
        self.logCard = QWidget(self)
        self.logCard.setFixedSize(260, 280)
        self.logCard.move(0, 800)
        self.logCard.setStyleSheet("background: transparent;")

        self.logLayout = QVBoxLayout(self.logCard)
        self.logLayout.setContentsMargins(8, 0, 8, 4)
        self.logLayout.setSpacing(0)
        self.logLayout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        self.logLabels = []
        for _ in range(15):
            lbl = QLabel("")
            lbl.setStyleSheet("color:#FFFFFF; font-size: 10px; line-height: 16px; text-shadow: 1px 1px 3px rgba(0,0,0,0.9);")
            self.logLayout.addWidget(lbl)
            self.logLabels.append(lbl)

        self.logLines = [""] * 15

    def setup_right_status(self):
        """右侧：状态摘要 (1493,878) ~ (1743,1080)，宽250，底部对齐"""
        self.statusCard = QWidget(self)
        self.statusCard.setFixedSize(250, 202)
        self.statusCard.move(1493, 878)
        self.statusCard.setStyleSheet("background: transparent;")

        rightLayout = QVBoxLayout(self.statusCard)
        rightLayout.setContentsMargins(8, 0, 8, 4)
        rightLayout.setSpacing(2)
        rightLayout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        self.statusLineLabel = QLabel("状态：未启动")
        self.statusLineLabel.setStyleSheet("color: #cccccc; font-size: 11px;")

        self.compLineLabel = QLabel("")
        self.compLineLabel.setStyleSheet("color: #ffcc00; font-size: 11px; font-weight: bold;")

        self.infoLineLabel = QLabel("对局：-- | 段位：-- | 通行证：--")
        self.infoLineLabel.setStyleSheet("color: #cccccc; font-size: 11px;")

        self.hotkeyLineLabel = QLabel("热键：F7 -- | F8 本局后停止 | F9 隐藏界面")
        self.hotkeyLineLabel.setStyleSheet("color: #cccccc; font-size: 11px;")

        rightLayout.addWidget(self.statusLineLabel)
        rightLayout.addWidget(self.compLineLabel)
        rightLayout.addWidget(self.infoLineLabel)
        rightLayout.addWidget(self.hotkeyLineLabel)

    def setup_timer(self):
        """定时刷新状态"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_state)
        self.timer.start(500)

    def refresh_state(self):
        """从消息队列读取状态更新"""
        while not self.message_queue.empty():
            msg = self.message_queue.get_nowait()

            if msg == "CLEAR":
                self._clear_hero_labels()
                # 重置左侧日志
                self.logLines = [""] * 15
                for i, label in enumerate(self.logLabels):
                    label.setText("")
                # 重置右侧推荐阵容
                self.compLineLabel.hide()
                # 重置状态摘要
                self.statusLineLabel.setText("状态：未启动")
                self.statusLineLabel.setStyleSheet("color: #888888; font-size: 11px; font-weight: bold;")
                self.infoLineLabel.setText("对局：-- | 段位：-- | 通行证：--")
                continue

            msg_type = msg[0] if isinstance(msg, (list, tuple)) else msg

            if msg_type == "STATUS":
                self._update_right_status(msg[1])
            elif msg_type == "LOG":
                self.add_game_log(msg[1])
            elif msg_type == "LABEL":
                self._update_hero_labels(msg[1])

    def add_game_log(self, text: str):
        """左侧添加一条游戏日志，新日志出现在底部，旧日志上移"""
        self.logLines.pop(0)
        self.logLines.append(text)
        for i, label in enumerate(self.logLabels):
            label.setText(self.logLines[i])

    def _update_right_status(self, data: dict):
        """更新右侧状态摘要"""
        game_count = data.get("game_count", "--")
        rank = data.get("rank", "--")
        pass_level = data.get("pass_level", "--")
        running = data.get("running", False)
        paused = data.get("paused", False)
        stop_after_game = data.get("stop_after_game", False)

        # 第一行：状态
        if not running:
            status_text = "未启动"
            status_color = "#888888"
        elif stop_after_game:
            status_text = "对局结束停止"
            status_color = "#cd5c5c"  # 暗红色
        elif paused:
            status_text = "暂停"
            status_color = "#ffd700"  # 黄色
        else:
            status_text = "自动对局"
            status_color = "#12aa9c"  # 绿色

        self.statusLineLabel.setText(f"状态：{status_text}")
        self.statusLineLabel.setStyleSheet(
            f"color: {status_color}; font-size: 11px; font-weight: bold;"
        )

        # 推荐阵容
        comp_name = data.get("comp_name", "")
        if comp_name:
            self.compLineLabel.setText(f"{comp_name}")
            self.compLineLabel.show()
        else:
            self.compLineLabel.hide()

        # 第二行：对局信息
        self.infoLineLabel.setText(
            f"对局：{game_count} | 段位：{rank} | 通行证：Lv {pass_level}"
        )

        # 第三行：热键
        f7_text = "F7 继续" if paused else "F7 暂停"

        if stop_after_game:
            f8_color = "#cd5c5c"  # 暗红色高亮
        else:
            f8_color = "#cccccc"

        self.hotkeyLineLabel.setText(
            f"热键：{f7_text} | "
            f"<span style='color:{f8_color};'>F8 本局后停止</span>"
            f" | F9 隐藏界面"
        )


    def _clear_hero_labels(self):
        """清除所有英雄标签"""
        for label in self.hero_labels:
            label.deleteLater()
        self.hero_labels.clear()

    def _update_hero_labels(self, labels: list):
        """更新英雄名称标签"""
        self._clear_hero_labels()
        for name, (x, y) in labels:
            label = QLabel(name, self)
            label.setStyleSheet("""
                color: white;
                font-size: 12px;
                font-weight: bold;
                background: rgba(0, 0, 0, 150);
                padding: 2px 6px;
                border-radius: 4px;
            """)
            label.move(x - 20, y + 25)
            label.show()
            self.hero_labels.append(label)


def run_overlay(message_queue):
    """在子进程中运行覆盖层"""
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    overlay = Overlay(message_queue)
    overlay.show()
    app.exec()


if __name__ == "__main__":
    """测试 overlay 四种状态切换"""
    import sys
    import multiprocessing
    import time
    import threading
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    queue = multiprocessing.Queue()
    overlay = Overlay(queue)
    overlay.show()

    def test_data():
        # 1. 未启动
        time.sleep(1)
        queue.put(("STATUS", {
            "running": False,
            "game_count": 0,
            "rank": "最强王者",
            "pass_level": 23,
        }))
        queue.put(("LOG", "等待启动..."))

        time.sleep(2)

        # 2. 自动对局
        queue.put(("STATUS", {
            "running": True,
            "paused": False,
            "stop_after_game": False,
            "game_count": 5,
            "rank": "最强王者",
            "pass_level": 23,
        }))
        queue.put(("LOG", "机器人启动"))
        queue.put(("LOG", "YOLO模型加载完成 → best.onnx"))
        queue.put(("LOG", "回合 2-1 开始（PVP）"))
        queue.put(("LOG", "YOLO检测完成，发现 3 个法球"))
        queue.put(("LOG", "成功拾取金色法球"))

        time.sleep(3)

        # 3. 暂停
        queue.put(("STATUS", {
            "running": True,
            "paused": True,
            "stop_after_game": False,
            "game_count": 5,
            "rank": "最强王者",
            "pass_level": 23,
        }))
        queue.put(("LOG", "用户按下 F7，机器人已暂停"))

        time.sleep(3)

        # 4. 继续（恢复自动对局）
        queue.put(("STATUS", {
            "running": True,
            "paused": False,
            "stop_after_game": False,
            "game_count": 5,
            "rank": "最强王者",
            "pass_level": 23,
        }))
        queue.put(("LOG", "用户按下 F7，机器人继续运行"))

        time.sleep(3)

        # 5. F8 本局结束后停止
        queue.put(("STATUS", {
            "running": True,
            "paused": False,
            "stop_after_game": True,
            "game_count": 5,
            "rank": "最强王者",
            "pass_level": 23,
        }))
        queue.put(("LOG", "用户按下 F8，本局结束后将停止123456789"))

        time.sleep(4)

        # 6. 回到未启动
        queue.put("CLEAR")
        queue.put(("STATUS", {
            "running": False,
            "game_count": 6,
            "rank": "最强王者",
            "pass_level": 23,
        }))
        queue.put(("LOG", "机器人已停止"))

    t = threading.Thread(target=test_data, daemon=True)
    t.start()

    app.exec()
