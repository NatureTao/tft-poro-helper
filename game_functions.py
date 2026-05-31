"""
Game类用于检索相关数据的函数
"""
from time import sleep
import cv2
import numpy as np
from PIL import ImageGrab
from ultralytics import YOLO
import screen_coords
import ocr
import game_assets
import mk_functions
from utils.logger import logger

# 全局加载 YOLO 模型，只加载一次
_yolo_model = None

def set_yolo_model(model):
    """从外部注入预加载的 YOLO 模型，避免游戏中重复加载"""
    global _yolo_model  
    _yolo_model = model

def _get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        import os
        os.environ["ULTRALYTICS_AUTO_UPDATE"] = "false"
        logger.info("加载 YOLO 模型 → tft_yolo_v5.onnx")
        _yolo_model = YOLO("models/tft_yolo_v5.onnx", task="detect", verbose=False)
        logger.info("YOLO 模型加载完成")
    return _yolo_model


def get_round() -> list[str, int]:
    """获取当前游戏回合"""
    screen_capture = ImageGrab.grab(bbox=screen_coords.ROUND_POS.get_coords())
    round_three = screen_capture.crop(screen_coords.ROUND_POS_THREE.get_coords())
    game_round: str = ocr.get_text_from_image(image=round_three)
    if game_round in game_assets.ROUNDS:
        return [game_round, 3]

    round_two = screen_capture.crop(screen_coords.ROUND_POS_TWO.get_coords())
    game_round: str = ocr.get_text_from_image(image=round_two)
    if game_round in game_assets.ROUNDS:
        return [game_round, 2]

    round_one = screen_capture.crop(screen_coords.ROUND_POS_ONE.get_coords())
    game_round: str = ocr.get_text_from_image(image=round_one)
    if game_round in game_assets.ROUNDS:
        return [game_round, 1]
    return ["999-999", 0]


def check_encounter_round() -> list[str]:
    """通过检查回合文本获取游戏回合列表"""
    round_list: list = []
    for positions in screen_coords.ROUND_ENCOUNTER_ICON_POS:
        mk_functions.move_mouse(positions[0].get_coords())
        round_message: str = ocr.get_text(
            screenxy=positions[1].get_coords(),
            scale=3
        )
        if any(keyword in round_message for keyword in ["选秀"]):
            round_list.append("carousel")
        elif any(keyword in round_message for keyword in ["奇遇出现了！"]):
            round_list.append("encounter")
        elif any(
                keyword in round_message for keyword in ["对抗：石甲虫", "对抗：暗影狼", "对抗：锋喙鸟", "对抗：远古巨龙"]):
            round_list.append("pve")
        else:
            round_list.append("pvp")
    mk_functions.move_mouse(screen_coords.DEFAULT_LOC.get_coords())
    return round_list


def pickup_items() -> None:
    """使用 YOLO 检测并拾取战利品法球"""
    model = _get_yolo_model()

    # 截取游戏画面
    screenshot = ImageGrab.grab()
    frame = np.array(screenshot)
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # YOLO 检测
    results = model(frame, verbose=False)

    if not results or len(results[0].boxes) == 0:
        logger.info("  YOLO未检测到法球")
        return

    # 获取检测到的法球
    detections = []
    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)
        detections.append({
            'class': cls_id,  # 0: blue, 1: golden, 2: white
            'confidence': conf,
            'center': (cx, cy)
        })

    # 按优先级排序：golden(1) > blue(0) > white(2)
    priority = {1: 0, 0: 1, 2: 2}
    detections.sort(key=lambda d: priority.get(d['class'], 99))

    class_names = {0: 'blue', 1: 'golden', 2: 'white'}
    logger.info(f"  YOLO检测到 {len(detections)} 个法球")

    for i, det in enumerate(detections):
        name = class_names.get(det['class'], 'unknown')
        cx, cy = det['center']
        logger.info(f"  拾取法球 [{i+1}/{len(detections)}] {name} ({cx},{cy}) 置信度:{det['confidence']:.2f}")
        mk_functions.right_click((cx, cy))
        sleep(1.5)


def _ocr_single_champ_carousel(tft_round: str) -> None:
    """从选秀界面拿取英雄"""
    while tft_round == get_round()[0]:
        mk_functions.right_click(screen_coords.CAROUSEL_LOC.get_coords())
        sleep(0.7)
    sleep(3)


def check_alive() -> bool:
    """检查屏幕看玩家是否还活着"""
    if ocr.get_text(screenxy=screen_coords.EXIT_NOW_POS.get_coords(), scale=3) == '现在退出':
        return False
    return (
            ocr.get_text(
                screenxy=screen_coords.VICTORY_POS.get_coords(),
                scale=3
            )
            != '现在退出'
    )


def exit_game() -> None:
    """退出游戏"""
    mk_functions.left_click(screen_coords.EXIT_NOW_LOC.get_coords())


def default_pos() -> None:
    """将鼠标移动到默认位置，以确保没有数据被OCR阻止"""
    mk_functions.left_click(screen_coords.DEFAULT_LOC.get_coords())


def forfeit() -> None:
    """认输"""
    mk_functions.press_esc()
    mk_functions.left_click(screen_coords.SURRENDER_LOC.get_coords())
    sleep(0.1)
    mk_functions.left_click(screen_coords.SURRENDER_TWO_LOC.get_coords())
    sleep(1)


if __name__ == '__main__':
    while True:
        print(get_round())
        sleep(1)