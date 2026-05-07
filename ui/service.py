# _*_ coding: utf-8 _*_
"""
英雄联盟 LCU API 客户端数据服务
通过本地 HTTPS 接口获取玩家信息、货币、段位等数据
"""
import os
import re
from datetime import datetime
from typing import Optional

import psutil
import requests
import urllib3
from requests import RequestException, Session
from requests.auth import HTTPBasicAuth

# 禁用 SSL 警告（本地 LCU API 使用自签名证书）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def get_client_uptime() -> int:
    """
    获取 LeagueClientUx.exe 的运行时长（秒）
    用于判断客户端是否刚启动（需要等 API 就绪）

    Returns:
        int: 运行秒数，未找到进程返回 0
    """
    try:
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            if proc.info.get('name') == 'LeagueClientUx.exe':
                create_time = datetime.fromtimestamp(proc.info['create_time'])
                uptime = datetime.now() - create_time
                return uptime.seconds
        return 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# LOLService —— 英雄联盟客户端数据服务
# ---------------------------------------------------------------------------

class LOLService:
    """
    通过 LCU API 获取英雄联盟客户端数据

    使用示例:
        lol = LOLService()
        lol.refresh_client()        # 手动刷新所有数据
        print(lol.gameName)         # 玩家昵称
        print(lol.rank_tft)         # 云顶段位
    """

    # 段位英文 → 中文映射
    TIER_MAP = {
        'IRON': '黑铁',
        'BRONZE': '青铜',
        'SILVER': '白银',
        'GOLD': '黄金',
        'PLATINUM': '铂金',
        'DIAMOND': '钻石',
        'MASTER': '大师',
        'GRANDMASTER': '宗师',
        'CHALLENGER': '王者',
    }



    # 队列名称 → 对象属性名
    RANK_QUEUES = [
        ('RANKED_SOLO_5x5',      'rank_solo'),        # 单双排
        ('RANKED_FLEX_SR',       'rank_flex'),         # 灵活排位
        ('RANKED_TFT',           'rank_tft'),          # 云顶之弈
        ('RANKED_TFT_TURBO',     'rank_tft_turbo'),    # 云顶狂暴
        ('RANKED_TFT_DOUBLE_UP', 'rank_tft_double'),   # 云顶双人
    ]

    # ==================================================================
    # 初始化和重置
    # ==================================================================

    def __init__(self):
        # ---- 连接信息 ----
        self.server_url: str = ""           # LCU API 地址 (https://127.0.0.1:PORT)
        self.remoting_auth_token: str = ""  # 认证令牌

        # ---- 通行证 ----
        self.passes: list[dict] = []  # 所有通行证列表
        self.pass_id: str = ""              # 通行证 ID
        self.pass_name: str = "未知"         # 通行证名称
        self.currentLevel: int = 0          # 当前等级
        self.currentLevelXP: int = 0        # 当前等级经验
        self.totalLevelXP: int = 0          # 升级所需总经验

        # ---- 玩家基本信息 ----
        self.gameName: str = "未知"          # 游戏昵称
        self.tagLine: str = "未知"           # 后缀标签 (#后面的部分)
        self.profileIconId: int = 0         # 头像 ID
        self.avatar: Optional[bytes] = None  # 头像图片二进制数据
        self.summonerLevel: int = 0         # 召唤师等级
        self.xpSinceLastLevel: int = 0      # 当前等级已获经验
        self.xpUntilNextLevel: int = 0      # 升级所需经验

        # ---- 货币 ----
        self.RP: int = 0                    # 点券
        self.lol_blue_essence: int = 0      # 蓝色精粹
        self.lol_orange_essence: int = 0    # 橙色精粹
        self.lol_mythic_essence: int = 0    # 神话精粹
        self.TFT_TREASURE_TROVE_TOKEN: int = 0  # 云石
        self.tft_standard_coin: int = 0         # 云顶召唤水晶
        self.tft_star_fragments: int = 0        # 星之碎片

        # ---- 段位（所有模式） ----
        self.rank_solo: str = "未定级"
        self.rank_flex: str = "未定级"
        self.rank_tft: str = "未定级"
        self.rank_tft_turbo: str = "未定级"
        self.rank_tft_double: str = "未定级"

        # 初始化时自动刷新一次
        self.refresh_client()

    def empty(self) -> None:
        """
        将所有数据重置为「等待/未知」状态
        当客户端未启动或 API 不可用时调用
        """
        # 连接信息不重置，保留上一次有效值

        self.pass_name = "等待游戏启动"
        self.currentLevel = 0
        self.currentLevelXP = 0
        self.totalLevelXP = 0

        self.gameName = "未知"
        self.tagLine = "未知"
        self.profileIconId = 0
        self.avatar = None
        self.summonerLevel = 0
        self.xpSinceLastLevel = 0
        self.xpUntilNextLevel = 0

        self.RP = 0
        self.lol_blue_essence = 0
        self.lol_orange_essence = 0
        self.lol_mythic_essence = 0
        self.TFT_TREASURE_TROVE_TOKEN = 0
        self.tft_standard_coin = 0
        self.tft_star_fragments = 0

        self.rank_solo = "等待游戏启动"
        self.rank_flex = "等待游戏启动"
        self.rank_tft = "等待游戏启动"
        self.rank_tft_turbo = "等待游戏启动"
        self.rank_tft_double = "等待游戏启动"

    # ==================================================================
    # 主刷新流程
    # ==================================================================

    def refresh_client(self) -> None:
        """
        刷新所有客户端数据
        流程: 获取连接 → 建立会话 → 并行拉取各模块数据
        """
        # 客户端启动不足25秒，API 可能尚未就绪
        if get_client_uptime() < 25:
            self.empty()
            return

        try:
            # Step 1: 获取端口和 token
            self._get_connection_info()

            # Step 2: 建立复用会话（减少 TCP 握手开销）
            with requests.Session() as session:
                session.auth = HTTPBasicAuth('riot', self.remoting_auth_token)
                session.verify = False
                session.timeout = 5

                # Step 3: 并行拉取所有数据模块
                self._get_player_info(session)
                self._get_pass_info(session)
                self._get_avatar(session)
                self._get_wallet(session)
                self._get_rank_info(session)

        except ConnectionError:
            self.empty()
        except RequestException:
            self.empty()
        except Exception:
            self.empty()

    # ==================================================================
    # 连接获取
    # ==================================================================

    def _get_connection_info(self) -> None:
        """
        从 LeagueClientUx 进程命令行获取端口和令牌

        Raises:
            ConnectionError: 客户端未启动或无法解析
        """
        re_app_port = re.compile(r'--app-port=([0-9]*)')
        re_remoting_auth_token = re.compile(r'--remoting-auth-token=([\w-]*)')

        cmd = (
            'powershell -Command "'
            'Get-CimInstance Win32_Process -Filter \'Name=\\"LeagueClientUx.exe\\"\' | '
            'Select-Object -ExpandProperty CommandLine'
            '"'
        )

        output = "".join(os.popen(cmd).readlines())

        if not output.strip():
            raise ConnectionError("客户端未启动")

        app_port = re.findall(re_app_port, output)[0]
        token = re.findall(re_remoting_auth_token, output)[0]

        self.remoting_auth_token = token
        self.server_url = f"https://127.0.0.1:{app_port}"

    # ==================================================================
    # 数据模块 —— 各接口独立获取，互不依赖
    # ==================================================================

    def _get_player_info(self, session: Session) -> None:
        """
        获取玩家基本信息
        接口: /lol-summoner/v1/current-summoner
        """
        try:
            r = session.get(f"{self.server_url}/lol-summoner/v1/current-summoner")
            if r.status_code == 200:
                data = r.json()
                self.gameName = data.get("gameName", "未知")
                self.tagLine = data.get("tagLine", "未知")
                self.profileIconId = data.get("profileIconId", 0)
                self.summonerLevel = data.get("summonerLevel", 0)
                self.xpSinceLastLevel = data.get("xpSinceLastLevel", 0)
                self.xpUntilNextLevel = data.get("xpUntilNextLevel", 0)
        except Exception:
            pass

    def _get_wallet(self, session: Session) -> None:
        """
        获取玩家货币信息
        接口: /lol-inventory/v1/wallet/me
        """
        try:
            r = session.get(f"{self.server_url}/lol-inventory/v1/wallet/me")
            if r.status_code == 200:
                data = r.json()
                self.RP = data.get('RP', 0)
                self.lol_blue_essence = data.get('lol_blue_essence', 0)
                self.lol_orange_essence = data.get('lol_orange_essence', 0)
                self.lol_mythic_essence = data.get('lol_mythic_essence', 0)
                self.TFT_TREASURE_TROVE_TOKEN = data.get('TFT_TREASURE_TROVE_TOKEN', 0)
                self.tft_standard_coin = data.get('tft_standard_coin', 0)
                self.tft_star_fragments = data.get('tft_star_fragments', 0)
        except Exception:
            pass

    def _get_pass_info(self, session: Session) -> None:
        """
        获取所有通行证信息
        接口: /lol-event-hub/v1/events → /lol-event-hub/v1/events/{id}/reward-track/xp

        Returns:
            存储到 self.passes 列表，每个元素为 dict:
            {
                'id': str,           # 通行证 ID
                'name': str,         # 通行证名称
                'type': str,         # 子类型 (Default / Mayhem / ...)
                'level': int,        # 当前等级
                'current_xp': int,   # 当前经验
                'total_xp': int,     # 升级所需总经验
            }
            同时为兼容旧代码，self.pass_name / self.currentLevel 等保留为主通行证的值
        """
        try:
            r = session.get(f"{self.server_url}/lol-event-hub/v1/events")
            if r.status_code != 200 or len(r.json()) == 0:
                return

            events = r.json()
            self.passes = []  # 通行证数组

            for event in events:
                event_info = event.get('eventInfo', {})
                if event_info.get('eventType') != 'kSeasonPass':
                    continue

                pass_id = event_info['eventId']
                pass_name = event_info['eventName']
                pass_type = event_info.get('seasonPassSubType', 'Unknown')

                # 获取经验进度
                level = 0
                current_xp = 0
                total_xp = 0

                try:
                    r2 = session.get(
                        f"{self.server_url}/lol-event-hub/v1/events/{pass_id}/reward-track/xp"
                    )
                    if r2.status_code == 200:
                        xp_data = r2.json()
                        level = xp_data.get('currentLevel', 0)
                        current_xp = xp_data.get('currentLevelXP', 0)
                        total_xp = xp_data.get('totalLevelXP', 0)
                except Exception:
                    pass

                self.passes.append({
                    'id': pass_id,
                    'name': pass_name,
                    'type': pass_type,
                    'level': level,
                    'current_xp': current_xp,
                    'total_xp': total_xp,
                })

            # 兼容旧代码：主通行证 = Default 类型的第一个
            default_pass = next(
                (p for p in self.passes if p['type'] == 'Default'),
                self.passes[0] if self.passes else None
            )
            if default_pass:
                self.pass_name = default_pass['name']
                self.currentLevel = default_pass['level']
                self.currentLevelXP = default_pass['current_xp']
                self.totalLevelXP = default_pass['total_xp']

        except Exception:
            pass

    def _get_avatar(self, session: Session) -> None:
        """
        获取玩家头像图片
        接口: /lol-game-data/assets/v1/profile-icons/{iconId}.jpg
        """
        if self.profileIconId == 0:
            return
        try:
            r = session.get(
                f"{self.server_url}/lol-game-data/assets/v1/profile-icons/{self.profileIconId}.jpg"
            )
            if r.status_code == 200:
                self.avatar = r.content
        except Exception:
            pass

    def _get_rank_info(self, session: Session) -> None:
        """
        获取所有模式段位信息
        接口: /lol-ranked/v1/current-ranked-stats

        支持的队列:
            - RANKED_SOLO_5x5      → rank_solo      (单双排)
            - RANKED_FLEX_SR       → rank_flex       (灵活排位)
            - RANKED_TFT           → rank_tft        (云顶之弈)
            - RANKED_TFT_TURBO     → rank_tft_turbo  (云顶狂暴)
            - RANKED_TFT_DOUBLE_UP → rank_tft_double (云顶双人)
        """
        try:
            r = session.get(f"{self.server_url}/lol-ranked/v1/current-ranked-stats")
            if r.status_code == 200:
                data = r.json()
                queue_map = data.get('queueMap', {})

                for queue_key, attr_name in self.RANK_QUEUES:
                    info = queue_map.get(queue_key, {})
                    tier = info.get('tier', '')
                    division = info.get('division', '')
                    if tier:
                        tier_cn = self.TIER_MAP.get(tier, tier)
                        setattr(self, attr_name, f"{tier_cn} {division}")
        except Exception:
            pass

