"""
处理游戏内部的棋盘/备战区状态
机器人用于决策的其他变量
"""
import math
import threading
from time import sleep

from PIL import ImageGrab

import game_assets
import mk_functions
import screen_coords
import settings
from champion import Champion
import comps
import ocr
import game_functions
import arena_functions
from vec4 import Vec4
from utils.logger import logger


class Arena:
    """
       Arena类，处理游戏逻辑，如棋盘和备战区状态
    """

    # pylint: disable=too-many-instance-attributes,too-many-public-methods
    def __init__(self, message_queue) -> None:
        self.message_queue = message_queue
        self.board_size = 0
        self.bench: list[None] = [None] * 9
        self.anvil_free: list[bool] = [False] * 9
        self.board: list = []
        self.board_unknown: list = []
        self.unknown_slots: list = comps.get_unknown_slots()
        self.champs_to_buy: dict = comps.champions_to_buy()
        self.board_names: list = []
        self.items: list = []
        self.final_comp = False
        self.level = 0
        self.augment_roll = True
        self.spam_roll = False
        self.HP: list = [None]
        self.active_portal: str = ""
        self.scorer = None  # 智能评分引擎（由 Game 注入）
        self.fixed_squad = None  # 固定阵容数据（由 Game 注入）
        self.current_comp = ""  # 当前推荐阵容名称
        self.locked_comp_heroes = None  # 2-4 锁定后的阵容英雄列表（不再重新评分）
        self.locked_comp_squad = None  # 锁定阵容的完整 squad dict（含站位数据）

    def portal_augment(self) -> None:
        """检查区域扩展并相应地设置标志"""
        mk_functions.move_mouse(screen_coords.PORTAL_AUGMENT_LOC.get_coords())
        sleep(1)
        region = ocr.get_text(
            screenxy=screen_coords.PORTAL_AUGMENT_POS.get_coords(), scale=3,
        )
        self.active_portal = region

        augment_flags = {
            "基础装备锻造器": "清除锻造器在 回合 1-3",
            "神器锻造器": "清除锻造器在 回合 1-3",
            "魔像训练师": "移动魔像到空白位置在 回合 1-4",
        }

        augment_name = next((name for name in augment_flags if name in region), None)

        if augment_name:
            flag = augment_flags[augment_name]
            logger.info(f"  地区奇遇: {region}| {flag}")
        else:
            logger.info(f"  地区奇遇: {region}")

    def fix_bench_state(self) -> None:
        """遍历备战区并修复未知的槽位"""
        bench_occupied: list = arena_functions.check_bench_occupied()
        for index, slot in enumerate(self.bench):
            if slot is None and bench_occupied[index]:
                mk_functions.right_click(screen_coords.BENCH_LOC[index].get_coords())
                champ_name: str = arena_functions._match_champion_name(
                    ocr.get_text(
                        screenxy=screen_coords.PANEL_NAME_LOC.get_coords(),
                        scale=3
                    )
                )
                if self.champs_to_buy.get(champ_name, 0) > 0:
                    logger.info(f"  备战区[{champ_name}]存在升星队列中")
                    champ_comp = comps.COMP.get(champ_name) or {}
                    self.bench[index] = Champion(
                        name=champ_name,
                        coords=screen_coords.BENCH_LOC[index].get_coords(),
                        build=self._get_build_items(champ_name),
                        slot=index,
                        size=game_assets.CHAMPIONS[champ_name]["Board Size"],
                        final_comp=champ_comp.get("final_comp", False),
                        trait1=game_assets.CHAMPIONS[champ_name]["Trait1"],
                        trait2=game_assets.CHAMPIONS[champ_name]["Trait2"],
                        trait3=game_assets.CHAMPIONS[champ_name]["Trait3"],
                        center=champ_comp.get("center", False),
                    )
                    self.champs_to_buy[champ_name] -= 1
                else:
                    logger.info(f" 备战区[{champ_name}]不在升星队列中")
                    self.bench[index] = "?"
                continue
            if isinstance(slot, str) and not bench_occupied[index]:
                self.bench[index] = None
                continue
            if isinstance(slot, Champion) and not bench_occupied[index]:
                self.bench[index] = None

    def _get_build_items(self, name: str) -> list:
        """获取英雄的预期装备列表：锁定阵容 > comps.COMP > 空"""
        if self.locked_comp_squad:
            items = self.locked_comp_squad.get("HERO", {}).get(name, {}).get("items", [])
            if items:
                return list(items)
        return comps.COMP.get(name, {}).get("items", []).copy()

    def bought_champion(self, name: str, slot: int) -> None:
        """购买英雄 并创建英雄实例"""
        champ_comp = comps.COMP.get(name) or {}
        self.bench[slot] = Champion(
            name=name,
            coords=screen_coords.BENCH_LOC[slot].get_coords(),
            build=self._get_build_items(name),
            slot=slot,
            size=game_assets.CHAMPIONS[name]["Board Size"],
            final_comp=champ_comp.get("final_comp", False),
            trait1=game_assets.CHAMPIONS[name]["Trait1"],
            trait2=game_assets.CHAMPIONS[name]["Trait2"],
            trait3=game_assets.CHAMPIONS[name]["Trait3"],
            center=champ_comp.get("center", False),
        )
        mk_functions.move_mouse(screen_coords.DEFAULT_LOC.get_coords())
        sleep(0.5)
        self.fix_bench_state()

    def have_champion(self) -> Champion | None:
        """检测备战区是否存在英雄"""
        return next(
            (
                champion
                for champion in self.bench
                if isinstance(champion, Champion)
                   and champion.name not in self.board_names
            ),
            None,
        )

    def _next_free_slot(self) -> int:
        """智能模式：找未占用的棋盘位置，优先后排（大下标 = 后排更安全）"""
        occupied = {c.index for c in self.board}
        for i in range(len(self.board_unknown)):
            occupied.add(self._unknown_slot_rev(i))
        # 从大到小遍历：后排(21-27) → 第三排(14-20) → 第二排(7-13) → 前排(0-6)
        for slot in reversed(self.unknown_slots):
            if slot not in occupied:
                return slot
        return 0

    def move_known(self, champion: Champion) -> None:
        """将英雄移动到棋盘上"""
        logger.info(f"  移动[{champion.name}]到棋盘")
        # 优先级：固定阵容 COMP > 锁定阵容 HERO seat > 空闲位置
        if champion.name in comps.COMP:
            board_index = comps.COMP[champion.name]["board_position"]
        elif self.locked_comp_squad:
            hero_data = self.locked_comp_squad.get("HERO", {}).get(champion.name)
            if hero_data and "seat" in hero_data:
                board_index = hero_data["seat"]
            else:
                board_index = self._next_free_slot()
        else:
            board_index = self._next_free_slot()
        destination = screen_coords.BOARD_LOC[board_index].get_coords()
        mk_functions.left_click(champion.coords)
        sleep(0.1)
        mk_functions.left_click(destination)
        champion.coords = destination
        old_bench_index = champion.index  # 保存备战席下标，先清备战席再改 index
        self.bench[old_bench_index] = None
        champion.index = board_index
        self.board.append(champion)
        self.board_names.append(champion.name)
        self.board_size += champion.size

    def _unknown_slot_rev(self, idx: int) -> int:
        """board_unknown 第 idx 个棋子对应的棋盘位置（从后排往前分配）"""
        return sorted(self.unknown_slots, reverse=True)[idx]

    def move_unknown(self) -> None:
        """将未识别的英雄移动到棋盘上（优先后排）"""
        for index, champion in enumerate(self.bench):
            if isinstance(champion, str):
                logger.info(f"  移动 {champion} 到棋盘")
                mk_functions.left_click(screen_coords.BENCH_LOC[index].get_coords())
                sleep(0.1)
                slot = self._unknown_slot_rev(len(self.board_unknown))
                mk_functions.left_click(
                    screen_coords.BOARD_LOC[slot].get_coords()
                )
                self.bench[index] = None
                self.board_unknown.append(champion)
                self.board_size += 1
                return

    def sell_bench(self) -> None:
        """出售备战区所有英雄"""
        for index, _ in enumerate(self.bench):
            mk_functions.press_e(screen_coords.BENCH_LOC[index].get_coords())
            self.bench[index] = None

    def unknown_in_bench(self) -> bool:
        """备战区是否有未知英雄"""
        return any(isinstance(slot, str) for slot in self.bench)

    def get_traits(self, champion_name):
        """获取指定英雄的羁绊信息"""
        traits = [game_assets.CHAMPIONS[champion_name][f"Trait{i}"] for i in range(1, 4)]
        return set(filter(None, traits))

    def move_champions(self) -> None:
        """将英雄移动到棋盘上"""
        self.level: int = arena_functions.fetch_level()
        while self.level > self.board_size:
            champion: Champion | None = self.have_champion()
            if champion is not None:
                self.move_known(champion)
            elif self.unknown_in_bench():
                self.move_unknown()
            else:
                bought_unknown = False
                shop: list = arena_functions.fetch_shop()
                count = 0
                for champion in shop:
                    count += 1
                    gold: int = arena_functions.fetch_gold()
                    common_traits = set()
                    for name in self.board_names:
                        common_traits.update(self.get_traits(name))
                    current_hero_traits = self.get_traits(champion[1]) if champion[1] else set()
                    character = any(trait in common_traits for trait in current_hero_traits)
                    none = not character
                    if none and self.level > self.board_size or count == shop.__len__():
                        character = True
                    _match_champion_name: bool = (
                            champion[1] in game_assets.CHAMPIONS
                            and game_assets.champion_gold_cost(champion[1]) <= gold
                            and game_assets.champion_board_size(champion[1]) == 1
                            and self.champs_to_buy.get(champion[1], -1) < 0
                            and champion[1] not in self.board_unknown
                            and character
                            and not self.locked_comp_heroes  # 锁定后不买打工仔
                    )
                    if _match_champion_name:
                        none_slot: int = arena_functions.find_empty_bench_slot()
                        mk_functions.left_click(
                            screen_coords.BUY_LOC[champion[0]].get_coords()
                        )
                        sleep(0.2)
                        self.bench[none_slot] = f"{champion[1]}"
                        self.move_unknown()
                        bought_unknown = True
                        break
                if not bought_unknown:
                    logger.info("  需清空备战区初始化")
                    self.sell_bench()
                    return

    def sync_board_state(self) -> None:
        """检测游戏是否自动上场了棋子（人口有缺但备战席有 Champion 没上去）"""
        expected = arena_functions.fetch_level()
        actual = self.board_size + len(self.board_unknown)
        if actual >= expected:
            return
        # 找备战席中已经有 Champion 实例但还没上场的
        for slot in self.bench:
            if isinstance(slot, Champion) and slot.name not in self.board_names:
                logger.info(f"  同步：检测到[{slot.name}]未上场，自动放置")
                self.move_known(slot)
                return
        # 如果备战席也没 Champion，从商店买一个便宜的打工仔占位（锁定后不买）
        if self.scorer and not self.locked_comp_heroes:
            gold = arena_functions.fetch_gold()
            shop = arena_functions.fetch_shop()
            for champ in shop:
                cost = game_assets.CHAMPIONS.get(champ[1], {}).get("Gold", 1)
                if cost <= gold and cost <= 2 and champ[1] not in self.board_unknown:
                    logger.info(f"  同步：买入打工仔[{champ[1]}]占人口")
                    none_slot = arena_functions.find_empty_bench_slot()
                    if none_slot != -1:
                        mk_functions.left_click(screen_coords.BUY_LOC[champ[0]].get_coords())
                        sleep(0.2)
                        self.bench[none_slot] = f"{champ[1]}"
                        self.move_unknown()
                    return

    def replace_unknown(self) -> None:
        """替换掉未识别的英雄（跳过已识别的）"""
        champion: Champion | None = self.have_champion()
        if len(self.board_unknown) > 0 and champion is not None:
            # 只替换仍为 ? 的未知棋子，已识别的保留
            try:
                idx = next(
                    i for i, v in enumerate(self.board_unknown)
                    if isinstance(v, str) and v in ("?", "")
                )
            except StopIteration:
                return
            pos = self._unknown_slot_rev(idx)
            mk_functions.press_e(
                screen_coords.BOARD_LOC[pos].get_coords()
            )
            self.board_unknown.pop(idx)
            self.board_size -= 1
            self.move_known(champion)

    def identify_board_unknowns(self) -> None:
        """右键棋盘上 ? 棋子 → OCR 识别名称"""
        for i in range(len(self.board_unknown)):
            slot = self.board_unknown[i]
            if isinstance(slot, str) and slot in ("?", ""):
                pos = self._unknown_slot_rev(i)
                mk_functions.right_click(
                    screen_coords.BOARD_LOC[pos].get_coords()
                )
                sleep(3)  # 等待棋子信息面板加载
                champ_name = arena_functions._match_champion_name(
                    ocr.get_text(
                        screenxy=screen_coords.PANEL_NAME_LOC.get_coords(),
                        scale=3,
                    )
                )
                if champ_name and champ_name in game_assets.CHAMPIONS:
                    logger.info(f"  识别棋盘未知棋子[{i}] → {champ_name}")
                    self.board_unknown[i] = champ_name

    def bench_cleanup(self) -> None:
        """出售未识别的英雄"""
        self.anvil_free: list[bool] = [False] * 9
        for index, champion in enumerate(self.bench):
            if champion == "?" or isinstance(champion, str):
                logger.info("  出售英雄")
                mk_functions.press_e(screen_coords.BENCH_LOC[index].get_coords())
                self.bench[index] = None
                self.anvil_free[index] = True
            elif isinstance(champion, Champion):
                if (
                        self.champs_to_buy.get(champion.name, -1) < 0
                        and champion.name in self.board_names
                ):
                    logger.info("  出售英雄")
                    mk_functions.press_e(screen_coords.BENCH_LOC[index].get_coords())
                    self.bench[index] = None
                    self.anvil_free[index] = True

    def clear_anvil(self) -> None:
        """消耗掉 备战区的武器库 (铁砧)"""
        isAnvil = False
        for index, champion in enumerate(self.bench):
            if champion is None and not self.anvil_free[index]:
                mk_functions.press_e(screen_coords.BENCH_LOC[index].get_coords())
        sleep(0.5)
        anvil_msg: str = ocr.get_text(
            screenxy=screen_coords.ANVIL_MSG_POS.get_coords(),
            scale=3
        )
        if anvil_msg == "选择一件":
            isAnvil = True
            logger.info(" 快速选择铁砧")
            mk_functions.left_click(screen_coords.BUY_LOC[2].get_coords())
            if isAnvil:
                game_functions.default_pos()
                sleep(1)

    def get_anvil_items(self) -> list:
        """返回铁砧上的物品"""
        screen_capture = ImageGrab.grab(bbox=screen_coords.ANVIL_ITEMS_POS.get_coords())
        items: list = []
        thread_list: list = []
        for index, pos in enumerate(screen_coords.ORDINARY_ANVIL_ITEM_POS):
            thread = threading.Thread(
                target=self.get_anvil_item, args=(screen_capture, pos, index, items)
            )
            thread_list.append(thread)
        for index, pos in enumerate(screen_coords.DIVINE_ANVIL_ITEM_POS):
            thread = threading.Thread(
                target=self.get_anvil_item, args=(screen_capture, pos, index, items)
            )
            thread_list.append(thread)
        for thread in thread_list:
            thread.start()
            sleep(0.05)
        for thread in thread_list:
            thread.join()
        return sorted(items)

    def get_anvil_item(self, screen_capture: ImageGrab.Image, pos: Vec4, index: int, items: list):
        """遍历识别每个铁砧物品"""
        item: str = screen_capture.crop(pos.get_coords())
        item: str = ocr.get_text_from_image(image=item)
        item = arena_functions._match_item_name(item)
        if item is not None:
            items.append((index, item))

    def place_items(self) -> None:
        """尝试遍历我的装备 并合成给英雄单位"""
        self.items = arena_functions.fetch_items()
        logger.info(f"  装备: {list(filter((None).__ne__, self.items))}")
        for index, _ in enumerate(self.items):
            if self.items[index] is not None:
                self.add_item_to_champs(index)

    def add_item_to_champs(self, item_index: int) -> None:
        """遍历棋盘中的英雄并检查英雄是否需要该装备"""
        for champ in self.board:
            if isinstance(champ, Champion) and champ.does_need_items() and self.items[item_index] is not None:
                        self.add_item_to_champ(item_index, champ)
                        if self.HP:
                            if (self.HP[0][1] <= settings.HEALTH and settings.RANDOM_ITEM) or \
                               (list(filter(None, self.items)).__len__() >= settings.MAX_ITEM and settings.RANDOM_MAX_ITEM):
                                self.any_item_to_champ(item_index, champ)
                            break

    def any_item_to_champ(self, item_index: int, champ: Champion) -> None:
        """决赛装备随便上了"""
        item = self.items[item_index]
        flag = False
        coords1 = None
        if champ.hero_type():
            if item in game_assets.REAR_ITEMS:
                coords1 = screen_coords.ITEM_POS[item_index][0].get_coords()
                flag = True
        else:
            if item in game_assets.FRONTLINE_ITEMS:
                coords1 = screen_coords.ITEM_POS[item_index][0].get_coords()
                flag = True
        if flag:
            mk_functions.left_click_drag(coords1, champ.coords)
            logger.info(f"  [随机] 装备 {item} 给 {champ.name}")
            champ.completed_items.append(item)
            index = self.items.index(item)
            while index < len(self.items) - 1:
                self.items[index] = self.items[index + 1]
                index += 1
            self.items[index] = None

    def handle_equip_item(self, item_index: int, champ, is_sacred: bool = False):
        """处理装备穿戴的通用方法"""
        item = self.items[item_index]
        similar_item = game_assets.SACRED_MATCHED_GROUP.get(item) if is_sacred else item
        if similar_item in champ.build:
            mk_functions.left_click_drag(screen_coords.ITEM_POS[item_index][0].get_coords(), champ.coords)
            item_type = "光明成装" if is_sacred else "成装"
            logger.info(f"  {item_type} {item} 给 {champ.name}")
            champ.completed_items.append(similar_item)
            champ.build.remove(similar_item)
            index = self.items.index(item)
            while index < len(self.items) - 1:
                self.items[index] = self.items[index + 1]
                index += 1
            self.items[index] = None
            sleep(0.01)
            return True
        return False

    def add_item_to_champ(self, item_index: int, champ: Champion) -> None:
        """获取物品的index和champ并装备该装备"""
        if not self.handle_equip_item(item_index, champ):
            self.handle_equip_item(item_index, champ, is_sacred=True)

        item = self.items[item_index]

        # 移除纹章逻辑
        if champ.does_need_trait():
            if champ.check_trait(item):
                mk_functions.left_click_drag(screen_coords.ITEM_POS[item_index][0].get_coords(), champ.coords)
                logger.info(f"  {item} 给 {champ.name}")
                champ.completed_items.append(item)
                index = self.items.index(item)
                while index < len(self.items) - 1:
                    self.items[index] = self.items[index + 1]
                    index += 1
                self.items[index] = None
                sleep(0.01)
                return

        # 给果实逻辑
        if champ.check_center():
            if not champ.check_eaten_fruit():
                if item == "强化果实":
                    logger.info(f"强化果实给 {champ.name}")
                    mk_functions.left_click_drag(screen_coords.ITEM_POS[item_index][0].get_coords(), champ.coords)
                    self.pick_fruits(champ)
                    index = self.items.index(item)
                    while index < len(self.items) - 1:
                        self.items[index] = self.items[index + 1]
                        index += 1
                    self.items[index] = None
                    return
            elif not champ.check_expect_fruit():
                if item == "强化果实移除器":
                    logger.info(f"移除 {champ.name} 的水果")
                    mk_functions.left_click_drag(screen_coords.ITEM_POS[item_index][0].get_coords(), champ.coords)
                    champ.eatenFruit = False
                    index = self.items.index(item)
                    mk_functions.move_mouse(screen_coords.ITEM_POS[index][0].get_coords())
                    item = ocr.get_text(
                        screenxy=screen_coords.ITEM_POS[index][1].get_coords(),
                        scale=1
                    )
                    valid = arena_functions._match_item_name(item)
                    if valid is not None and valid != "强化果实移除器":
                        while index < len(self.items) - 1:
                            self.items[index] = self.items[index + 1]
                            index += 1
                        self.items[index] = None
                    return

        elif self.check_all_center_expect_fruit() and not champ.check_eaten_fruit():
            logger.info(f"所有c位都获得了水果而且是预期的,剩下的水果给 {champ.name}")
            mk_functions.left_click_drag(screen_coords.ITEM_POS[item_index][0].get_coords(), champ.coords)
            self.pick_fruits(champ)
            index = self.items.index(item)
            while index < len(self.items) - 1:
                self.items[index] = self.items[index + 1]
                index += 1
            self.items[index] = None
            return

        if item in game_assets.FULL_ITEMS:
            if item in champ.build:
                mk_functions.left_click_drag(screen_coords.ITEM_POS[item_index][0].get_coords(), champ.coords)
                logger.info(f"  装备 {item} 给 {champ.name}")
                champ.completed_items.append(item)
                champ.build.remove(item)
                index = self.items.index(item)
                while index < len(self.items) - 1:
                    self.items[index] = self.items[index + 1]
                    index += 1
                self.items[index] = None

        elif len(champ.current_building) == 0:
            item_to_move: str | None = None
            for build_item in champ.build:
                build_item_components: list = list(game_assets.FULL_ITEMS[build_item])
                if item in build_item_components:
                    item_to_move = item
                    build_item_components.remove(item_to_move)
                    champ.current_building.append(
                        (build_item, build_item_components[0])
                    )
                    champ.build.remove(build_item)
            if item_to_move is not None:
                mk_functions.left_click_drag(screen_coords.ITEM_POS[item_index][0].get_coords(), champ.coords)
                logger.info(f"  装备 {item} 给 {champ.name}")
                index = self.items.index(item)
                while index < len(self.items) - 1:
                    self.items[index] = self.items[index + 1]
                    index += 1
                self.items[index] = None
        else:
            for buildItem in champ.current_building:
                if item == buildItem[1]:
                    mk_functions.left_click_drag(screen_coords.ITEM_POS[item_index][0].get_coords(), champ.coords)
                    champ.completed_items.append(buildItem[0])
                    champ.current_building.clear()
                    index = self.items.index(item)
                    while index < len(self.items) - 1:
                        self.items[index] = self.items[index + 1]
                        index += 1
                    self.items[index] = None
                    logger.info(f"  装备 {item} 给 {champ.name}")
                    logger.info(f"  合成 {buildItem[0]}")
                    sleep(0.05)
                    return

    def fix_unknown(self) -> None:
        """解决未知英雄"""
        sleep(0.5)
        pos = self._unknown_slot_rev(0) if self.board_unknown else 0
        mk_functions.press_e(
            screen_coords.BOARD_LOC[pos].get_coords()
        )
        self.board_unknown.pop(0)
        self.board_size -= 1

    def remove_champion(self, champion: Champion) -> None:
        """移除棋盘和备战区上的指定英雄"""
        for index, slot in enumerate(self.bench):
            if isinstance(slot, Champion) and slot.name == champion.name:
                mk_functions.press_e(slot.coords)
                self.bench[index] = None
        self.champs_to_buy.pop(champion.name)
        mk_functions.press_e(champion.coords)
        self.board_names.remove(champion.name)
        self.board_size -= champion.size
        self.board.remove(champion)

    def final_comp_check(self) -> None:
        """检查棋盘并替换没有进入决赛的英雄"""
        if self.locked_comp_heroes:
            # === 智能模式锁定后：清理非阵容棋子，上阵容棋子 ===
            # 1. 卖掉棋盘上不在锁定阵容中的棋子
            for champ in list(self.board):
                if isinstance(champ, Champion) and champ.name not in self.locked_comp_heroes:
                    logger.info(f"  清理非阵容棋子[{champ.name}]")
                    mk_functions.press_e(champ.coords)
                    self.board.remove(champ)
                    self.board_names.remove(champ.name)
                    self.board_size -= champ.size
            # 1.5 清理 board_unknown 中不在锁定阵容的棋子（如1-1选秀的）
            for i in reversed(range(len(self.board_unknown))):
                name = self.board_unknown[i]
                if isinstance(name, str) and name not in self.locked_comp_heroes and name not in ("?", ""):
                    logger.info(f"  清理非阵容棋子[{name}]（board_unknown）")
                    pos = self._unknown_slot_rev(i)
                    mk_functions.press_e(
                        screen_coords.BOARD_LOC[pos].get_coords()
                    )
                    self.board_unknown.pop(i)
                    self.board_size -= 1

            # 2. 把备战席中阵容需要的棋子上场
            for slot in list(self.bench):
                if isinstance(slot, Champion) and slot.name in self.locked_comp_heroes:
                    if slot.name not in self.board_names:
                        self.move_known(slot)
            return

        # === 固定阵容模式：原逻辑 ===
        for slot in self.bench:
            if (
                    isinstance(slot, Champion)
                    and slot.final_comp
                    and slot.name not in self.board_names
            ):
                for champion in self.board:
                    if not champion.final_comp and champion.size == slot.size:
                        logger.info(f"  更换 {champion.name} 为 {slot.name}")
                        self.remove_champion(champion)
                        self.move_known(slot)
                        break

    def tacticians_crown_check(self) -> None:
        """检测是否从选秀界面获取一个金铲铲冠冕装备"""
        mk_functions.move_mouse(screen_coords.ITEM_POS[0][0].get_coords())
        sleep(0.1)
        item: str = ocr.get_text(
            screenxy=screen_coords.ITEM_POS[0][1].get_coords(),
            scale=1
        )
        item: str = arena_functions._match_item_name(item)
        try:
            if ("金铲铲冠冕" in item) or ("金锅锅冠冕" in item) or ("金锅铲冠冕" in item):
                self.board_size -= 1
            else:
                logger.info(f"{item} 不是冠冕")
        except TypeError:
            logger.warning("  [!]装备栏没有装备")

    def _find_locked_squad(self) -> dict:
        """从 scorer 中查找锁定阵容的完整数据"""
        if not self.scorer or not self.current_comp:
            return {}
        for s in self.scorer._squads:
            if s.get("_name") == self.current_comp:
                return s
        return {}

    def lock_current_comp(self) -> None:
        """2-4/3-4 锁定当前推荐阵容，停止重新评分"""
        self.final_comp = True
        # 重新评分一次，取第 1 名锁定（只锁定这一套）
        if self.scorer:
            bench = {}
            for slot in self.bench:
                if isinstance(slot, Champion):
                    name = slot.name
                    bench[name] = bench.get(name, {"star": 1, "count": 0})
                    bench[name]["count"] += 1
            components = [i for i in self.items if i is not None]
            gold = arena_functions.fetch_gold()
            level = arena_functions.fetch_level()
            shop = arena_functions.fetch_shop()
            shop_names = [s[1] for s in shop if s[1]]
            active_traits = {}
            for c in self.board:
                if isinstance(c, Champion):
                    for i in range(1, 4):
                        t = game_assets.CHAMPIONS.get(c.name, {}).get(f"Trait{i}", "")
                        if t:
                            active_traits[t] = active_traits.get(t, 0) + 1
            rankings = self.scorer.score_all(
                bench_champions=bench, components=components,
                active_traits=active_traits, shop_champions=shop_names,
                gold=gold, level=level,
            )
            if rankings:
                self.current_comp = rankings[0]["name"]
                self.locked_comp_squad = self._find_locked_squad()
                self.locked_comp_heroes = {}
                for h in rankings[0].get("heroes", []):
                    if h in game_assets.CHAMPIONS:
                        # 从阵容文件读取目标星级: star=2→3个, star=3→9个
                        star = 2
                        if self.locked_comp_squad:
                            star = self.locked_comp_squad.get("HERO", {}).get(h, {}).get("star", 2)
                        need = 9 if star >= 3 else 3
                        self.locked_comp_heroes[h] = need
                hero_info = ", ".join(f"{n}" for n in self.locked_comp_heroes)
                logger.info(f"  阵容已锁定: {self.current_comp} ({len(self.locked_comp_heroes)} 个英雄)")
                # 立即覆盖 champs_to_buy
                self.champs_to_buy = dict(self.locked_comp_heroes)
                return
        # 保底：用当前的
        self.locked_comp_heroes = dict(self.champs_to_buy)
        self.locked_comp_squad = self._find_locked_squad()

    def spend_gold(self, speedy=False) -> None:
        """每回合都消费金币"""

        # ==============================================================
        # 智能模式：每回合评分，用推荐阵容覆盖 champs_to_buy
        # ==============================================================
        if self.scorer:
            if self.final_comp and self.locked_comp_heroes:
                # 已锁定 → 使用锁定时的静态英雄列表，不再重新评分
                self.champs_to_buy = dict(self.locked_comp_heroes)
                logger.info(f"  锁定阵容: {self.current_comp}")
                # 跳转到买棋逻辑（不执行下面评分代码）
                self._compute_min_gold()
                self._buy_loop()
                return

            # 未锁定 → 正常评分
            bench = {}
            for slot in self.bench:
                if isinstance(slot, Champion):
                    name = slot.name
                    if name not in bench:
                        bench[name] = {"star": 1, "count": 0}
                    bench[name]["count"] += 1
                    bench[name]["star"] = max(bench[name]["star"], getattr(slot, 'star', 1))

            components = [item for item in self.items if item is not None]
            gold = arena_functions.fetch_gold()
            level = arena_functions.fetch_level()
            shop = arena_functions.fetch_shop()
            shop_names = [s[1] for s in shop if s[1]]

            # 从棋盘统计当前羁绊
            active_traits = {}
            for champion in self.board:
                if isinstance(champion, Champion):
                    hero_data = game_assets.CHAMPIONS.get(champion.name, {})
                    for i in range(1, 4):
                        trait = hero_data.get(f"Trait{i}", "")
                        if trait:
                            active_traits[trait] = active_traits.get(trait, 0) + 1

            rankings = self.scorer.score_all(
                bench_champions=bench,
                components=components,
                active_traits=active_traits,
                shop_champions=shop_names,
                gold=gold,
                level=level,
            )

            if rankings:
                top = rankings[0]
                self.current_comp = top['name']
                logger.info(f"推荐: {self.current_comp} ({top['score']}分)")
                # 把推荐阵容的棋子注入 champs_to_buy
                self.champs_to_buy.clear()
                if self.final_comp:
                    # 2-4 后锁定阵容 → 只买第 1 名的棋子
                    candidates = [rankings[0]]
                else:
                    # 前期灵活 → 买前 3 名阵容的棋子，方便转型
                    candidates = rankings[:3]
                for r in candidates:
                    for hero_name in r.get('heroes', []):
                        if hero_name in game_assets.CHAMPIONS:
                            self.champs_to_buy[hero_name] = 3
        # ==============================================================

        self._compute_min_gold(speedy)
        self._buy_loop()

    def _compute_min_gold(self, speedy=False) -> None:
        """计算本回合的预留金币阈值"""
        if self.scorer:
            level = arena_functions.fetch_level()
            if self.spam_roll or (self.HP and self.HP[0][1] <= settings.HEALTH):
                self._min_gold = 0  # 血量低 → 全花光
            elif level <= 5:
                self._min_gold = 34  # 3~5 级存 34 吃利息
            else:
                self._min_gold = 54  # 6+ 级存 54 吃利息
        else:
            self._min_gold = 100 if speedy else (settings.MIN_GOLD if self.spam_roll else settings.MAX_GOLD)

    def _buy_loop(self) -> None:
        """买棋主循环：XP/刷新（受 min_gold 控制）+ 买棋（不受限，买得起就买）"""
        show_store = False
        first_run = True

        while first_run or arena_functions.fetch_gold() >= self._min_gold:
            refresh = True
            if not first_run:
                cur_level = arena_functions.fetch_level()
                if cur_level != 10:
                    if self.scorer:
                        if cur_level <= 5:
                            buy_xp = False
                        elif cur_level >= 9:
                            buy_xp = False
                        else:
                            buy_xp = True
                    else:
                        buy_xp = cur_level not in settings.UPGRADE_LEVEL

                    if buy_xp:
                        mk_functions.buy_xp()
                        logger.info("  小于期望等级 -> 购买经验")
                        if settings.BUY_EXP_REFRESH_STORE:
                            mk_functions.reroll()
                            logger.info("  小于期望等级 -> 刷新商店")
                            refresh = False
                            show_store = True
                    else:
                        if self.spam_roll or cur_level >= 9 or (self.scorer and cur_level <= 5):
                            mk_functions.reroll()
                            logger.info("  刷新商店")
                            show_store = True
                    if not self.scorer and self.check_center_perfect():
                        mk_functions.buy_xp()
                        logger.info("  C位成型 -> 购买经验")
                        mk_functions.reroll()
                        logger.info("  C位成型 -> 刷新商店")
                        refresh = False
                        show_store = True

            shop = arena_functions.fetch_shop()
            if show_store or first_run:
                names = " | ".join(s[1] or "?" for s in shop)
                logger.info(f"  商店：[{names}]")

            for champion in shop:
                if self.champs_to_buy.get(champion[1], -1) >= 0:
                    cost = game_assets.CHAMPIONS.get(champion[1], {}).get("Gold", 1)
                    if arena_functions.fetch_gold() >= cost:
                        self.buy_champion(champion, 1)

            first_run = False
            if arena_functions.fetch_round_remaining_time() <= 4:
                return

    def _clean_bench_excess(self) -> None:
        """备战席满时：卖掉已经2星棋子的多余1星，腾位置"""
        # 统计每个棋子在备战席的数量
        champ_count = {}
        for slot in self.bench:
            if isinstance(slot, Champion):
                name = slot.name
                champ_count[name] = champ_count.get(name, 0) + 1

        for i, slot in enumerate(self.bench):
            if isinstance(slot, Champion):
                name = slot.name
                count = champ_count.get(name, 0)
                # 如果已经有 3 个以上（已合2星还多），卖掉多余的1星
                if count >= 3 and count > len([s for s in self.bench
                                               if isinstance(s, Champion) and s.name == name and s not in self.board_names]):
                    mk_functions.press_e(slot.coords)
                    logger.info(f"  清理备战席多余[{name}]（已有2星）")
                    self.bench[i] = None
                    champ_count[name] -= 1

    def buy_champion(self, champion, quantity) -> None:
        """从商店购买英雄"""
        none_slot: int = arena_functions.find_empty_bench_slot()
        if none_slot != -1:
            mk_functions.left_click(screen_coords.BUY_LOC[champion[0]].get_coords())
            logger.info(f"    购买 {champion[1]}")
            self.bought_champion(champion[1], none_slot)
            if champion[1] in self.champs_to_buy:
                self.champs_to_buy[champion[1]] -= quantity
        else:
            # 备战席满 → 先清理已2星的多余1星
            self._clean_bench_excess()
            none_slot = arena_functions.find_empty_bench_slot()
            if none_slot != -1:
                mk_functions.left_click(screen_coords.BUY_LOC[champion[0]].get_coords())
                logger.info(f"    购买 {champion[1]}")
                self.bought_champion(champion[1], none_slot)
                if champion[1] in self.champs_to_buy:
                    self.champs_to_buy[champion[1]] -= quantity
                return
            logger.info(f"  备战区已满 无法购买: {champion[1]}")
            mk_functions.left_click(screen_coords.BUY_LOC[champion[0]].get_coords())
            game_functions.default_pos()
            sleep(0.5)
            self.fix_bench_state()
            none_slot = arena_functions.find_empty_bench_slot()
            sleep(0.5)
            if none_slot != -1:
                logger.info(f"    购买 {champion[1]}")
                if champion[1] in self.champs_to_buy:
                    self.champs_to_buy[champion[1]] -= quantity

    def buy_xp_round(self) -> None:
        """当金币等于或超过预定值时购买经验 4"""
        if arena_functions.fetch_gold() >= 4:
            mk_functions.buy_xp()

    def pick_augment(self) -> None:
        """从用户定义的强化优先级列表中选择一个强化"""
        errorCount = 0
        while True:
            sleep(1)
            augments: list = []
            for coords in screen_coords.AUGMENT_POS:
                augment: str = ocr.get_text(
                    screenxy=coords.get_coords(), scale=3
                )
                augments.append(augment)
            logger.info(f"强化符文: {augments}")
            if len(list(filter(None, augments))) == 3 and '' not in augments or errorCount >= 10:
                break
            errorCount += 1

        for potential in comps.AUGMENTS:
            for augment in augments:
                if potential in augment:
                    logger.info(f"选择强化符文 {augment}")
                    mk_functions.left_click(
                        screen_coords.AUGMENT_LOC[augments.index(augment)].get_coords()
                    )
                    return

        if self.augment_roll:
            logger.info("刷新强化符文")
            for i in range(0, 3):
                mk_functions.left_click(screen_coords.AUGMENT_ROLL[i].get_coords())
            self.augment_roll = False
            self.pick_augment()
            return

        logger.warning("未找到预设强化符文,默认选择第一个")

        for augment in augments:
            found = False
            for potential in comps.AVOID_AUGMENTS:
                if potential in augment:
                    found = True
                    break
            if not found:
                mk_functions.left_click(
                    screen_coords.AUGMENT_LOC[augments.index(augment)].get_coords()
                )
                return
        mk_functions.left_click(screen_coords.AUGMENT_LOC[0].get_coords())

    def pick_fruits(self, champ: Champion):
        """选择当前传入英雄需要的强化果实"""
        errorCount = 0
        while True:
            sleep(1)
            fruits: list = []
            for coords in screen_coords.FRUITS_POS:
                fruit: str = ocr.get_text(
                    screenxy=coords.get_coords(), scale=3
                )
                fruits.append(fruit)
            logger.info(f"强化果实: {fruits}")
            if len(list(filter(None, fruits))) == 3 and '' not in fruits:
                break
            errorCount += 1
            if errorCount > 3:
                break

        for potential in comps.FRUIT:
            for fruit in fruits:
                if potential in fruit:
                    logger.info(f"选择喜爱强化果实 {fruit}")
                    mk_functions.left_click(
                        screen_coords.FRUITS_LOC[fruits.index(fruit)].get_coords()
                    )
                    champ.eatenFruit = True
                    champ.expect_fruit = True
                    return

        for potential in comps.AVOID_FRUIT:
            for fruit in fruits:
                if potential in fruit:
                    logger.info(f"选择讨厌强化果实 {fruit}")
                    mk_functions.left_click(
                        screen_coords.FRUITS_LOC[fruits.index(fruit)].get_coords()
                    )
                    champ.eatenFruit = True
                    return
        mk_functions.left_click(screen_coords.FRUITS_LOC[0].get_coords())
        champ.eatenFruit = True

    def find_blue_buff(self, screenshot=(517, 365, 1415, 699), difference_lv=30) -> int:
        """查找棋盘上魔像的位置"""
        d_x = screenshot[0]
        d_y = screenshot[1]
        screenshot = ImageGrab.grab(bbox=screenshot)
        screenshot_pixels = screenshot.load()
        target_color = (0, 114, 255)
        for x in range(screenshot.size[0]):
            for y in range(screenshot.size[1]):
                pixel_color = screenshot_pixels[x, y]
                diff = abs(pixel_color[0] - target_color[0]) + abs(pixel_color[1] - target_color[1]) + abs(
                    pixel_color[2] - target_color[2])
                if diff < difference_lv:
                    coord = (x + d_x, y + d_y)
                    return self.find_target_index(coord)

    def find_target_index(self, xy):
        """传入x和y 返回棋盘位置下标"""
        for index, coordinate in enumerate(screen_coords.BOARD_LOC):
            distance = math.sqrt((coordinate.get_coords()[0] - xy[0]) ** 2 + (coordinate.get_coords()[1] - xy[1]) ** 2)
            if distance <= 30:
                return index
        return None

    def check_center_perfect(self) -> bool:
        """返回C位是否达到预期等级"""
        for heroName in comps.COMP:
            if comps.COMP[heroName]["center"] == True and self.champs_to_buy[heroName] == 0:
                return True
        return False

    def check_all_center_expect_fruit(self) -> bool:
        """获取所有C位是否吃了水果"""
        return False

    def get_label(self) -> None:
        """获取用于在窗口上显示英雄名称UI的标签"""
        labels: list = [
            (f"{slot.name}", slot.coords)
            for slot in self.bench
            if isinstance(slot, Champion)
        ]
        for slot in self.board:
            if isinstance(slot, Champion):
                labels.append((f"{slot.name}", slot.coords))

        labels.extend(
            (slot, screen_coords.BOARD_LOC[self._unknown_slot_rev(index)].get_coords())
            for index, slot in enumerate(self.board_unknown)
        )
        self.message_queue.put(("LABEL", labels))