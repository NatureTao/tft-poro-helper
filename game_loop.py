"""
游戏循环：匹配队列 → 创建 Game 实例 → 进入游戏循环
在 BotController 的子进程中运行
"""
import os
import time
import traceback
import json
from pathlib import Path
import multiprocessing

import settings
import auto_queue
from game import Game
from utils.logger import logger


def load_squad(squad_name):
    """加载指定的阵容配置"""
    try:
        squad_path = Path(__file__).parent / "squads" / f"{squad_name}.json"
        if squad_path.exists():
            with open(squad_path, 'r', encoding='utf-8') as f:
                squad_data = json.load(f)
                logger.info(f"已加载阵容配置: {squad_name}")
                return squad_data
        else:
            logger.warning(f"阵容配置文件不存在: {squad_name}")
            return None
    except Exception as e:
        logger.error(f"加载阵容配置失败: {e}")
        return None


def game_loop(message_queue: multiprocessing.Queue, squad_data=None):
    """机器人主循环：匹配 → 游戏 → 再匹配"""
    counter = 0

    # 显示基本信息
    logger.info("TFT OCR BOT 已启动")
    logger.info("Set15：天下无双格斗大赛")

    if settings.AUTO_POWER_OFF:
        logger.info("自动关机功能已开启")

    if settings.QUEUE_ID == 1100:
        game_mode = "排位模式"
    elif settings.QUEUE_ID == 1090:
        game_mode = "匹配模式"
    else:
        game_mode = f"未知模式 (ID:{settings.QUEUE_ID})"
    logger.info(f"当前挂机模式: {game_mode}")

    while True:
        if counter == settings.NUMBER_OF_HANGING_UP_GAMES and settings.AUTO_POWER_OFF:
            logger.info("已达到设定对局数，60秒后自动关机")
            os.system("shutdown -s -t 60")
            break

        try:
            logger.info("正在匹配队列...")
            auto_queue.queue()
            logger.info("匹配成功，进入游戏")

            # 创建游戏实例，传入 message_queue 用于推送状态
            game_instance = Game(message_queue)

            if squad_data:
                logger.info("使用阵容配置进行游戏")

            counter += 1
            logger.info(f"第 {counter} 局完成")

        except Exception as e:
            logger.error("游戏异常，正在重新连接...")
            logger.error(str(e))
            traceback.print_exc()
            time.sleep(1)