"""
机器人控制器：管理 game_loop 和 overlay 进程
"""
import multiprocessing
from utils.logger import logger

class BotController:
    """控制机器人的启动、暂停、停止"""

    def __init__(self):
        self.message_queue = multiprocessing.Queue()
        self.game_process = None
        self.overlay_process = None

        self.is_running = False
        self.is_paused = False
        self.stop_after_game = False
        self.smart_mode = False

    def start(self, squad_name=None, smart_mode=False):
        if self.is_running:
            return

        self.is_running = True
        self.is_paused = False
        self.stop_after_game = False
        self.smart_mode = smart_mode

        # 启动 overlay 子进程
        from overlay import run_overlay
        self.overlay_process = multiprocessing.Process(
            target=run_overlay,
            args=(self.message_queue,),
            daemon=True
        )
        self.overlay_process.start()

        # 加载阵容数据（固定阵容 or 智能评分阵容列表）
        from game_loop import game_loop, load_squad
        squad_data = None
        if smart_mode:
            # 智能模式：加载所有 squad 文件，传给评分引擎
            squad_data = self._load_all_squads()
            logger.info(f"智能推荐模式：加载了 {len(squad_data)} 套阵容")
        elif squad_name:
            # 固定阵容模式：只加载一个阵容
            squad_data = load_squad(squad_name)
            logger.info(f"固定阵容模式：{squad_name}")

        # 启动游戏循环
        self.game_process = multiprocessing.Process(
            target=game_loop,
            args=(self.message_queue, squad_data, smart_mode),
            daemon=True
        )
        self.game_process.start()
        self._send_status()

    def _load_all_squads(self) -> list:
        """加载 squads/ 目录下所有阵容文件"""
        import json
        from pathlib import Path
        squads = []
        squads_dir = Path(__file__).parent / "squads"
        if squads_dir.exists():
            for f in squads_dir.glob("*.json"):
                with open(f, "r", encoding="utf-8") as fp:
                    squad = json.load(fp)
                    squad["_name"] = f.stem
                    squads.append(squad)
        return squads

    def stop(self):
        """停止机器人"""
        if not self.is_running:
            return

        self.is_running = False
        self.is_paused = False
        self.stop_after_game = False

        if self.game_process and self.game_process.is_alive():
            self.game_process.terminate()
            self.game_process.join(timeout=3)

        self.message_queue.put("CLEAR")
        self._send_status()

    def toggle_pause(self):
        """切换暂停/继续"""
        if not self.is_running:
            return
        self.is_paused = not self.is_paused
        self._send_status()

    def toggle_stop_after_game(self):
        """切换本局结束后停止"""
        if not self.is_running:
            return
        self.stop_after_game = not self.stop_after_game
        self._send_status()

    def _send_status(self):
        """推送状态到 overlay"""
        self.message_queue.put(("STATUS", {
            "running": self.is_running,
            "paused": self.is_paused,
            "stop_after_game": self.stop_after_game,
            "game_count": 0,
            "rank": "--",
            "pass_level": "--",
        }))

    def send_log(self, text: str):
        """推送日志到 overlay"""
        if self.is_running:
            self.message_queue.put(("LOG", text))

    def send_labels(self, labels: list):
        """推送英雄标签到 overlay"""
        if self.is_running:
            self.message_queue.put(("LABEL", labels))

    def cleanup(self):
        """清理所有进程"""
        self.stop()
        if self.overlay_process and self.overlay_process.is_alive():
            self.overlay_process.terminate()