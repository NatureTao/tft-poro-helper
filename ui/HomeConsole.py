"""
控制台模块：纯日志展示（带标签栏 + 清空按钮）
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtGui import QTextCursor
from qfluentwidgets import CardWidget, TextEdit, FluentIcon, IconWidget, TransparentToolButton, ToolButton, PushButton


class HomeConsole(CardWidget):
    """日志控制台"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = None
        self.setMinimumHeight(250)
        self.setup_ui()

    def setup_ui(self):
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(12, 8, 12, 8)
        self.vBoxLayout.setSpacing(6)

        # ---- 标签栏 ----
        tabBar = QHBoxLayout()
        tabBar.setSpacing(6)

        icon = IconWidget(FluentIcon.COMMAND_PROMPT)
        icon.setFixedSize(16, 16)

        title = QLabel("运行日志")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #cccccc; font-family: 'SimHei';")

        tabBar.addWidget(icon)
        tabBar.addWidget(title)
        tabBar.addStretch()

        clearBtn = PushButton(FluentIcon.BROOM, "清空")
        clearBtn.clicked.connect(self.clear_log)
        tabBar.addWidget(clearBtn)

        self.vBoxLayout.addLayout(tabBar)

        # ---- 日志展示区 ----
        self.textEdit = TextEdit()
        self.textEdit.setReadOnly(True)
        self.textEdit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.vBoxLayout.addWidget(self.textEdit, 1)

    def set_controller(self, controller):
        self.controller = controller
        from utils.logger import logger
        logger.signal.info.connect(self._on_log_info)
        logger.signal.warning.connect(self._on_log_warning)
        logger.signal.error.connect(self._on_log_error)
        print(f"[HomeConsole] debug_mode={logger.debug_mode}")
        if logger.debug_mode:
            self.appendLog("[系统] DEBUG 模式已开启，日志将保存到文件")

    def _on_log_info(self, msg: str):
        print(f"[信号收到] {msg}")
        self.appendLog(f"[信息] {msg}")

    def _on_log_warning(self, msg: str):
        self.appendLog(f"[警告] {msg}")

    def _on_log_error(self, msg: str):
        self.appendLog(f"[错误] {msg}")

    def appendLog(self, message: str):
        """添加日志"""
        html = f'<span style="color:#12aa9c;font-size:12px;">{message}</span><br>'
        if self.textEdit.toPlainText():
            html = self.textEdit.toHtml() + html
        self.textEdit.setHtml(html)
        self.scroll_to_bottom()

    def clear_log(self):
        """清空日志"""
        self.textEdit.clear()

    def scroll_to_bottom(self):
        """滚动到底部"""
        cursor = self.textEdit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.textEdit.setTextCursor(cursor)
        self.textEdit.ensureCursorVisible()