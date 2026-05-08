"""
控制台模块：纯日志展示（带标签栏 + 清空按钮）
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtGui import QTextCursor
from qfluentwidgets import CardWidget, TextEdit, FluentIcon, IconWidget, PushButton

from ui.i18n import I18n, I18nKey


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

        self.title = QLabel(I18n.get(I18nKey.RUN_LOG))
        self.title.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #cccccc; font-family: 'SimHei';"
        )

        tabBar.addWidget(icon)
        tabBar.addWidget(self.title)
        tabBar.addStretch()

        self.clearBtn = PushButton(FluentIcon.BROOM, I18n.get(I18nKey.CLEAR))
        self.clearBtn.clicked.connect(self.clear_log)
        tabBar.addWidget(self.clearBtn)

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
        if logger.debug_mode:
            self.appendLog(I18n.get(I18nKey.DEBUG_MODE_ON), "info")

    def _on_log_info(self, msg: str):
        self.appendLog(msg, "info")

    def _on_log_warning(self, msg: str):
        self.appendLog(msg, "warning")

    def _on_log_error(self, msg: str):
        self.appendLog(msg, "error")

    def appendLog(self, message: str, level: str = "info"):
        """
        添加日志
        level: 'info' | 'warning' | 'error' | 'success'
        """
        colors = {
            "info":    "#12aa9c",
            "warning": "#f0a040",
            "error":   "#e04040",
            "success": "#66bb6a",
        }
        c = colors.get(level, "#12aa9c")

        tags = {
            "info":    "INFO",
            "warning": "WARN",
            "error":   "ERROR",
            "success": "OK",
        }
        tag = tags.get(level, "INFO")

        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")

        html = (
            f'<p style="margin:2px 0; font-size:13px; line-height:1.6;">'
            f'<span style="color:#888888;">{timestamp}</span>&nbsp;'
            f'<span style="color:{c}; font-weight:bold;">[{tag}]</span>&nbsp;'
            f'<span style="color:#cccccc;">{message}</span>'
            f'</p>'
        )

        if self.textEdit.toPlainText():
            html = self.textEdit.toHtml() + html
        self.textEdit.setHtml(html)
        self.scroll_to_bottom()

    def clear_log(self):
        self.textEdit.clear()

    def scroll_to_bottom(self):
        cursor = self.textEdit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.textEdit.setTextCursor(cursor)
        self.textEdit.ensureCursorVisible()

    # ==================================================================
    # 国际化刷新
    # ==================================================================

    def refresh_texts(self):
        """语言切换后刷新所有文本"""
        self.title.setText(I18n.get(I18nKey.RUN_LOG))
        self.clearBtn.setText(I18n.get(I18nKey.CLEAR))