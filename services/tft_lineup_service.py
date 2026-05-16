"""
腾讯 TFT 阵容数据服务
- 获取阵容列表
- 清洗数据（英雄/装备/符文 ID → 中文名）
- 导出为标准 squad JSON 格式
"""
import os
import re
import json
import time
import requests
from typing import List, Dict, Optional


class TFTLineupService:
    """
    腾讯 TFT 阵容数据服务

    使用示例:
        tft = TFTLineupService()

        # 导出所有阵容为 squad 文件
        tft.export_all_squads("squads_qq")

        # 获取单个阵容的 squad 格式
        squad = tft.get_squad("14127")
    """

    _HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://lol.qq.com/',
        'Origin': 'https://lol.qq.com',
    }

    # 基础数据源 URL
    _URL_CHESS = 'https://game.gtimg.cn/images/lol/act/img/tft/js/chess.js'
    _URL_EQUIP = 'https://game.gtimg.cn/images/lol/act/img/tft/js/equip.js'
    _URL_HEX   = 'https://game.gtimg.cn/images/lol/act/img/tft/js/hex.js'

    # 默认避免的强化符文（会改变已购买棋子）
    DEFAULT_AVOID_AUGMENTS = ["潘朵拉的备战席", "潘朵拉的席位"]

    def __init__(self, season: str = 's17', cache_ttl: int = 1800):
        """
        Args:
            season: 赛季标识，如 's17'
            cache_ttl: 映射缓存时间（秒），默认 30 分钟
        """
        self._season = season
        self._lineup_list: List[Dict] = []
        self._is_loaded = False
        self._session = requests.Session()
        self._session.headers.update(self._HEADERS)

        # ID → 中文名 映射缓存
        self._chess_map: Dict[str, str] = {}       # hero_id → displayName
        self._chess_cost: Dict[str, int] = {}      # hero_id → cost
        self._equip_map: Dict[str, str] = {}       # equipId → name
        self._hex_map: Dict[str, str] = {}         # hexId → name
        self._cache_expire: float = 0.0
        self._cache_ttl = cache_ttl

    # ==================================================================
    # 公开方法 — 阵容列表
    # ==================================================================

    def get_all_lineups(self, force_reload: bool = False) -> List[Dict]:
        """获取当前赛季所有阵容的原始数据"""
        if force_reload:
            self._is_loaded = False
        if not self._is_loaded:
            self._load_lineups()
        return self._lineup_list

    def get_lineup_by_id(self, lineup_id: str) -> Optional[Dict]:
        """根据 ID 获取单个阵容原始数据"""
        for lineup in self.get_all_lineups():
            if str(lineup.get('id')) == str(lineup_id):
                return lineup
        return None

    def get_count(self) -> int:
        """获取阵容总数"""
        return len(self.get_all_lineups())

    def get_names(self) -> List[str]:
        """获取所有阵容名称"""
        return [self._extract_name(item) for item in self.get_all_lineups()]

    def refresh(self) -> None:
        """强制刷新阵容列表"""
        self._is_loaded = False
        self._lineup_list = []

    # ==================================================================
    # 公开方法 — Squad 导出
    # ==================================================================

    def get_squad(self, lineup_id: str) -> Optional[Dict]:
        """
        获取单个阵容的 squad 格式

        Returns:
            {
                "HERO": {
                    "薇古丝": {"seat": 27, "items": ["鬼索的狂暴之刃", ...], "star": 2},
                    ...
                },
                "AUGMENTS": [...],
                "AVOID_AUGMENTS": [...]
            }
        """
        cleaned = self._clean_lineup(lineup_id)
        if not cleaned:
            return None
        return self._to_squad(cleaned)

    def export_all_squads(self, output_dir: str = "squads_qq") -> int:
        """
        将所有阵容导出为 squad JSON 文件

        Args:
            output_dir: 输出目录

        Returns:
            生成的阵容文件数量
        """
        os.makedirs(output_dir, exist_ok=True)
        count = 0

        for lineup in self.get_all_lineups():
            lid = str(lineup.get("id", ""))
            if not lid:
                continue

            squad = self.get_squad(lid)
            if not squad or not squad.get("HERO"):
                continue

            name = self._extract_name(lineup)
            safe = re.sub(r'[<>:"/\\|?*]', '', name)[:50].strip()
            filepath = os.path.join(output_dir, f"{safe}.json")

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(squad, f, ensure_ascii=False, indent=2)
            count += 1

        print(f"已生成 {count} 个阵容文件到 {output_dir}/")
        return count

    # ==================================================================
    # 内部方法 — 数据加载
    # ==================================================================

    def _load_lineups(self) -> None:
        """请求阵容列表接口"""
        url = f'https://game.gtimg.cn/images/lol/act/tftzlkauto/json/lineupJson/{self._season}/6/lineup_detail_total.json'
        url += f"?v={int(time.time() / 180000)}"
        resp = self._session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        self._lineup_list = (
            data.get('lineup_list') if isinstance(data, dict)
            else data if isinstance(data, list)
            else []
        )
        self._is_loaded = True

    def _load_mappers(self) -> None:
        """加载英雄/装备/符文的 ID→名称 映射（带缓存）"""
        if self._chess_map and time.time() < self._cache_expire:
            return

        # 英雄
        try:
            chess = self._session.get(self._URL_CHESS, timeout=15).json()
            for item in chess.get('data', []):
                cid = item.get('chessId', '')
                name = item.get('displayName', '')
                cost = int(item.get('price', 1))
                if cid and name:
                    self._chess_map[cid] = name
                    self._chess_cost[cid] = cost
        except Exception as e:
            print(f"[警告] 英雄数据加载失败: {e}")

        # 装备
        try:
            equip = self._session.get(self._URL_EQUIP, timeout=15).json()
            for item in equip.get('data', []):
                eid = item.get('equipId', '')
                name = item.get('name', '')
                if eid and name:
                    self._equip_map[eid] = name
        except Exception as e:
            print(f"[警告] 装备数据加载失败: {e}")

        # 符文
        try:
            hex_data = self._session.get(self._URL_HEX, timeout=15).json()
            for item in hex_data.get('data', {}).values():
                if isinstance(item, dict) and item.get('type') != '0':
                    hid = item.get('hexId', '')
                    name = item.get('name', '')
                    if hid and name:
                        self._hex_map[hid] = name
        except Exception as e:
            print(f"[警告] 符文数据加载失败: {e}")

        self._cache_expire = time.time() + self._cache_ttl

    # ==================================================================
    # 内部方法 — ID → 名称
    # ==================================================================

    def _hero_name(self, hero_id: str) -> str:
        """英雄 ID → 中文名"""
        self._load_mappers()
        return self._chess_map.get(str(hero_id), f"英雄{hero_id}")

    def _equip_name(self, equip_id: str) -> str:
        """装备 ID → 中文名"""
        self._load_mappers()
        return self._equip_map.get(str(equip_id), f"装备{equip_id}")

    def _equip_names(self, equip_ids: str) -> List[str]:
        """逗号分隔的装备 ID 字符串 → 名称列表"""
        if not equip_ids:
            return []
        return [self._equip_name(e.strip()) for e in equip_ids.split(',') if e.strip()]

    def _hex_names(self, hex_ids: str) -> List[str]:
        """逗号分隔的符文 ID 字符串 → 名称列表"""
        if not hex_ids:
            return []
        return [self._hex_map.get(h.strip(), f"符文{h.strip()}") for h in hex_ids.split(',') if h.strip()]

    # ==================================================================
    # 内部方法 — 位置转换
    # ==================================================================

    def _location_to_seat(self, location: str) -> int:
        """
        将 "row,col" 格式的位置转为 seat 编号 (0-27)

        棋盘 4行×7列：
          第1行 (row=1) col=1~7 → seat 0~6
          第2行 (row=2) col=1~7 → seat 7~13
          第3行 (row=3) col=1~7 → seat 14~20
          第4行 (row=4) col=1~7 → seat 21~27
        """
        if not location:
            return 0
        parts = location.split(",")
        if len(parts) != 2:
            return 0
        try:
            row = int(parts[0].strip())
            col = int(parts[1].strip())
        except ValueError:
            return 0
        if row < 1 or row > 4 or col < 1 or col > 7:
            return 0
        return (row - 1) * 7 + (col - 1)

    # ==================================================================
    # 内部方法 — 数据清洗 & 转换
    # ==================================================================

    def _clean_lineup(self, lineup_id: str) -> Optional[Dict]:
        """清洗单个阵容：ID 全部转为中文名"""
        lineup = self.get_lineup_by_id(lineup_id)
        if not lineup:
            return None

        detail = lineup.get('detail', '')
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except json.JSONDecodeError:
                detail = {}

        # 取最终阵容，没有则用 9 级阵容
        heroes = detail.get('hero_location') or detail.get('hero_location_l9') or []
        cleaned_heroes = []

        for h in heroes:
            hid = h.get('hero_id', '') or h.get('chess_id', '')
            if not hid:
                continue
            star = int(h.get('numStar', 1))
            if star <= 1:
                star = 2

            cleaned_heroes.append({
                'hero': self._hero_name(hid),
                'star': star,
                'location': h.get('location', ''),
                'equips': self._equip_names(h.get('equipment_id', '')),
            })

        return {
            'name': self._extract_name(lineup),
            'heroes': cleaned_heroes,
            'hex_recomm': self._hex_names(detail.get('hexbuff', {}).get('recomm', '')),
            'hex_replace': self._hex_names(detail.get('hexbuff', {}).get('replace', '')),
        }

    def _to_squad(self, cleaned: Dict) -> Dict:
        """将清洗后的数据转为 squad 格式"""
        squad = {
            "HERO": {},
            "AUGMENTS": [],
            "AVOID_AUGMENTS": list(self.DEFAULT_AVOID_AUGMENTS),
        }

        for h in cleaned.get('heroes', []):
            name = h['hero']
            if not name:
                continue
            squad["HERO"][name] = {
                "seat": self._location_to_seat(h.get('location', '')),
                "items": h['equips'],
                "star": h['star'],
            }

        for aug in cleaned.get('hex_recomm', []):
            if aug:
                squad["AUGMENTS"].append(aug)
        for aug in cleaned.get('hex_replace', []):
            if aug and aug not in squad["AUGMENTS"]:
                squad["AUGMENTS"].append(aug)

        return squad

    def _extract_name(self, lineup: Dict) -> str:
        """从原始数据中提取阵容名称"""
        detail = lineup.get('detail', '')
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except json.JSONDecodeError:
                return '未知阵容'
        if isinstance(detail, dict):
            return detail.get('line_name', '未知阵容')
        return '未知阵容'