lol = LOLService()


# ==================================================================
# 独立运行测试
# ==================================================================

if __name__ == '__main__':
    print("=" * 50)
    print("  英雄联盟 LCU API 数据测试")
    print("=" * 50)

    # 连接信息
    print(f"\n[连接] {lol.server_url}")
    print(f"[令牌] {lol.remoting_auth_token}")

    # 玩家信息
    print(f"\n[玩家] {lol.gameName}#{lol.tagLine}")
    print(f"[等级] Lv.{lol.summonerLevel} "
          f"({lol.xpSinceLastLevel}/{lol.xpUntilNextLevel})")

    # 货币
    print(f"\n[货币]")
    print(f"  点券:       {lol.RP}")
    print(f"  蓝色精粹:   {lol.lol_blue_essence}")
    print(f"  橙色精粹:   {lol.lol_orange_essence}")
    print(f"  神话精粹:   {lol.lol_mythic_essence}")
    print(f"  云石:       {lol.TFT_TREASURE_TROVE_TOKEN}")

    # 通行证
    print(f"\n[通行证]")
    for p in lol.passes:
        print(f"  {p['name']} [{p['type']}] Lv.{p['level']} ({p['current_xp']}/{p['total_xp']})")

    # 主通行证快捷访问
    print(f"\n[主通行证] {lol.pass_name} Lv.{lol.currentLevel} ({lol.currentLevelXP}/{lol.totalLevelXP})")

    # 段位
    print(f"\n[段位]")
    print(f"  单双排:     {lol.rank_solo}")
    print(f"  灵活排位:   {lol.rank_flex}")
    print(f"  云顶之弈:   {lol.rank_tft}")
    print(f"  云顶狂暴:   {lol.rank_tft_turbo}")
    print(f"  云顶双人:   {lol.rank_tft_double}")