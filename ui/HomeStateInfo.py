"""
挂机统计组件
展示：对局统计、运行时长、通行证信息、段位
自适应高度，与日志区一起拉伸
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QWidget
from qfluentwidgets import CardWidget, FluentIcon, IconWidget, ProgressBar

from ui.service import lol

class HomeStateInfo(CardWidget):
    """挂机统计卡片"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.TIER_COLORS = {
            '黑铁': '#5C5C5C',
            '青铜': '#6C4E2C',
            '白银': '#C0C2C1',
            '黄金': '#E2AD32',
            '铂金': '#32B898',
            '钻石': '#4290C7',
            '大师': '#7C40A8',
            '宗师': '#E20E0E',
            '王者': '#E2B832',
        }
        self.session_games = 0
        self.total_games = 0
        self.session_uptime = 0
        self.setup_ui()
        self.refresh_from_service()

    def setup_ui(self):
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(18, 14, 18, 14)
        self.vBoxLayout.setSpacing(10)

        # ==============================================================
        # 标题
        # ==============================================================
        title = QLabel("挂机统计")
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #ffffff; font-family: 'SimHei';"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vBoxLayout.addWidget(title)

        # ==============================================================
        # 三指标：本次对局 | 累计对局 | 运行时长
        # ==============================================================
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        self.stat_labels = {}
        for icon_key, label_text, key, default in [
            ("GAME", "本次对局", "session_games", "0 局"),
            ("PIE_SINGLE", "累计对局", "total_games", "0 局"),
            ("HISTORY", "运行时长", "uptime", "00:00:00"),
        ]:
            box = QVBoxLayout()
            box.setSpacing(2)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # 图标 + 文字 居中
            header = QHBoxLayout()
            header.setSpacing(4)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon = IconWidget(getattr(FluentIcon, icon_key))
            icon.setFixedSize(16, 16)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 12px; color: #888888; font-family: 'SimHei';")
            header.addWidget(icon)
            header.addWidget(lbl)

            val = QLabel(default)
            val.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff;")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)

            box.addLayout(header)
            box.addWidget(val)
            row1.addLayout(box, 1)  # 等宽拉伸，各占 1/3

            self.stat_labels[key] = val

        row1.addStretch()
        self.vBoxLayout.addLayout(row1)

        # ==============================================================
        # 分隔线
        # ==============================================================
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.08);")
        self.vBoxLayout.addWidget(sep)

        # ==============================================================
        # 通行证
        # ==============================================================
        passHeader = QLabel("通行证")
        passHeader.setStyleSheet("font-size: 13px; font-weight: bold; color: #cccccc;")
        self.vBoxLayout.addWidget(passHeader)

        self.passNameLabel = QLabel("等待游戏启动")
        self.passNameLabel.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")

        self.passLevelLabel = QLabel("Lv.0")
        self.passLevelLabel.setStyleSheet("font-size: 26px; font-weight: bold; color: #12aa9c;")

        self.passProgress = ProgressBar()
        self.passProgress.setFixedHeight(8)
        self.passProgress.setMaximum(1)
        self.passProgress.setValue(0)

        self.passDetailLabel = QLabel("0 / 0 XP")
        self.passDetailLabel.setStyleSheet("font-size: 11px; color: #888888;")

        self.vBoxLayout.addWidget(self.passNameLabel)
        self.vBoxLayout.addWidget(self.passLevelLabel)
        self.vBoxLayout.addWidget(self.passProgress)
        self.vBoxLayout.addWidget(self.passDetailLabel)

        # ==============================================================
        # 分隔线
        # ==============================================================
        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background: rgba(255,255,255,0.08);")
        self.vBoxLayout.addWidget(sep2)

        # ==============================================================
        # 段位
        # ==============================================================
        rankHeader = QHBoxLayout()
        rankHeader.setSpacing(4)
        rankIcon = IconWidget(FluentIcon.FLAG)
        rankIcon.setFixedSize(16, 16)
        rankTitle = QLabel("云顶段位")
        rankTitle.setStyleSheet("font-size: 13px; font-weight: bold; color: #cccccc;")
        rankHeader.addWidget(rankIcon)
        rankHeader.addWidget(rankTitle)
        rankHeader.addStretch()
        self.vBoxLayout.addLayout(rankHeader)

        self.rankValueLabel = QLabel("未定级")
        self.rankValueLabel.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffd700;")
        self.vBoxLayout.addWidget(self.rankValueLabel)

        self.rankDetailLabel = QLabel("单双: -- | 灵活: -- | 狂暴: --")
        self.rankDetailLabel.setStyleSheet("font-size: 11px; color: #777777;")
        self.vBoxLayout.addWidget(self.rankDetailLabel)

    # ==================================================================
    # 内部方法
    # ==================================================================
    def _get_tier_color(self, rank_text: str) -> str:
        """根据段位名返回对应颜色"""
        for tier, color in self.TIER_COLORS.items():
            if tier in rank_text:
                return color
        return '#cccccc'

    # ==================================================================
    # 更新
    # ==================================================================

    def update_stats(self, session_games=None, total_games=None, uptime_seconds=None):
        if session_games is not None:
            self.session_games = session_games
            self.stat_labels["session_games"].setText(f"{session_games} 局")
        if total_games is not None:
            self.total_games = total_games
            self.stat_labels["total_games"].setText(f"{total_games} 局")
        if uptime_seconds is not None:
            self.session_uptime = uptime_seconds
            h = uptime_seconds // 3600
            m = (uptime_seconds % 3600) // 60
            s = uptime_seconds % 60
            self.stat_labels["uptime"].setText(f"{h:02d}:{m:02d}:{s:02d}")

    def refresh_from_service(self):
        if lol.passes:
            main_pass = next(
                (p for p in lol.passes if p['type'] == 'Default'),
                lol.passes[0]
            )
            self.passNameLabel.setText(main_pass['name'])
            self.passLevelLabel.setText(f"Lv.{main_pass['level']}")
            self.passProgress.setMaximum(max(main_pass['total_xp'], 1))
            self.passProgress.setValue(main_pass['current_xp'])
            self.passDetailLabel.setText(
                f"{main_pass['current_xp']} / {main_pass['total_xp']} XP"
            )
        else:
            self.passNameLabel.setText("等待游戏启动")
            self.passLevelLabel.setText("Lv.0")
            self.passProgress.setMaximum(1)
            self.passProgress.setValue(0)
            self.passDetailLabel.setText("0 / 0 XP")

        rank = lol.rank_tft if lol.rank_tft != "未定级" else "未定级"
        self.rankValueLabel.setText(rank)
        self.rankValueLabel.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {self._get_tier_color(rank)};"
        )
        self.rankDetailLabel.setText(
            f"单双: {lol.rank_solo} | 灵活: {lol.rank_flex} | 狂暴: {lol.rank_tft_turbo}"
        )