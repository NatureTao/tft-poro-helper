"""
处理每回合游戏中发生的任务
"""
import time
from time import sleep, perf_counter
import random
import multiprocessing
import importlib
from win32con import BM_CLICK
import win32gui

import mk_functions
import screen_coords
import settings
import arena_functions
import game_assets
import game_functions
from arena import Arena
from vec4 import Vec4
from vec2 import Vec2
from utils.logger import logger
import ocr

class Game:
    """
    游戏主控制器

    职责：回合调度，不直接操作棋子
    - 检测游戏窗口
    - 等待加载完成
    - 循环检测回合变化 → 分发到对应回合处理方法
    """

    def __init__(self, message_queue: multiprocessing.Queue, squad_data=None, smart_mode=False) -> None:
        """
        初始化游戏实例

        Args:
            message_queue: 多进程消息队列（推送状态/日志到 overlay）
            squad_data: 阵容数据（固定阵容为单个 dict，智能模式为列表）
            smart_mode: 是否启用智能推荐模式
        """
        importlib.reload(game_assets)
        self.message_queue = message_queue
        self.arena = Arena(self.message_queue)
        self.round: list[str, int] = ["0-0", 0]
        self.time = None
        self.start_time = None
        self.forfeit_time: int = settings.FORFEIT_TIME + random.randint(50, 150)
        self.found_window = False

        # 阵容模式初始化
        self.smart_mode = smart_mode
        self.scorer = None
        self.fixed_squad = None

        if smart_mode and squad_data:
            from services.tft_scorer import TFTScorer
            self.scorer = TFTScorer()
            self.scorer._squads = squad_data  # 直接用预加载的阵容列表
            self.arena.scorer = self.scorer  # 传给 arena
            logger.info(f"智能推荐模式：{len(squad_data)} 套阵容就绪")
        elif squad_data and not smart_mode:
            self.fixed_squad = squad_data  # 固定阵容模式
            self.arena.fixed_squad = squad_data
            logger.info(f"固定阵容模式：{squad_data.get('_name', '未知阵容')}")
        else:
            logger.info("固定阵容模式（从 squads 目录加载）")

        logger.info("寻找游戏窗口")
        while not self.found_window:
            win32gui.EnumWindows(self.callback, None)
            sleep(1)
        self.loading_screen()

    # ==================================================================
    # 窗口检测
    # ==================================================================

    def callback(self, hwnd, extra) -> None:
        """
        窗口回调：检测游戏窗口并记录位置/大小
        由 win32gui.EnumWindows 调用
        """
        if settings.GAME_HWND_NAME not in win32gui.GetWindowText(hwnd):
            return

        rect = win32gui.GetWindowRect(hwnd)
        x_pos, y_pos = rect[0], rect[1]
        width = rect[2] - x_pos
        height = rect[3] - y_pos

        if width < 200 or height < 200:
            return

        logger.info(f"游戏窗口[{win32gui.GetWindowText(hwnd)}]已加载")
        logger.info(f"  起始位置: ({x_pos}, {y_pos})")
        logger.info(f"  窗口大小: ({width}, {height})")
        Vec4.setup_screen(x_pos, y_pos, width, height)
        Vec2.setup_screen(x_pos, y_pos, width, height)
        self.found_window = True

    # ==================================================================
    # 加载等待
    # ==================================================================

    def loading_screen(self) -> None:
        """
        等待游戏加载完成
        检测到任意有效回合（1-1 到 7-8）后退出，进入主循环
        支持断线重连（不会卡在 1-1 检测）
        """
        game_functions.default_pos()

        while True:
            current_round = game_functions.get_round()[0]

            if current_round in game_assets.ROUNDS:
                logger.info(f"游戏加载完成，当前回合: {current_round}")
                break

            if self.check_failed_to_connect_window():
                return

            sleep(1)

        self.start_time = perf_counter()
        self.game_loop()

    def check_failed_to_connect_window(self) -> bool:
        """
        检查"连接失败"弹窗
        如果出现 → 点击取消按钮退出游戏
        """
        hwnd = win32gui.FindWindow(None, "Failed to Connect")
        if hwnd:
            logger.warning("发现'连接失败'窗口，试图退出并重新连接")
            if reconnect_button := win32gui.FindWindowEx(hwnd, 0, "Button", None):
                if cancel_button := win32gui.FindWindowEx(hwnd, reconnect_button, "Button", None):
                    logger.info("退出游戏")
                    win32gui.SendMessage(cancel_button, BM_CLICK, 0, 0)
                    return True
        return False

    # ==================================================================
    # 主循环
    # ==================================================================

    def game_loop(self) -> None:
        """
        游戏主循环
        每 0.5 秒检测一次回合变化，分发到对应处理方法
        检测到死亡 → 退出游戏 → 等待下一局
        """
        ran_round: str = None          # 上一次处理的回合（避免重复执行）
        last_game_health: int = 100    # 上一次存活状态

        while True:
            # 检测存活状态（通过 API 获取 deaths 字段）
            game_health: int = arena_functions.fetch_alive()
            if game_health == 1 and last_game_health > 0:
                # 刚死亡 → 等待确认 → 退出
                count = 15
                while count > 0:
                    if not game_functions.check_alive():
                        self.message_queue.put("CLEAR")
                        game_functions.exit_game()
                        break
                    sleep(1)
                    count -= 1
                break

            last_game_health = game_health

            # 获取当前回合
            self.round = game_functions.get_round()

            # 自动投降
            if settings.FORFEIT and perf_counter() - self.start_time > self.forfeit_time:
                game_functions.forfeit()
                continue

            # 回合变化 → 分发
            if self.round[0] != ran_round:
                if self.round[0] in game_assets.PVP_ROUND:
                    game_functions.default_pos()
                    self.pvp_round()
                elif self.round[0] in game_assets.PVE_ROUND:
                    game_functions.default_pos()
                    self.pve_round()
                elif self.round[0] in game_assets.CAROUSEL_ROUND:
                    self.carousel_round()
                elif self.round[0] in game_assets.SECOND_ROUND:
                    self.second_round()
                    self.second_round()
                elif self.round[0] in game_assets.ENCOUNTER_ROUNDS:
                    logger.info(f"[遇到对局] {self.round[0]} 不执行操作")
                    self.message_queue.put("CLEAR")

                ran_round = self.round[0]

                # 每个新阶段的第一回合 → 动态更新回合类型
                if self.round[1] == 1 and self.round[0].split("-")[1] == "1":
                    logger.info("[当前回合]")
                    self.encounter_round_setup()

            sleep(0.5)

    def encounter_round_setup(self) -> None:
        """
        动态回合配置
        每个新阶段的第一回合（如 2-1, 3-1）会重新检测后续回合类型
        通过 OCR 读取回合信息图标，判断 carousel/pve/pvp/encounter
        """
        # 清空当前阶段的所有回合配置
        prefix = self.round[0].split("-")[0]
        for attr in ['CAROUSEL_ROUND', 'PVE_ROUND', 'PVP_ROUND', 'ANVIL_ROUNDS', 'ITEM_PLACEMENT_ROUNDS']:
            setattr(game_assets, attr, {
                r for r in getattr(game_assets, attr) if not r.startswith(prefix)
            })

        # 读取回合信息图标
        for index, round_msg in enumerate(game_functions.check_encounter_round()):
            logger.info(f"  回合 {prefix}-{index + 1}: {round_msg.upper()} 对局")
            if index == 0:
                continue

            if round_msg == "carousel":
                game_assets.CAROUSEL_ROUND.add(f"{prefix}-{index + 1}")
                game_assets.ANVIL_ROUNDS.add(f"{prefix}-{index + 2}")
                game_assets.ITEM_PLACEMENT_ROUNDS.add(f"{prefix}-{index + 2}")
            elif round_msg == "pve":
                game_assets.PVE_ROUND.add(f"{prefix}-{index + 1}")
            elif round_msg == "pvp":
                game_assets.PVP_ROUND.add(f"{prefix}-{index + 1}")
            elif round_msg == "encounter":
                game_assets.ENCOUNTER_ROUNDS.add(f"{prefix}-{index + 1}")
                if index + 1 == 2 and 3 <= int(prefix) <= 4:
                    game_assets.AUGMENT_ROUNDS.add(f"{prefix}-{index + 2}")

    # ==================================================================
    # 回合处理方法
    # ==================================================================

    def second_round(self) -> None:
        """
        1-2 初始对局
        把 1-1 选秀拿到的棋子放到棋盘上
        """
        logger.info(f"[初始对局] {self.round[0]}")
        self.message_queue.put("CLEAR")

        # 等待备战区有棋子
        while True:
            result = arena_functions.check_bench_occupied()
            if any(result):
                break
        self.arena.bench[result.index(True)] = "?"
        for _ in range(arena_functions.fetch_level()):
            self.arena.move_unknown()

        sleep(2.5)
        self.arena.portal_augment()  # 检测区域奇遇
        self.end_round_tasks()

    def carousel_round(self) -> None:
        """选秀回合：根据赛季调用不同逻辑"""
        logger.info(f"[选秀] {self.round[0]}")
        self.message_queue.put("CLEAR")

        if self.round[0] == "1-1":
            logger.info("  本局星神介绍，等待进入1-2...")
            while self.round[0] == game_functions.get_round()[0]:
                sleep(1)
            return

        elif self.round[0] == "3-4":
            # 确定使用阵容
            self.arena.final_comp = True

        # 按赛季分发选秀逻辑（2-4 / 3-4 / 4-4 都会执行）
        self._handle_post_carousel()

        # 等待选秀结束
        logger.info("  等待选秀完成...")
        while self.round[0] == game_functions.get_round()[0]:
            sleep(1)



    def _handle_post_carousel(self) -> None:
        """选秀后的额外操作（不同赛季不同实现）"""
        season = getattr(settings, 'TFT_SEASON', 's17')

        if season == 's17':
            self._pick_blessing_and_penguin()
        # elif season == 's18':
        #     self._pick_xxx()
        else:
            logger.info(f"  当前赛季 {season} 无选秀后额外操作")

    def _pick_blessing_and_penguin(self) -> None:
        """S17：星界赐福 + 企鹅棋子选择"""
        import random

        sleep(5)
        # 星界赐福：随机
        choice = random.randint(1, 2)
        mk_functions.left_click(screen_coords.BLESSING_LOC[choice - 1].get_coords())
        logger.info(f"  星界赐福：随机选择第 {choice} 个")
        sleep(4)

        # 企鹅棋子：OCR 识别
        logger.info("  OCR 识别企鹅棋子...")
        penguins = []
        for coords in screen_coords.PENGUIN_POS:
            text = ocr.get_text(screenxy=coords.get_coords(), scale=3)
            name = self._extract_penguin_name(text)
            name = arena_functions._match_champion_name(name)
            penguins.append(name)
        logger.info(f"  企鹅棋子: {penguins}")

        target_heroes = set(self.arena.champs_to_buy.keys()) | set(self.arena.board_names)
        for i, name in enumerate(penguins):
            if name in target_heroes:
                mk_functions.left_click(screen_coords.PENGUIN_LOC[i].get_coords())
                logger.info(f"  选择企鹅棋子（在阵容中）: {name}")
                return

        i = random.randint(0, 2)
        mk_functions.left_click(screen_coords.PENGUIN_LOC[i].get_coords())
        logger.info(f"  随机选择企鹅棋子: {penguins[i]}")

    def _extract_penguin_name(self, text: str) -> str:
        """从 'X费:  XXX' 中提取英雄名"""
        if ":" in text:
            text = text.split(":")[-1].strip()
        return arena_functions._match_champion_name(text)


    def pve_round(self) -> None:
        """
        PVE 回合（打野怪）
        包含：强化符文选择、魔像处理、铁砧消耗
        """
        logger.info(f"[PvE 对局] {self.round[0]}")
        self.message_queue.put(("LOG", f"回合 {self.round[0]} 开始（PVE）"))
        self.message_queue.put("CLEAR")
        sleep(0.5)

        # 强化符文选择（2-1, 3-2, 4-2）
        if self.round[0] in game_assets.AUGMENT_ROUNDS:
            sleep(1)
            self.arena.augment_roll = True
            self.arena.pick_augment()
            sleep(2.5)

        # 魔像训练师处理（1-4）
        if self.round[0] == "1-4":
            if self.arena.active_portal in game_assets.DUMMY_PORTALS:
                logger.info("处理魔像逻辑")
                index = self.arena.find_blue_buff()
                if index is not None:
                    mk_functions.left_click(screen_coords.BOARD_LOC[index].get_coords())
                    sleep(0.5)
                    mk_functions.left_click(
                        screen_coords.BOARD_LOC[self.arena.unknown_slots[len(self.arena.board_unknown)]].get_coords()
                    )
                    self.arena.board_unknown.append("魔像")

        # 额外强化符文（2-6）
        if self.round[0] == "2-6":
            if self.arena.active_portal in game_assets.ADDITIONAL_AUGMENT:
                logger.info("选择额外强化符文")
                self.arena.pick_augment()

        # 核心操作流程
        self.arena.fix_bench_state()      # 修复备战区状态（OCR 识别棋子）
        self.arena.spend_gold()            # 消费金币（买棋子/刷新/升级）
        self.arena.move_champions()        # 把棋子从备战区移到棋盘
        self.arena.replace_unknown()       # 替换未识别的英雄
        if self.arena.final_comp:
            self.arena.final_comp_check()  # 决赛阵容检查
        self.arena.bench_cleanup()         # 出售多余棋子

        # 1-3 铁砧处理
        if self.round[0] == "1-3":
            sleep(1.5)
            if self.arena.active_portal in game_assets.ANVIL_PORTALS:
                self.arena.anvil_free[1:] = [True] * 8
                self.arena.clear_anvil()
                self.arena.anvil_free[:2] = [True, False]
                self.arena.clear_anvil()
            self.arena.tacticians_crown_check()

        self.end_round_tasks()

    def pvp_round(self) -> None:
        """
        PVP 回合（玩家对战）
        包含：强化符文选择、购买经验、拾取战利品、装备合成
        """
        logger.info(f"[PvP 对局] {self.round[0]}")
        self.message_queue.put(("LOG", f"回合 {self.round[0]} 开始（PVP）"))
        self.message_queue.put("CLEAR")
        sleep(0.5)

        # 强化符文选择
        if self.round[0] in game_assets.AUGMENT_ROUNDS:
            sleep(1)
            self.arena.augment_roll = True
            self.arena.pick_augment()
            sleep(2.5)

        # 2-1 / 2-5 购买经验
        if self.round[0] in ("2-1", "2-5"):
            self.arena.buy_xp_round()

        # 拾取战利品法球（YOLO 检测）
        if self.round[0] in game_assets.PICKUP_ROUNDS:
            logger.info("  拾取战利品")
            self.message_queue.put(("LOG", "YOLO检测中..."))
            game_functions.pickup_items()
            self.message_queue.put(("LOG", "战利品拾取完成"))

        # 核心操作流程
        self.arena.fix_bench_state()
        self.arena.bench_cleanup()

        if self.round[0] in game_assets.ANVIL_ROUNDS:
            self.arena.clear_anvil()

        self.arena.spend_gold(speedy=self.round[0] in game_assets.PICKUP_ROUNDS)
        self.arena.move_champions()
        self.arena.replace_unknown()

        if self.arena.final_comp:
            self.arena.final_comp_check()

        self.arena.bench_cleanup()

        # 装备合成
        if self.round[0] in game_assets.ITEM_PLACEMENT_ROUNDS:
            sleep(1)
            self.arena.place_items()

        self.end_round_tasks()

    # ==================================================================
    # 回合末尾
    # ==================================================================

    def end_round_tasks(self) -> None:
        """
        每回合末尾执行
        - 获取血量/排名
        - 推送状态到 overlay
        - 血量低 → 开启 spam_roll（疯狂刷新）
        - 推送英雄标签到 overlay
        """
        self.arena.HP = arena_functions.fetch_health_ranking()
        if self.arena.HP:
            logger.info(f" 生命值：{self.arena.HP[0][1]}")
            logger.info(f" 排名：{self.arena.HP[0][0]}")

            self.message_queue.put(("STATUS", {
                "running": True,
                "paused": False,
                "stop_after_game": False,
                "round": self.round[0],
            }))

            # 血量低于阈值 → 疯狂刷新找关键棋子
            if self.arena.HP[0][1] <= settings.HEALTH:
                self.arena.spam_roll = True
            else:
                self.arena.spam_roll = False

        self.arena.get_label()         # 推送英雄名标签
        game_functions.default_pos()   # 鼠标归位


if __name__ == "__main__":
    import screen_coords
    import ocr
    import arena_functions
    import mk_functions
    import random
    from time import sleep

    print("等待5秒后测试星界赐福 + 企鹅棋子...")
    sleep(5)

    # 星界赐福：随机点击
    choice = random.randint(1, 2)
    print(f"点击星界赐福第 {choice} 个: {screen_coords.BLESSING_LOC[choice - 1].get_coords()}")
    mk_functions.left_click(screen_coords.BLESSING_LOC[choice - 1].get_coords())
    sleep(1)

    # 企鹅棋子 OCR
    print("\n企鹅棋子 OCR 识别结果:")
    for i, coords in enumerate(screen_coords.PENGUIN_POS):
        text = ocr.get_text(screenxy=coords.get_coords(), scale=3)
        # 提取 "X费: XXX" → "XXX"
        if ":" in text:
            text = text.split(":")[-1].strip()
        name = arena_functions._match_champion_name(text)
        print(f"  位置{i+1}: 原始='{text}' → 匹配='{name}'")