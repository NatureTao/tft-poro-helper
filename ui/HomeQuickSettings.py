"""
快速设置组件
- 语言切换（VerticalToggleSwitch 三段式）
- 模式选择（ToggleSwitch 二段式）
- 日志等级（ToggleSwitch 二段式）
一体式胶囊切换按钮，填充色滑动过渡
"""
from PySide6.QtCore import Qt, QRectF, QPropertyAnimation, Property, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QFont, QMouseEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from qfluentwidgets import CardWidget

import settings
from ui.VerticalToggleSwitch import VerticalToggleSwitch
from utils.logger import logger
from ui.i18n import I18n, I18nKey, Language

# 语言索引 → Language 枚举映射
LANG_INDEX_MAP = {
    0: Language.ZH_CN,
    1: Language.ZH_TW,
    2: Language.EN_US,
}


# ======================================================================
# 二段式胶囊切换按钮
# ======================================================================

class ToggleSwitch(QWidget):
    """水平二段式胶囊切换按钮，滑动动画"""

    def __init__(self, left_text="", right_text="", parent=None):
        super().__init__(parent)
        self._left_text = left_text
        self._right_text = right_text
        self._selected = 0           # 0=左, 1=右
        self._anim_pos = 0.0         # 动画位置 0.0~1.0
        self.setFixedHeight(34)

        # 颜色配置
        self.bg_color = QColor(50, 50, 55)
        self.slider_color = QColor("#12aa9c")
        self.text_normal = QColor("#999999")
        self.text_selected = QColor("#ffffff")

        self.on_toggled = None       # 回调函数 signature: (index: int)

    # ==================================================================
    # 公开接口
    # ==================================================================

    def set_selected(self, index: int, animated=False):
        """设置选中项：0=左，1=右"""
        self._selected = index
        self._anim_pos = float(index)
        self.update()

    def selected(self) -> int:
        """返回当前选中索引"""
        return self._selected

    def set_texts(self, left_text: str, right_text: str):
        """更新左右文本（国际化用）"""
        self._left_text = left_text
        self._right_text = right_text
        self.update()

    # ==================================================================
    # 自绘
    # ==================================================================

    def paintEvent(self, e):
        """自绘背景胶囊 + 滑块 + 文字"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2

        # 背景胶囊
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.bg_color)
        painter.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        # 滑块
        slider_w = (w - 4) / 2
        slider_x = 2 + self._anim_pos * slider_w
        painter.setBrush(self.slider_color)
        painter.drawRoundedRect(QRectF(slider_x, 2, slider_w, h - 4), r - 2, r - 2)

        # 文字
        font = QFont("Microsoft YaHei", 11)
        font.setBold(True)
        painter.setFont(font)

        left_rect = QRectF(0, 0, w / 2, h)
        left_color = self._lerp_color(self.text_selected, self.text_normal, self._anim_pos)
        painter.setPen(left_color)
        painter.drawText(left_rect, Qt.AlignmentFlag.AlignCenter, self._left_text)

        right_rect = QRectF(w / 2, 0, w / 2, h)
        right_color = self._lerp_color(self.text_normal, self.text_selected, self._anim_pos)
        painter.setPen(right_color)
        painter.drawText(right_rect, Qt.AlignmentFlag.AlignCenter, self._right_text)

    def _lerp_color(self, c1: QColor, c2: QColor, t: float) -> QColor:
        """颜色线性插值"""
        return QColor(
            int(c1.red()   + (c2.red()   - c1.red())   * t),
            int(c1.green() + (c2.green() - c1.green()) * t),
            int(c1.blue()  + (c2.blue()  - c1.blue())  * t),
        )

    # ==================================================================
    # 交互 & 动画
    # ==================================================================

    def mousePressEvent(self, event: QMouseEvent):
        """点击切换"""
        new_index = 0 if event.position().x() < self.width() / 2 else 1
        if new_index != self._selected:
            self._selected = new_index
            self._animate(new_index)
            if self.on_toggled:
                self.on_toggled(new_index)
        self.update()

    def _animate(self, target: int):
        """滑动动画"""
        self._anim = QPropertyAnimation(self, b"anim_pos")
        self._anim.setDuration(250)
        self._anim.setStartValue(self._anim_pos)
        self._anim.setEndValue(float(target))
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(lambda: self.update())
        self._anim.start()

    # 动画属性（QPropertyAnimation 需要）
    def get_anim_pos(self):
        return self._anim_pos

    def set_anim_pos(self, val):
        self._anim_pos = val

    anim_pos = Property(float, get_anim_pos, set_anim_pos)


# ======================================================================
# 快速设置卡片
# ======================================================================

class HomeQuickSettings(CardWidget):
    """快速设置卡片：语言 → 模式选择 → 日志等级"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_lang = 0
        self.setup_ui()

    # ==================================================================
    # UI 构建
    # ==================================================================

    def setup_ui(self):
        """构建 UI 布局"""
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(16, 12, 16, 12)
        self.vBoxLayout.setSpacing(14)

        label_style = (
            "font-size: 15px; font-weight: bold; color: #ffffff; font-family: 'SimHei';"
        )

        # ---- 语言 ----
        self.langLabel = QLabel(I18n.get(I18nKey.LANGUAGE))
        self.langLabel.setStyleSheet(label_style)
        self.langLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        langLayout = QHBoxLayout()
        langLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.langSwitch = VerticalToggleSwitch(("简体中文", "繁體中文", "English"))
        self.langSwitch.setFixedWidth(180)
        self.langSwitch.setFixedHeight(110)
        self.langSwitch.on_toggled = self._on_lang_changed
        langLayout.addWidget(self.langSwitch)

        self.vBoxLayout.addWidget(self.langLabel)
        self.vBoxLayout.addLayout(langLayout)

        # ---- 模式选择 ----
        self.modeLabel = QLabel(I18n.get(I18nKey.MODE_SELECT))
        self.modeLabel.setStyleSheet(label_style)
        self.modeLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.modeSwitch = ToggleSwitch(I18n.get(I18nKey.MATCH), I18n.get(I18nKey.RANK))
        self.modeSwitch.setFixedWidth(180)
        self.modeSwitch.on_toggled = self._on_mode_changed

        self.vBoxLayout.addWidget(self.modeLabel)
        self.vBoxLayout.addWidget(self.modeSwitch)

        # ---- 日志等级 ----
        self.logLabel = QLabel(I18n.get(I18nKey.LOG_LEVEL))
        self.logLabel.setStyleSheet(label_style)
        self.logLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.logSwitch = ToggleSwitch(I18n.get(I18nKey.NORMAL), I18n.get(I18nKey.DEBUG))
        self.logSwitch.setFixedWidth(180)
        self.logSwitch.on_toggled = self._on_log_changed

        self.vBoxLayout.addWidget(self.logLabel)
        self.vBoxLayout.addWidget(self.logSwitch)

        self.vBoxLayout.addStretch()

    # ==================================================================
    # 设置加载
    # ==================================================================

    def load_settings(self):
        """从 settings 和 logger 加载当前状态"""
        self.langSwitch.set_selected(self._current_lang)
        self.modeSwitch.set_selected(0 if settings.QUEUE_ID == 1090 else 1)
        self.logSwitch.set_selected(1 if logger.debug_mode else 0)

    # ==================================================================
    # 回调 — 语言
    # ==================================================================

    def _on_lang_changed(self, index: int):
        """语言切换回调"""
        I18n.set_language(LANG_INDEX_MAP[index])
        self._refresh_texts()
        self._notify_home_refresh()

    def _refresh_texts(self):
        """刷新本组件所有国际化文本"""
        self.langLabel.setText(I18n.get(I18nKey.LANGUAGE))
        self.modeLabel.setText(I18n.get(I18nKey.MODE_SELECT))
        self.logLabel.setText(I18n.get(I18nKey.LOG_LEVEL))
        self.modeSwitch.set_texts(I18n.get(I18nKey.MATCH), I18n.get(I18nKey.RANK))
        self.logSwitch.set_texts(I18n.get(I18nKey.NORMAL), I18n.get(I18nKey.DEBUG))

    def _notify_home_refresh(self):
        """通知父级 Home 刷新所有子组件文本"""
        p = self.parent()
        while p and not hasattr(p, 'refresh_all_texts'):
            p = p.parent()
        if p:
            p.refresh_all_texts()

    # ==================================================================
    # 回调 — 模式 & 日志
    # ==================================================================

    def _on_mode_changed(self, index: int):
        """模式切换：0=匹配(1090)，1=排位(1100)"""
        settings.QUEUE_ID = 1090 if index == 0 else 1100

    def _on_log_changed(self, index: int):
        """日志等级：0=正常，1=调试"""
        if index == 1:
            logger.enable_debug()
        else:
            logger.disable_debug()