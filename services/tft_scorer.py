"""
TFT 阵容评分引擎
根据当前手牌/装备/羁绊/强化符文/商店状态，对 squad 阵容进行打分
"""
import json
import os
from typing import List, Dict, Tuple
from services.game_data_update import GameDataUpdate


class TFTScorer:
    """
    TFT 阵容评分器

    评分维度（按优先级）：
        棋子匹配 > 羁绊匹配 > 装备匹配 > 商店匹配 > 经济 > 等级 > 强化符文

    使用示例:
        scorer = TFTScorer()
        rankings = scorer.score_all(
            bench_champions={"薇古丝": {"star": 2, "count": 3}, ...},
            components=["暴风之剑", "拳套", ...],
            active_traits={"重装战士": 2, "牧羊人": 3},
            shop_champions=["凯南", "俄洛伊", ...],
            augments=["新竞争者", "英勇福袋"],
            gold=50,
            level=7,
        )
    """

    def __init__(self, squads_dir: str = "squads_qq"):
        self._squads_dir = squads_dir
        self._squads: List[Dict] = []
        self._game_data: Dict = {}
        self._load_squads()
        self._load_game_data()

    # ==================================================================
    # 数据加载
    # ==================================================================

    def _load_squads(self) -> None:
        if not os.path.exists(self._squads_dir):
            print(f"[警告] 阵容目录不存在: {self._squads_dir}")
            return
        for filename in os.listdir(self._squads_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self._squads_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        squad = json.load(f)
                    if "HERO" in squad:
                        squad["_name"] = filename.replace(".json", "")
                        self._squads.append(squad)
                except Exception as e:
                    print(f"[警告] 加载 {filename} 失败: {e}")

    def _load_game_data(self) -> None:
        try:
            gd = GameDataUpdate(origin="META_TFT", language="CN")
            gd.pull_latest_data()
            self._game_data = {
                "champions": gd.CHAMPIONS,
                "traits": gd.TRAITS,
                "combinable_items": gd.COMBINABLE_ITEMS,
            }
        except Exception as e:
            print(f"[警告] 游戏数据加载失败: {e}")

    # ==================================================================
    # 评分入口
    # ==================================================================

    def score_all(
        self,
        bench_champions: Dict[str, Dict],
        components: List[str],
        active_traits: Dict[str, int],
        shop_champions: List[str] = None,
        augments: List[str] = None,
        gold: int = 0,
        level: int = 1,
    ) -> List[Dict]:
        """对所有阵容评分，返回按分数降序的列表"""
        shop_champions = shop_champions or []
        augments = augments or []

        results = []
        for squad in self._squads:
            score, detail = self._score_one(
                squad, bench_champions, components, active_traits,
                shop_champions, augments, gold, level,
            )
            results.append({
                "name": squad.get("_name", "未知"),
                "score": score,
                "details": detail,
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    # ==================================================================
    # 单阵容评分
    # ==================================================================

    def _score_one(
        self,
        squad: Dict,
        bench: Dict,
        components: List[str],
        active_traits: Dict[str, int],
        shop_champions: List[str],
        augments: List[str],
        gold: int,
        level: int,
    ) -> Tuple[float, Dict]:
        total = 0.0
        detail = {}

        # 1. 棋子匹配分（权重最高）
        champion_score = self._score_champions(squad, bench)
        total += champion_score
        detail["champion_match"] = champion_score

        # 2. 羁绊匹配分
        trait_score = self._score_traits(squad, active_traits)
        total += trait_score
        detail["trait_match"] = trait_score

        # 3. 装备匹配分（散件合成，有棋子才加分）
        item_score = self._score_items(squad, bench, components)
        total += item_score
        detail["item_match"] = item_score

        # 4. 商店棋子匹配分
        shop_score = self._score_shop(squad, shop_champions)
        total += shop_score
        detail["shop_match"] = shop_score

        # 5. 经济可行性
        economy_score = self._score_economy(squad, gold)
        total += economy_score
        detail["economy"] = economy_score

        # 6. 等级达标
        level_score = self._score_level(squad, level)
        total += level_score
        detail["level"] = level_score

        # 7. 强化符文匹配分
        augment_score = self._score_augments(squad, augments)
        total += augment_score
        detail["augment_match"] = augment_score

        return total, detail

    # ==================================================================
    # 各维度评分
    # ==================================================================

    def _score_champions(self, squad: Dict, bench: Dict) -> float:
        """棋子匹配分：已达标 +15，快 2 星 +8，至少有 1 个 +4"""
        score = 0.0
        for hero_name, hero_data in squad.get("HERO", {}).items():
            target_star = hero_data.get("star", 2)
            if hero_name in bench:
                current = bench[hero_name]
                current_star = current.get("star", 1)
                current_count = current.get("count", 1)

                if current_star >= target_star:
                    score += 15
                elif current_count >= 2 and target_star == 2:
                    score += 8
                elif current_count >= 1:
                    score += 4
        return score

    def _score_traits(self, squad: Dict, active_traits: Dict[str, int]) -> float:
        """羁绊匹配分：完美 +10，激活 +6"""
        score = 0.0
        squad_traits = self._extract_squad_traits(squad)
        trait_breakpoints = self._game_data.get("traits", {})

        for trait_name, target_count in squad_traits.items():
            current_count = active_traits.get(trait_name, 0)
            breakpoints = trait_breakpoints.get(trait_name, [])
            min_required = breakpoints[0] if breakpoints else 99

            if current_count >= target_count:
                score += 10
            elif current_count >= min_required:
                score += 6
        return score

    def _score_items(self, squad: Dict, bench: Dict, components: List[str]) -> float:
        """装备匹配分：有棋子 + 散件齐 +8"""
        score = 0.0
        combinable = self._game_data.get("combinable_items", {})

        for hero_name, hero_data in squad.get("HERO", {}).items():
            # 必须有这个棋子才给装备加分
            if hero_name not in bench:
                continue
            for item_name in hero_data.get("items", []):
                recipe = combinable.get(item_name, [])
                if recipe and all(comp in components for comp in recipe):
                    score += 8
        return score

    def _score_shop(self, squad: Dict, shop_champions: List[str]) -> float:
        """商店匹配分：商店有阵容需要的棋子 +5/个"""
        score = 0.0
        squad_heroes = set(squad.get("HERO", {}).keys())
        for hero in shop_champions:
            if hero in squad_heroes:
                score += 5
        return score

    def _score_economy(self, squad: Dict, gold: int) -> float:
        """经济可行性：金币 ≥ 50% 总费 +12，≥ 30% +6"""
        total_cost = 0
        champions_data = self._game_data.get("champions", {})
        for hero_name in squad.get("HERO", {}):
            cost = champions_data.get(hero_name, {}).get("cost", 1)
            total_cost += cost

        if gold >= total_cost * 0.5:
            return 12
        elif gold >= total_cost * 0.3:
            return 6
        return 0

    def _score_level(self, squad: Dict, level: int) -> float:
        """等级达标：≥ 阵容等级 +8，差 1 级 +4"""
        target_level = squad.get("target_level", 8)
        if level >= target_level:
            return 8
        elif level >= target_level - 1:
            return 4
        return 0

    def _score_augments(self, squad: Dict, augments: List[str]) -> float:
        """强化符文匹配：推荐列表匹配 +10/个，避免列表命中 -20/个"""
        score = 0.0
        squad_augments = squad.get("AUGMENTS", [])
        squad_avoid = squad.get("AVOID_AUGMENTS", [])

        for aug in augments:
            if aug in squad_augments:
                score += 10
            if aug in squad_avoid:
                score -= 20
        return score

    # ==================================================================
    # 辅助方法
    # ==================================================================

    def _extract_squad_traits(self, squad: Dict) -> Dict[str, int]:
        champions_data = self._game_data.get("champions", {})
        trait_counter: Dict[str, int] = {}

        for hero_name in squad.get("HERO", {}):
            champ = champions_data.get(hero_name, {})
            for trait in champ.get("traits", []):
                trait_counter[trait] = trait_counter.get(trait, 0) + 1

        return trait_counter

    def reload_squads(self) -> None:
        self._squads.clear()
        self._load_squads()

    def reload_game_data(self) -> None:
        self._load_game_data()


# ==================================================================
# 模拟测试
# ==================================================================

if __name__ == "__main__":
    scorer = TFTScorer(squads_dir="../squads")

    print("=" * 60)
    print("  TFT 阵容评分引擎 - 模拟测试")
    print("=" * 60)

    # ── 模拟游戏状态 ──
    bench = {
        "薇古丝": {"star": 2, "count": 3},
        "俄洛伊": {"star": 1, "count": 1},
        "努努和威朗普": {"star": 1, "count": 2},
        "布里茨": {"star": 1, "count": 1},
    }

    components = [
        "暴风之剑", "拳套", "反曲之弓",
        "无用大棒", "巨人腰带", "负极斗篷",
    ]

    active_traits = {
        "重装战士": 3,
        "牧羊人": 1,
        "汪星机器人": 1,
    }

    shop_champions = [
        "卡尔玛", "巴德", "莫德凯撒", "娑娜", "凯南",
    ]

    augments = [
        "新竞争者",       # 可能在某些阵容的推荐列表里
        "英勇福袋",       # 同上
    ]

    gold = 52
    level = 6

    # ── 执行评分 ──
    rankings = scorer.score_all(
        bench_champions=bench,
        components=components,
        active_traits=active_traits,
        shop_champions=shop_champions,
        augments=augments,
        gold=gold,
        level=level,
    )

    # ── 输出结果 ──
    print(f"\n📊 共 {len(rankings)} 套阵容参与评分")
    print(f"💰 金币: {gold}  |  ⬆ 等级: {level}")
    print(f"🎒 散件: {', '.join(components)}")
    print(f"⚔ 激活羁绊: {active_traits}")
    print(f"🛒 商店棋子: {shop_champions}")
    print(f"✨ 强化符文: {augments}")
    print(f"\n{'─' * 60}")

    for i, r in enumerate(rankings[:8], 1):
        d = r["details"]
        bar = "█" * int(r["score"] / 3) if r["score"] > 0 else ""
        print(f"\n#{i} {r['name']}")
        print(f"   总分: {r['score']}  {bar}")
        print(f"   棋子={d['champion_match']:<4} 羁绊={d['trait_match']:<4} "
              f"装备={d['item_match']:<4} 商店={d['shop_match']:<4}")
        print(f"   经济={d['economy']:<4} 等级={d['level']:<4} "
              f"符文={d['augment_match']:<4}")

    # ── 推荐 ──
    if rankings:
        top = rankings[0]
        print(f"\n{'=' * 60}")
        print(f"🏆 推荐阵容: {top['name']} ({top['score']} 分)")
        if len(rankings) >= 2:
            print(f"🥈 备选: {rankings[1]['name']} ({rankings[1]['score']} 分)")
        if len(rankings) >= 3:
            print(f"🥉 备选: {rankings[2]['name']} ({rankings[2]['score']} 分)")