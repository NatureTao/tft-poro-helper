"""
自定义圆形进度条组件（可缩放版）
"""
from PySide6.QtCore import Qt, QRectF, QRect
from PySide6.QtGui import (
    QColor, QPainter, QPen, QFont,
    QPainterPath, QLinearGradient, QPixmap
)
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ProgressBar, isDarkTheme
from pathlib import Path

# ======================================================================
# 基准样式参数（基于 RING_SIZE=140 设计，缩放时等比变换）
# ======================================================================
RING_SIZE = 140
RING_STROKE = 8
RING_GAP_ANGLE = 50
RING_START_ANGLE = 245
AVATAR_GAP = 4
BADGE_W = 60
BADGE_H = 24
BADGE_RADIUS = 12
BADGE_BORDER = 3
SHADOW_BLUR = 8
SHADOW_OFFSET_Y = 2
BADGE_WIDGET_W = BADGE_W + BADGE_BORDER * 2 + SHADOW_BLUR * 2
BADGE_WIDGET_H = BADGE_H + BADGE_BORDER * 2 + SHADOW_BLUR + SHADOW_OFFSET_Y
BADGE_OVERLAP = 20


class RadialGauge(ProgressBar):
    """拱形进度环"""

    def __init__(self, parent=None, diameter=RING_SIZE):
        super().__init__(parent, useAni=False)
        self.setTextVisible(False)
        self.diameter = diameter
        self._strokeWidth = int(RING_STROKE * diameter / RING_SIZE)
        self.setFixedSize(diameter, diameter)
        self.progressColor = QColor("#12aa9c")


    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        cw = self._strokeWidth
        margin = cw / 2
        d = self.diameter
        arc_rect = QRectF(margin, margin, d - cw, d - cw)
        full_span = 360 - RING_GAP_ANGLE

        bg = QColor(255, 255, 255, 28) if isDarkTheme() else QColor(0, 0, 0, 22)
        pen = QPen(bg, cw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(arc_rect, RING_START_ANGLE * 16, -full_span * 16)

        if self.maximum() > self.minimum():
            ratio = self.val / (self.maximum() - self.minimum())
            span = int(full_span * ratio)
            pen.setColor(self.progressColor)
            painter.setPen(pen)
            painter.drawArc(arc_rect, RING_START_ANGLE * 16, -span * 16)


class CircleAvatar(QWidget):
    """圆形头像"""

    def __init__(self, parent=None, size=116):
        super().__init__(parent)
        self.size = size
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._pixmap = None

    def setPixmap(self, pixmap: QPixmap):
        if pixmap.isNull():
            return
        s = self.size
        scaled = pixmap.scaled(s, s, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
        cx = (scaled.width() - s) // 2
        cy = (scaled.height() - s) // 2
        self._pixmap = scaled.copy(QRect(cx, cy, s, s))
        self.update()

    def paintEvent(self, e):
        if self._pixmap is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, self.size, self.size)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, self._pixmap)


class LevelBadge(QWidget):
    """等级徽章"""

    def __init__(self, parent=None, w=BADGE_WIDGET_W, h=BADGE_WIDGET_H):
        super().__init__(parent)
        self.setFixedSize(w, h)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._text = ""
        self.badge_radius = BADGE_RADIUS
        self.border = BADGE_BORDER

    def setText(self, text: str):
        self._text = text
        self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        b = self.border
        s = SHADOW_BLUR
        rect = QRectF(s, s // 2, self.width() - s * 2, self.height() - s - SHADOW_OFFSET_Y)
        r = self.badge_radius

        # 阴影
        for i in range(SHADOW_BLUR):
            alpha = 35 * (1 - i / SHADOW_BLUR)
            offset = i * 0.7
            path = QPainterPath()
            path.addRoundedRect(
                rect.adjusted(-offset, SHADOW_OFFSET_Y - offset, offset, SHADOW_OFFSET_Y + offset),
                r + offset, r + offset
            )
            painter.fillPath(path, QColor(0, 0, 0, int(alpha)))

        # 渐变
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, QColor("#0B7A7E"))
        grad.setColorAt(1, QColor("#10A0A4"))
        body = QPainterPath()
        body.addRoundedRect(rect, r, r)
        painter.fillPath(body, grad)

        # 边框
        painter.setPen(QPen(QColor(255, 255, 255, 220), b,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        bp = QPainterPath()
        bp.addRoundedRect(rect, r, r)
        painter.drawPath(bp)

        # 文字
        painter.setPen(QColor(255, 255, 255, 240))
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)


class PlayerProfileWidget(QWidget):
    """可缩放组合组件"""

    def __init__(self, parent=None, width=160, height=180):
        super().__init__(parent)
        self.setFixedSize(width, height)

        scale = width / (RING_SIZE + BADGE_WIDGET_W // 2)
        ring_d = int(RING_SIZE * scale)
        ring_x = (width - ring_d) // 2

        # 头像 = 圆环内径 - 间距（修正居中的关键）
        inner = ring_d - int(RING_STROKE * scale) * 2
        avatar_s = inner - AVATAR_GAP * 2

        badge_w = int(BADGE_WIDGET_W * scale)
        badge_h = int(BADGE_WIDGET_H * scale)
        overlap = int(BADGE_OVERLAP * scale)

        self.ring = RadialGauge(self, diameter=ring_d)
        self.ring.move(ring_x, 0)

        self.avatar = CircleAvatar(self, size=avatar_s)
        ax = ring_x + (ring_d - avatar_s) // 2
        ay = (ring_d - avatar_s) // 2
        self.avatar.move(ax, ay)

        self.badge = LevelBadge(self, w=badge_w, h=badge_h)
        bx = (width - badge_w) // 2
        by = ring_d - overlap
        self.badge.move(bx, by)
        self.setFixedSize(width, ring_d + badge_h - overlap)

    def set_default_avatar(self):
        avatar_path = Path(__file__).parent / "icon" / "default.jpg"
        pix = QPixmap(str(avatar_path))
        if not pix.isNull():
            self.avatar.setPixmap(pix)

    def set_avatar(self, pix: QPixmap):
        self.avatar.setPixmap(pix)

    def set_level(self, level: int):
        self.badge.setText(f"Lv.{level}")

    def set_progress(self, current: int, maximum: int):
        self.ring.setMaximum(maximum)
        self.ring.setValue(current)