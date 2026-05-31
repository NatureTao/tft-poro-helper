"""
Arena 辅助函数模块
负责游戏对局数据的获取，包括：
- API 数据：等级、存活状态（Live Client Data API :2999）
- OCR 识别：血量排名、金币、回合时间、商店英雄、装备列表、备战区状态
"""
import time
import threading
from difflib import SequenceMatcher

import numpy as np
import requests
from PIL import ImageGrab

import screen_coords
import ocr
import game_assets
import mk_functions
from vec4 import Vec4


# ======================================================================
# API 数据获取（Live Client Data API :2999）
# ======================================================================

def fetch_level() -> int:
    """
    从 Live Client Data API 获取召唤师等级
    Returns:
        int: 当前等级，失败返回 1
    """
    try:
        response = requests.get(
            "https://127.0.0.1:2999/liveclientdata/allgamedata",
            timeout=10,
            verify=False,
        )
        return int(response.json()["activePlayer"]["level"])
    except (requests.exceptions.ConnectionError, KeyError):
        return 1


def fetch_alive() -> int:
    """
    从 Live Client Data API 判断召唤师是否存活
    Returns:
        int: 0=存活, 1=已死亡, None=获取失败
    """
    try:
        response = requests.get(
            "https://127.0.0.1:2999/liveclientdata/allgamedata",
            timeout=20,
            verify=False,
        )
        data = response.json()
        my_name = data["activePlayer"]["riotId"]
        for player in data["allPlayers"]:
            if player["riotId"] == my_name:
                return int(player["scores"]["deaths"])
    except (requests.exceptions.ConnectionError, KeyError):
        return None


# ======================================================================
# OCR 数据获取（屏幕识别）
# ======================================================================

def fetch_health_ranking() -> list:
    """
    通过 OCR 识别右侧血量面板，获取排名和血量
    Returns:
        list[tuple[int, int]]: [(排名, 血量), ...]，按排名升序
    """
    screen_capture = ImageGrab.grab(bbox=screen_coords.HEALTH_POS.get_coords())
    hp_list: list = []
    thread_list: list = []

    for index, pos in enumerate(screen_coords.HEALTH_ITEM_POS):
        thread = threading.Thread(
            target=_ocr_single_health, args=(screen_capture, pos, index, hp_list)
        )
        thread_list.append(thread)

    for thread in thread_list:
        thread.start()
        time.sleep(0.05)

    for thread in thread_list:
        thread.join()

    return hp_list


def _ocr_single_health(
    screen_capture: ImageGrab.Image, pos: Vec4, index: int, hp_list: list
) -> None:
    """OCR 识别单个位置的血量数字，有效则添加到 hp_list"""
    health_text: str = screen_capture.crop(pos.get_coords())
    health_text = ocr.get_text_from_image(image=health_text)
    try:
        if (
            health_text.isnumeric()
            and 3 >= len(health_text) == len(str(int(health_text)))
            and int(health_text) <= 150
        ):
            hp_list.append((index + 1, int(health_text)))
    except ValueError:
        pass


def fetch_gold() -> int:
    """OCR 识别当前金币数"""
    gold_text: str = ocr.get_text(
        screenxy=screen_coords.GOLD_POS.get_coords(), scale=1
    )
    try:
        return int(gold_text)
    except ValueError:
        return 0


def fetch_round_remaining_time() -> int:
    """OCR 识别回合剩余时间（秒）"""
    try:
        return int(ocr.get_text(
            screenxy=screen_coords.REMAINING_TIME_POS.get_coords(), scale=3
        ))
    except ValueError:
        return -1


def fetch_abnormal_gold() -> int:
    """S13 4-6 回合异常突变钱包金币数"""
    gold_text: str = ocr.get_text(
        screenxy=screen_coords.GOLD_ABNORMAL_POS.get_coords(), scale=3
    )
    try:
        return int(gold_text)
    except ValueError:
        return 0


def fetch_abnormal_name() -> str:
    """OCR 识别异常突变 BUFF 名称"""
    try:
        return str(ocr.get_text(
            screenxy=screen_coords.ABNORMAL_POS.get_coords(), scale=3
        ))
    except Exception:
        return ""


def fetch_shop() -> list:
    """OCR 识别商店中 5 个英雄的名称和位置，返回 [(槽位, 名称), ...]"""
    screen_capture = ImageGrab.grab(bbox=screen_coords.SHOP_POS.get_coords())
    shop: list = []
    thread_list: list = []

    for shop_index, name_pos in enumerate(screen_coords.CHAMP_NAME_POS):
        thread = threading.Thread(
            target=_ocr_single_champ, args=(screen_capture, name_pos, shop_index, shop)
        )
        thread_list.append(thread)

    for thread in thread_list:
        thread.start()
        time.sleep(0.01)

    for thread in thread_list:
        thread.join()

    return sorted(shop)


