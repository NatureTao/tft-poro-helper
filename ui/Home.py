"""首页页面组件"""
import threading

from PySide6.QtCore import Qt, QTimer, QThreadPool
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout
from qfluentwidgets import FluentIcon, PushButton

from ui.HomeQuickSettings import HomeQuickSettings
from ui.HomeUserInfo import HomeUserInfo, RefreshTask
from ui.HomeStateInfo import HomeStateInfo
from ui.HomeConsole import HomeConsole
from ui.i18n import I18n, I18nKey

class Home(QFrame):
    """首页"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.timer = None
        self.lock = threading.Lock()
        self.controller = None
        self.is_running = False
        self._session_start = None
        self._game_count = 0
        self.setObjectName(I18n.get(I18nKey.HOME_PAGE_NAME))

        # ---- 主布局 ----
        self.vBoxLayout = QVBoxLayout(self)

        # ---- 上区：水平布局 ----
        topHBox = QHBoxLayout()
        topHBox.setSpacing(12)

        self.quickSettings = HomeQuickSettings(self)

        # 头像 + 按钮垂直布局
        userVBox = QVBoxLayout()
        userVBox.setSpacing(0)

        self.userInfoModule = HomeUserInfo(self)
        self.startBtn = PushButton(FluentIcon.PLAY_SOLID, I18n.get(I18nKey.START_BOT))
        self.startBtn.setFixedHeight(120)
        start_font = QFont()
        start_font.setPointSize(14)
        start_font.setWeight(QFont.Weight.DemiBold)
        self.startBtn.setFont(start_font)
        self.startBtn.clicked.connect(self._on_start_clicked)

        userVBox.addWidget(self.userInfoModule)
        userVBox.addSpacing(8)
        userVBox.addWidget(self.startBtn)


        self.statsModule = HomeStateInfo(self)

        topHBox.addWidget(self.quickSettings)
        topHBox.addLayout(userVBox)
        topHBox.addWidget(self.statsModule, 1)
        topHBox.addStretch()

        self.vBoxLayout.addLayout(topHBox)

        # ---- 下区：日志 ----
        self.consoleModule = HomeConsole(self)
        self.vBoxLayout.addWidget(self.consoleModule, 1)

        self._start_auto_refresh()

    def set_controller(self, controller):
        self.controller = controller
        self.consoleModule.set_controller(controller)
        self.quickSettings.load_settings()

    def refresh_all_texts(self):
        self.startBtn.setText(
            I18n.get(I18nKey.STOP_BOT) if self.is_running else I18n.get(I18nKey.START_BOT)
        )
        self.statsModule.refresh_texts()
        self.consoleModule.refresh_texts()

    def _on_start_clicked(self):
        """开始/结束挂机"""
        if self.controller is None:
            from utils.logger import logger
            logger.warning("引擎还在加载中，请稍候...")
            return

        if self.is_running:
            self.controller.stop()
            self.is_running = False
            self._session_start = None
            self.startBtn.setIcon(FluentIcon.PLAY_SOLID)
            self.startBtn.setText(I18n.get(I18nKey.START_BOT))
        else:
            self.consoleModule.clear_log()  # 清空上一局日志
            self.controller.start(smart_mode=True)
            self.is_running = True
            self._session_start = __import__('time').time()
            self._game_count += 1
            self.statsModule.update_stats(session_games=self._game_count, uptime_seconds=0)
            self.startBtn.setIcon(FluentIcon.POWER_BUTTON)
            self.startBtn.setText(I18n.get(I18nKey.STOP_BOT))

    def _start_auto_refresh(self):
        QThreadPool.globalInstance().setMaxThreadCount(1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_client_data)
        self.timer.start(1000)

    def _refresh_client_data(self):
        # 更新运行时（每秒）
        if self._session_start is not None:
            uptime = int(__import__('time').time() - self._session_start)
            self.statsModule.update_stats(
                session_games=self._game_count,
                total_games=self._game_count,
                uptime_seconds=uptime,
            )

        task = RefreshTask(self.userInfoModule.updateData)
        task.signals.finished.connect(self.statsModule.refresh_from_service)
        QThreadPool.globalInstance().start(task)