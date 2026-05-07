"""
首页用户信息组件
左侧：头像 + 玩家名称（垂直居中）
"""
from PySide6.QtCore import Qt, Signal, QRunnable, QObject
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel
from qfluentwidgets import CardWidget

from ui.RadialGauge import PlayerProfileWidget
from ui.service import lol


class HomeUserInfo(CardWidget):
    """首页用户信息卡片"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.refresh_display()

    def setup_ui(self):
        """构建 UI 布局"""
        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(24, 16, 24, 16)

        # ---- 左侧：头像 + 玩家名（垂直居中） ----
        leftVBox = QVBoxLayout()
        leftVBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        leftVBox.setSpacing(4)

        self.profile = PlayerProfileWidget(width=160, height=160)

        self.playerName = QLabel("Poro")
        self.playerName.setStyleSheet("font-size: 20px; color: #cccccc;")
        self.playerName.setAlignment(Qt.AlignmentFlag.AlignCenter)

        leftVBox.addWidget(self.profile)
        leftVBox.addWidget(self.playerName)

        self.hBoxLayout.addLayout(leftVBox)


    # ==================================================================
    # 刷新
    # ==================================================================

    def refresh_display(self):
        """初始显示"""
        self._update_profile(lol)

    def updateData(self, lol_service=None):
        """定时刷新回调"""
        data = lol_service if lol_service else lol
        self._update_profile(data)

    def _update_profile(self, data):
        """更新头像、等级环、徽章、玩家名"""
        if data.avatar is not None:
            pix = QPixmap()
            pix.loadFromData(data.avatar)
            self.profile.set_avatar(pix)
        else:
            self.profile.set_default_avatar()

        self.profile.set_level(data.summonerLevel)
        self.profile.set_progress(data.xpSinceLastLevel, max(data.xpUntilNextLevel, 1))
        self.playerName.setText(f"{data.gameName}")


# ======================================================================
# 后台刷新线程
# ======================================================================

class RefreshSignals(QObject):
    finished = Signal(object)


class RefreshTask(QRunnable):
    def __init__(self, callback):
        super().__init__()
        self.signals = RefreshSignals()
        self.signals.finished.connect(callback)

    def run(self):
        lol.refresh_client()
        self.signals.finished.emit(lol)