def _ocr_single_champ(
    screen_capture: ImageGrab.Image, name_pos: Vec4, shop_pos: int, shop_array: list
) -> None:
    """OCR 识别单个英雄名称，有效则添加到商店列表"""
    champ_text: str = screen_capture.crop(name_pos.get_coords())
    champ_text = ocr.get_text_from_image(image=champ_text)
    shop_array.append((shop_pos, _match_champion_name(champ_text)))


def fetch_items() -> list:
    """OCR 遍历装备栏获取装备名称列表"""
    item_bench: list = []
    for positions in screen_coords.ITEM_POS:
        mk_functions.move_mouse(positions[0].get_coords())
        item_text: str = ocr.get_text(
            screenxy=positions[1].get_coords(), scale=1
        )
        valid = _match_item_name(item_text)
        if valid is None:
            break
        item_bench.append(valid)

    mk_functions.move_mouse(screen_coords.DEFAULT_LOC.get_coords())
    return item_bench


# ======================================================================
# 备战区状态检测（颜色像素判断）
# ======================================================================

def find_empty_bench_slot() -> int:
    """查找备战区第一个空位（通过检测血条颜色），返回 0-8，-1 表示无空位"""
    for slot, positions in enumerate(screen_coords.BENCH_HEALTH_POS):
        screen_capture = ImageGrab.grab(bbox=positions.get_coords())
        screenshot_array = np.array(screen_capture)
        is_health_color = np.all(screenshot_array == [0, 255, 18], axis=-1)
        if not any(np.convolve(is_health_color.reshape(-1), np.ones(5), mode='valid')):
            return slot
    return -1


def check_bench_occupied() -> list:
    """检测备战区 9 个位置是否被占用，返回布尔值列表"""
    bench_occupied: list = []
    for positions in screen_coords.BENCH_HEALTH_POS:
        screen_capture = ImageGrab.grab(bbox=positions.get_coords())
        screenshot_array = np.array(screen_capture)
        is_health_color = np.all(screenshot_array == [0, 203, 15], axis=-1)
        occupied = any(np.convolve(is_health_color.reshape(-1), np.ones(5), mode='valid'))
        bench_occupied.append(occupied)
    return bench_occupied


# ======================================================================
# 名称匹配（模糊匹配）
# ======================================================================

def _match_champion_name(champ: str) -> str:
    """将 OCR 识别的英雄名称匹配为 game_assets 中的标准名称"""
    if champ in game_assets.CHAMPIONS:
        return champ
    return next(
        (
            champion
            for champion in game_assets.CHAMPIONS
            if SequenceMatcher(a=champion, b=champ).ratio() >= 0.7
        ),
        "",
    )


def _match_item_name(item: str) -> str | None:
    """将 OCR 识别的物品名称匹配为 game_assets 中的标准名称"""
    if item in game_assets.ITEMS:
        return item

    # 强化果实特殊处理
    if "强化果实" in item:
        long_match = next(
            (name for name in game_assets.ITEMS
             if name.startswith("强化果实") and len(name) > len("强化果实")),
            None
        )
        if long_match:
            return long_match

    return next(
        (
            valid_name
            for valid_name in game_assets.ITEMS
            if valid_name in item or SequenceMatcher(a=valid_name, b=item).ratio() >= 0.85
        ),
        None,
    )

"""
旧名称	新名称	说明
get_level()	fetch_level()	统一 fetch_ 前缀表示数据获取
get_alive()	fetch_alive()	同上
get_HP()	fetch_health_ranking()	明确是血量排名
get_little_hero_health()	_ocr_single_health()	私有函数，_ 前缀
get_gold()	fetch_gold()	统一前缀
get_round_remaining_time()	fetch_round_remaining_time()	统一前缀
get_abnormal_gold()	fetch_abnormal_gold()	统一前缀
get_abnormal()	fetch_abnormal_name()	明确是名称
get_shop()	fetch_shop()	统一前缀
get_champ()	_ocr_single_champ()	私有函数
get_items()	fetch_items()	统一前缀
empty_slot()	find_empty_bench_slot()	语义更清晰
bench_occupied_check()	check_bench_occupied()	动词在前
valid_champ()	_match_champion_name()	明确是匹配
valid_item()	_match_item_name()	明确是匹配
"""

if __name__ == "__main__":
    print(check_bench_occupied())