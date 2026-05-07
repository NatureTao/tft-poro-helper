"""
垂直三段式切换按钮
"""
from PySide6.QtCore import Qt, QRectF, QPropertyAnimation, Property, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QFont, QMouseEvent
from PySide6.QtWidgets import QWidget


class VerticalToggleSwitch(QWidget):
    """垂直三段式切换按钮"""

    RADIUS = 10  # 固定圆角

    def __init__(self, texts=("", "", ""), parent=None):
        super().__init__(parent)
        self._texts = texts
        self._selected = 0
        self._anim_pos = 0.0
        self.setFixedWidth(120)

        self.bg_color = QColor(50, 50, 55)
        self.slider_color = QColor("#12aa9c")
        self.text_normal = QColor("#999999")
        self.text_selected = QColor("#ffffff")
        self.on_toggled = None

    def set_selected(self, index: int):
        self._selected = index
        self._anim_pos = float(index)
        self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        seg_h = (h - 4) / 3

        # 背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.bg_color)
        painter.drawRoundedRect(QRectF(0, 0, w, h), self.RADIUS, self.RADIUS)

        # 滑块
        slider_y = 2 + self._anim_pos * seg_h
        painter.setBrush(self.slider_color)
        painter.drawRoundedRect(QRectF(2, slider_y, w - 4, seg_h), self.RADIUS - 2, self.RADIUS - 2)

        # 文字
        font = QFont("Microsoft YaHei", 11)
        font.setBold(True)
        painter.setFont(font)

        for i in range(3):
            rect = QRectF(0, i * seg_h + 2, w, seg_h)
            if i == self._selected:
                painter.setPen(self.text_selected)
            else:
                painter.setPen(self.text_normal)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._texts[i])

    def mousePressEvent(self, event: QMouseEvent):
        seg_h = (self.height() - 4) / 3
        y = event.position().y()
        new_index = min(int(y / seg_h), 2)
        if new_index != self._selected:
            self._selected = new_index
            self._animate(new_index)
            if self.on_toggled:
                self.on_toggled(new_index)
        self.update()

    def _animate(self, target: int):
        self._anim = QPropertyAnimation(self, b"anim_pos")
        self._anim.setDuration(250)
        self._anim.setStartValue(self._anim_pos)
        self._anim.setEndValue(float(target))
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(lambda: self.update())
        self._anim.start()

    def get_anim_pos(self):
        return self._anim_pos

    def set_anim_pos(self, val):
        self._anim_pos = val

    anim_pos = Property(float, get_anim_pos, set_anim_pos)