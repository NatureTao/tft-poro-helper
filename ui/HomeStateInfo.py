"""
挂机统计组件
展示：对局统计、运行时长、通行证信息、段位
自适应高度，与日志区一起拉伸
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QWidget
from qfluentwidgets import CardWidget, FluentIcon, IconWidget, ProgressBar

from services.lol_client_service import lol
from ui.i18n import I18n, I18nKey


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

        # ---- 字体 ----
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setWeight(QFont.Weight.DemiBold)

        normal_font = QFont()
        normal_font.setPointSize(12)

        small_font = QFont()
        small_font.setPointSize(8)
        small_font.setWeight(QFont.Weight.Light)

        big_font = QFont()
        big_font.setPointSize(14)
        big_font.setWeight(QFont.Weight.DemiBold)

        # ==============================================================
        # 标题
        # ==============================================================
        self.title = QLabel(I18n.get(I18nKey.STATS))
        self.title.setFont(title_font)
        self.title.setStyleSheet("color: #ffffff;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vBoxLayout.addWidget(self.title)

        # ==============================================================
        # 三指标
        # ==============================================================
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        self.stat_labels = {}
        self.stat_header_labels = {}
        for icon_key, label_key, key, suffix in [
            ("GAME",        I18nKey.THIS_GAME,   "session_games", "局"),
            ("PIE_SINGLE",  I18nKey.TOTAL_GAMES, "total_games",   "局"),
            ("HISTORY",     I18nKey.RUNTIME,     "uptime",        "00:00:00"),
        ]:
            box = QVBoxLayout()
            box.setSpacing(2)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)

            header = QHBoxLayout()
            header.setSpacing(4)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon = IconWidget(getattr(FluentIcon, icon_key))
            icon.setFixedSize(16, 16)
            lbl = QLabel(I18n.get(label_key))
            lbl.setFont(small_font)
            lbl.setStyleSheet("color: #888888;")
            header.addWidget(icon)
            header.addWidget(lbl)

            val = QLabel(f"0 {I18n.get(I18nKey.GAME_UNIT)}" if suffix == "局" else suffix)
            val.setFont(big_font)
            val.setStyleSheet("color: #ffffff;")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)

            box.addLayout(header)
            box.addWidget(val)
            row1.addLayout(box, 1)

            self.stat_labels[key] = val
            self.stat_header_labels[key] = lbl

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
        self.passHeader = QLabel(I18n.get(I18nKey.PASS))
        self.passHeader.setFont(normal_font)
        self.passHeader.setStyleSheet("color: #cccccc;")
        self.vBoxLayout.addWidget(self.passHeader)

        self.passNameLabel = QLabel(I18n.get(I18nKey.PASS_WAIT))
        self.passNameLabel.setFont(normal_font)
        self.passNameLabel.setStyleSheet("color: #ffffff;")

        self.passLevelLabel = QLabel("Lv.0")
        self.passLevelLabel.setFont(title_font)
        self.passLevelLabel.setStyleSheet("color: #12aa9c;")

        self.passProgress = ProgressBar()
        self.passProgress.setFixedHeight(8)
        self.passProgress.setMaximum(1)
        self.passProgress.setValue(0)

        self.passDetailLabel = QLabel("0 / 0 XP")
        self.passDetailLabel.setFont(small_font)
        self.passDetailLabel.setStyleSheet("color: #888888;")

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
        self.rankTitle = QLabel(I18n.get(I18nKey.TFT_RANK))
        self.rankTitle.setFont(normal_font)
        self.rankTitle.setStyleSheet("color: #cccccc;")
        rankHeader.addWidget(rankIcon)
        rankHeader.addWidget(self.rankTitle)
        rankHeader.addStretch()
        self.vBoxLayout.addLayout(rankHeader)

        self.rankValueLabel = QLabel(I18n.get(I18nKey.UNRANKED))
        self.rankValueLabel.setFont(big_font)
        self.rankValueLabel.setStyleSheet("color: #ffd700;")
        self.vBoxLayout.addWidget(self.rankValueLabel)

        self.rankDetailLabel = QLabel(
            f"{I18n.get(I18nKey.SOLO_RANK)}: -- | "
            f"{I18n.get(I18nKey.FLEX_RANK)}: -- | "
            f"{I18n.get(I18nKey.TURBO_RANK)}: --"
        )
        self.rankDetailLabel.setFont(small_font)
        self.rankDetailLabel.setStyleSheet("color: #777777;")
        self.vBoxLayout.addWidget(self.rankDetailLabel)

    # ==================================================================
    # 内部方法
    # ==================================================================
    def _get_tier_color(self, rank_text: str) -> str:
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
            self.stat_labels["session_games"].setText(f"{session_games} {I18n.get(I18nKey.GAME_UNIT)}")
        if total_games is not None:
            self.total_games = total_games
            self.stat_labels["total_games"].setText(f"{total_games} {I18n.get(I18nKey.GAME_UNIT)}")
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
            self.passNameLabel.setText(I18n.get(I18nKey.PASS_WAIT))
            self.passLevelLabel.setText("Lv.0")
            self.passProgress.setMaximum(1)
            self.passProgress.setValue(0)
            self.passDetailLabel.setText("0 / 0 XP")

        rank = lol.rank_tft if lol.rank_tft != "--" else I18n.get(I18nKey.UNRANKED)
        self.rankValueLabel.setText(rank)
        self.rankValueLabel.setStyleSheet(
            f"color: {self._get_tier_color(rank)};"
        )
        self.rankDetailLabel.setText(
            f"{I18n.get(I18nKey.SOLO_RANK)}: {lol.rank_solo} | "
            f"{I18n.get(I18nKey.FLEX_RANK)}: {lol.rank_flex} | "
            f"{I18n.get(I18nKey.TURBO_RANK)}: {lol.rank_tft_turbo}"
        )

    def refresh_texts(self):
        """语言切换后刷新所有文本"""
        self.title.setText(I18n.get(I18nKey.STATS))
        self.passHeader.setText(I18n.get(I18nKey.PASS))
        self.rankTitle.setText(I18n.get(I18nKey.TFT_RANK))
        for key, lbl in self.stat_header_labels.items():
            if key == "session_games":
                lbl.setText(I18n.get(I18nKey.THIS_GAME))
            elif key == "total_games":
                lbl.setText(I18n.get(I18nKey.TOTAL_GAMES))
            elif key == "uptime":
                lbl.setText(I18n.get(I18nKey.RUNTIME))

        # 刷新统计数字单位
        self.update_stats(
            session_games=self.session_games,
            total_games=self.total_games,
            uptime_seconds=self.session_uptime
        )
        self.refresh_from_service()