"""
机器人控制器：管理 game_loop 和 overlay 进程
"""
import multiprocessing


class BotController:
    """控制机器人的启动、暂停、停止"""

    def __init__(self):
        self.message_queue = multiprocessing.Queue()
        self.game_process = None
        self.overlay_process = None

        self.is_running = False
        self.is_paused = False
        self.stop_after_game = False

    def start(self, squad_name=None):
        """启动机器人"""
        if self.is_running:
            return

        self.is_running = True
        self.is_paused = False
        self.stop_after_game = False

        # 延迟导入，仅在启动时加载
        from game_loop import game_loop, load_squad

        # 启动 overlay 子进程
        from overlay import run_overlay
        self.overlay_process = multiprocessing.Process(
            target=run_overlay,
            args=(self.message_queue,),
            daemon=True
        )
        self.overlay_process.start()

        # 加载阵容
        squad_data = None
        if squad_name:
            squad_data = load_squad(squad_name)

        # 启动游戏循环
        self.game_process = multiprocessing.Process(
            target=game_loop,
            args=(self.message_queue, squad_data),
            daemon=True
        )
        self.game_process.start()

        self._send_status()

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