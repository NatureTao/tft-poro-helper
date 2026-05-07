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


class Game:
    """Game类 处理游戏逻辑 每回合"""

    def __init__(self, message_queue: multiprocessing.Queue) -> None:
        importlib.reload(game_assets)
        self.message_queue = message_queue
        self.arena = Arena(self.message_queue)
        self.round: list[str, int] = ["0-0", 0]
        self.time = None
        self.forfeit_time: int = settings.FORFEIT_TIME + random.randint(50, 150)
        self.found_window = False

        logger.info("寻找游戏窗口")
        while not self.found_window:
            win32gui.EnumWindows(self.callback, None)
            sleep(6)
        self.loading_screen()

    def callback(self, hwnd, extra) -> None:
        """用于查找游戏窗口并获取其大小的函数"""
        if settings.GAME_HWND_NAME not in win32gui.GetWindowText(hwnd):
            return

        rect = win32gui.GetWindowRect(hwnd)

        x_pos = rect[0]
        y_pos = rect[1]
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

    def loading_screen(self) -> None:
        """循环，当游戏在加载屏幕时运行"""
        game_functions.default_pos()
        while game_functions.get_round()[0] != "1-1":
            if self.check_failed_to_connect_window():
                return
            sleep(1)
        self.start_time: float = perf_counter()
        self.game_loop()

    def check_failed_to_connect_window(self) -> bool:
        """检查"连接失败"窗口并尝试重新连接"""
        hwnd = win32gui.FindWindow(None, "Failed to Connect")
        if hwnd:
            logger.warning("发现'连接失败'窗口，试图退出并重新连接")
            if reconnect_button := win32gui.FindWindowEx(hwnd, 0, "Button", None):
                if cancel_button := win32gui.FindWindowEx(
                        hwnd, reconnect_button, "Button", None
                ):
                    logger.info("退出游戏")
                    win32gui.SendMessage(cancel_button, BM_CLICK, 0, 0)
                    return True
                logger.warning("未找到取消按钮")
            else:
                logger.warning("未找到重新连接按钮")
        return False

    def _push_status(self):
        """推送当前状态到 overlay"""
        hp_val = "--"
        rank_val = "--"
        if self.arena.HP and len(self.arena.HP) > 0 and self.arena.HP[0]:
            rank_val = str(self.arena.HP[0][0])
            hp_val = str(self.arena.HP[0][1])

        self.message_queue.put(("STATUS", {
            "running": True,
            "paused": False,
            "stop_after_game": False,
            "round": self.round[0],
        }))

    def game_loop(self) -> None:
        """在游戏处于活动状态时运行的Loop"""
        ran_round: str = None
        last_game_health: int = 100

        while True:
            game_health: int = arena_functions.fetch_alive()
            if game_health == 1 and last_game_health > 0:
                count: int = 15
                while count > 0:
                    if not game_functions.check_alive():
                        self.message_queue.put("CLEAR")
                        game_functions.exit_game()
                        break
                    sleep(1)
                    count -= 1
                break
            if game_health == 1 and last_game_health > 0:
                time.sleep(5)
                self.message_queue.put("CLEAR")
                game_functions.exit_game()
                break

            last_game_health = game_health

            self.round = game_functions.get_round()

            if (
                    settings.FORFEIT
                    and perf_counter() - self.start_time > self.forfeit_time
            ):
                game_functions.forfeit()
                continue

            if self.round[0] != ran_round:
                if self.round[0] in game_assets.PVP_ROUND:
                    game_functions.default_pos()
                    self.pvp_round()
                    ran_round: str = self.round[0]
                elif self.round[0] in game_assets.PVE_ROUND:
                    game_functions.default_pos()
                    self.pve_round()
                    ran_round: str = self.round[0]
                elif self.round[0] in game_assets.CAROUSEL_ROUND:
                    self.carousel_round()
                    ran_round: str = self.round[0]
                elif self.round[0] in game_assets.SECOND_ROUND:
                    self.second_round()
                    ran_round: str = self.round[0]
                elif self.round[0] in game_assets.ENCOUNTER_ROUNDS:
                    logger.info(f"[遇到对局] {self.round[0]} 不执行操作")
                    self.message_queue.put("CLEAR")
                    ran_round: str = self.round[0]
                if self.round[1] == 1 and self.round[0].split("-")[1] == "1":
                    logger.info("[当前回合]")
                    self.encounter_round_setup()
            sleep(0.5)

    def encounter_round_setup(self) -> None:
        """从game_assets中删除轮次，并通过检查轮次消息将其添加回来"""
        game_assets.CAROUSEL_ROUND = {
            carousel_round
            for carousel_round in game_assets.CAROUSEL_ROUND
            if not carousel_round.startswith(self.round[0].split("-")[0])
        }
        game_assets.PVE_ROUND = {
            pve_round
            for pve_round in game_assets.PVE_ROUND
            if not pve_round.startswith(self.round[0].split("-")[0])
        }
        game_assets.PVP_ROUND = {
            pvp_round
            for pvp_round in game_assets.PVP_ROUND
            if not pvp_round.startswith(self.round[0].split("-")[0])
        }
        game_assets.ANVIL_ROUNDS = {
            anvil_round
            for anvil_round in game_assets.ANVIL_ROUNDS
            if not anvil_round.startswith(self.round[0].split("-")[0])
        }
        game_assets.ITEM_PLACEMENT_ROUNDS = {
            item_placement_round
            for item_placement_round in game_assets.ITEM_PLACEMENT_ROUNDS
            if not item_placement_round.startswith(self.round[0].split("-")[0])
        }
        for index, round_msg in enumerate(game_functions.check_encounter_round()):
            logger.info(f"  回合 {self.round[0].split('-')[0]}-{str(index + 1)}: {round_msg.upper()} 对局")
            if index == 0:
                continue
            if round_msg == "carousel":
                game_assets.CAROUSEL_ROUND.add(
                    self.round[0].split("-")[0] + "-" + str(index + 1)
                )
                game_assets.ANVIL_ROUNDS.add(
                    self.round[0].split("-")[0] + "-" + str(index + 2)
                )
                game_assets.ITEM_PLACEMENT_ROUNDS.add(
                    self.round[0].split("-")[0] + "-" + str(index + 2)
                )
            elif round_msg == "pve":
                game_assets.PVE_ROUND.add(
                    self.round[0].split("-")[0] + "-" + str(index + 1)
                )
            elif round_msg == "pvp":
                game_assets.PVP_ROUND.add(
                    self.round[0].split("-")[0] + "-" + str(index + 1)
                )
            elif round_msg == "encounter":
                game_assets.ENCOUNTER_ROUNDS.add(
                    self.round[0].split("-")[0] + "-" + str(index + 1)
                )
                if index + 1 == 2 and 3 <= int(self.round[0].split("-")[0]) <= 4:
                    game_assets.AUGMENT_ROUNDS.add(
                        self.round[0].split("-")[0] + "-" + str(index + 2)
                    )

    def second_round(self) -> None:
        """Move unknown champion to board after first carousel"""
        logger.info(f"[初始对局] {self.round[0]}")
        self.message_queue.put("CLEAR")
        while True:
            result = arena_functions.check_bench_occupied()
            if any(result):
                break
        self.arena.bench[result.index(True)] = "?"
        for _ in range(arena_functions.fetch_level()):
            self.arena.move_unknown()
        sleep(2.5)
        self.arena.portal_augment()
        self.end_round_tasks()

    def carousel_round(self) -> None:
        """Handles tasks for carousel rounds"""
        logger.info(f"[选秀] {self.round[0]}")
        self.message_queue.put("CLEAR")
        if self.round[0] == "3-4":
            self.arena.final_comp = True
        logger.info("  等待选秀结束")
        game_functions._ocr_single_champ_carousel(self.round[0])

    def pve_round(self) -> None:
        """Handles tasks for PVE rounds"""
        logger.info(f"[PvE 对局] {self.round[0]}")
        self.message_queue.put(("LOG", f"回合 {self.round[0]} 开始（PVE）"))
        self.message_queue.put("CLEAR")
        sleep(0.5)
        if self.round[0] in game_assets.AUGMENT_ROUNDS:
            sleep(1)
            self.arena.augment_roll = True
            self.arena.pick_augment()
            sleep(2.5)
        # todo 处理魔像 假人等
        if self.round[0] == "1-4":
            if self.arena.active_portal in game_assets.DUMMY_PORTALS:
                logger.info("处理魔像逻辑")
                index = self.arena.find_blue_buff()
                if index is not None:
                    mk_functions.left_click(screen_coords.BOARD_LOC[index].get_coords())
                    sleep(0.5)
                    mk_functions.left_click(
                        screen_coords.BOARD_LOC[
                            self.arena.unknown_slots[len(self.arena.board_unknown)]
                        ].get_coords()
                    )
                    self.arena.board_unknown.append("魔像")
        # 处理额外的强化符文
        if self.round[0] == "2-6":
            if self.arena.active_portal in game_assets.ADDITIONAL_AUGMENT:
                logger.info("选择额外强化符文")
                self.arena.pick_augment()

        self.arena.fix_bench_state()
        self.arena.spend_gold()
        self.arena.move_champions()
        self.arena.replace_unknown()
        if self.arena.final_comp:
            self.arena.final_comp_check()
        self.arena.bench_cleanup()

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
        """处理PVP回合的任务"""
        logger.info(f"[PvP 对局] {self.round[0]}")
        self.message_queue.put(("LOG", f"回合 {self.round[0]} 开始（PVP）"))
        self.message_queue.put("CLEAR")
        sleep(0.5)

        if self.round[0] in game_assets.AUGMENT_ROUNDS:
            sleep(1)
            self.arena.augment_roll = True
            self.arena.pick_augment()
            sleep(2.5)
        if self.round[0] in ("2-1", "2-5"):
            self.arena.buy_xp_round()
        if self.round[0] in game_assets.PICKUP_ROUNDS:
            logger.info("  拾取战利品")
            self.message_queue.put(("LOG", "YOLO检测中..."))
            game_functions.pickup_items()
            self.message_queue.put(("LOG", "战利品拾取完成"))

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

        if self.round[0] in game_assets.ITEM_PLACEMENT_ROUNDS:
            sleep(1)
            self.arena.place_items()
        self.end_round_tasks()

    def end_round_tasks(self) -> None:
        """跨回合的常见任务发生在最后"""
        self.arena.HP = arena_functions.fetch_health_ranking()
        if self.arena.HP:
            logger.info(f" 生命值：{self.arena.HP[0][1]}")
            logger.info(f" 排名：{self.arena.HP[0][0]}")

            # 推送血量状态到 overlay
            self.message_queue.put(("STATUS", {
                "running": True,
                "paused": False,
                "stop_after_game": False,
                "round": self.round[0],
            }))

            if self.arena.HP[0][1] <= settings.HEALTH:
                self.arena.spam_roll = True
            else:
                self.arena.spam_roll = False

        self.arena.get_label()
        game_functions.default_pos()