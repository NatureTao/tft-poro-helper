"""
处理进入游戏：创建房间 → 匹配 → 自动接受
"""
import os
import re
from time import sleep
import json
from requests.auth import HTTPBasicAuth
import requests
import urllib3

import settings
from utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_client() -> tuple:
    """获取英雄联盟客户端端口和令牌"""
    logger.info("正在获取客户端连接信息...")

    cmd = (
        'powershell -Command "'
        'Get-CimInstance Win32_Process -Filter \'Name=\\"LeagueClientUx.exe\\"\' | '
        'Select-Object -ExpandProperty CommandLine'
        '"'
    )
    re_app_port = re.compile(r'--app-port=([0-9]*)')
    re_remoting_auth_token = re.compile(r'--remoting-auth-token=([\w-]*)')

    while True:
        output = "".join(os.popen(cmd).readlines())
        if output.strip():
            app_port = re.findall(re_app_port, output)[0]
            token = re.findall(re_remoting_auth_token, output)[0]
            server_url = f"https://127.0.0.1:{app_port}"
            logger.info(f"客户端已连接 → {server_url}")
            return token, server_url
        logger.warning("客户端未启动，10秒后重试...")
        sleep(10)


def create_lobby(client_info: tuple) -> bool:
    """创建房间"""
    payload = json.dumps({"queueId": settings.QUEUE_ID})
    try:
        resp = requests.post(
            f"{client_info[1]}/lol-lobby/v2/lobby/",
            data=payload,
            auth=HTTPBasicAuth('riot', client_info[0]),
            timeout=10,
            verify=False,
        )
        if resp.status_code == 200:
            logger.info("房间已创建")
            return True
        return False
    except Exception as e:
        logger.error(f"创建房间失败: {e}")
        return False


def start_queue(client_info: tuple) -> bool:
    """开始匹配"""
    try:
        resp = requests.post(
            f"{client_info[1]}/lol-lobby/v2/lobby/matchmaking/search",
            auth=HTTPBasicAuth('riot', client_info[0]),
            timeout=10,
            verify=False,
        )
        if resp.status_code == 204:
            logger.info("匹配中...")
            return True
        return False
    except Exception as e:
        logger.error(f"开始匹配失败: {e}")
        return False


def accept_queue(client_info: tuple) -> None:
    """接受对局（延迟 2-5 秒模拟真人）"""
    import random
    delay = random.uniform(2, 5)
    sleep(delay)

    requests.post(
        f"{client_info[1]}/lol-matchmaking/v1/ready-check/accept",
        auth=HTTPBasicAuth('riot', client_info[0]),
        timeout=10,
        verify=False,
    )
    logger.info("已接受对局,等待其他玩家中...")


def check_game_status(client_info: tuple) -> str:
    """检查当前游戏状态"""
    try:
        resp = requests.get(
            f"{client_info[1]}/lol-gameflow/v1/session",
            auth=HTTPBasicAuth('riot', client_info[0]),
            timeout=10,
            verify=False,
        )
        return resp.json().get("phase", "None")
    except Exception:
        return "None"


def reconnect(client_info: tuple) -> None:
    """重新连接游戏"""
    requests.post(
        f"{client_info[1]}/lol-gameflow/v1/reconnect",
        auth=HTTPBasicAuth('riot', client_info[0]),
        timeout=10,
        verify=False,
    )
    logger.info("重新连接游戏")


def change_arena_skin(client_info: tuple) -> None:
    """更改棋盘皮肤为默认"""
    try:
        resp = requests.delete(
            f"{client_info[1]}/lol-cosmetics/v1/selection/tft-map-skin",
            auth=HTTPBasicAuth('riot', client_info[0]),
            timeout=10,
            verify=False,
        )
        if resp.status_code == 204:
            logger.info("棋盘皮肤已设为默认")
    except Exception as e:
        logger.warning(f"更改棋盘皮肤失败: {e}")


def queue() -> None:
    """进入对局的完整流程"""
    client_info = get_client()

    # 1. 如果正在游戏中，等待结束
    while check_game_status(client_info) == "InProgress":
        sleep(2)

    # 2. 如果需要重连
    if check_game_status(client_info) == "Reconnect":
        logger.info("检测到重连状态")
        reconnect(client_info)
        return

    # 3. 创建房间
    while not create_lobby(client_info):
        sleep(3)

    # 4. 改皮肤
    change_arena_skin(client_info)
    sleep(3)

    # 5. 状态机：匹配 → 接受 → 进入游戏
    last_state = ""
    while True:
        state = check_game_status(client_info)
        if state != last_state:
            logger.info(f"游戏状态: {state}")
            last_state = state

        if state == "None":
            create_lobby(client_info)
        elif state == "Lobby":
            start_queue(client_info)
        elif state == "ReadyCheck":
            accept_queue(client_info)
        elif state == "InProgress":
            logger.info("对局开始！")
            return
        sleep(3)


if __name__ == "__main__":
    import settings
    from utils.logger import logger

    print("=" * 50)
    print("  自动匹配测试")
    print(f"  模式: {'排位' if settings.QUEUE_ID == 1100 else '匹配'}")
    print("=" * 50)

    try:
        queue()
    except KeyboardInterrupt:
        logger.info("用户取消")
    except Exception as e:
        logger.error(f"异常: {e}")