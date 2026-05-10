import traceback
import requests


class GameDataUpdate:

    def __init__(self,origin="QQ",language="CN",tft_set = "17"):
        self.origin = origin
        self.language = language
        self.tft_set = tft_set
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            "Pragma": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
        }

        self.CHAMPIONS = {}
        self.ALL_ITEMS = set()
        self.COMBINABLE_ITEMS = {}
        self.ALL_AUGMENTS = []
        self.TRAITS = {}

    def __str__(self):
        if self.language == "CN":
            return f"[GameDataUpdate] -> (数据源：{self.origin}) (语言：{self.language})"
        if self.language == "TW":
            return f"[GameDataUpdate] -> (數據源：{self.origin}) (語言：{self.language})"
        if self.language == "EN":
            return f"[GameDataUpdate] -> (origin：{self.origin}) (language：{self.language})"
        return "[GameDataUpdate] -> Unknown initialization attributes."

    def pull_latest_data(self):
        """
        用于更新TFT最赛季 【英雄棋子、武器装备、强化符文】
        :return:
        """
        match self.origin:
            case "META_TFT":
                import re
                def clean_name(x: str) -> str:
                    """去掉 <rules>...</rules> 标签"""
                    x = re.sub(r'</?rules>', '', x)
                    x = re.sub(r'\s+', ' ', x).strip()
                    return x

                # MetaTFT数据源
                suffix = "zh_cn" if self.language != "TW" and self.language != "EN" else "zh_tw" if self.language == "TW" else "en_us"
                data_url = f"https://data.metatft.com/lookups/TFTSet{self.tft_set}_latest_{suffix}.json"

                try:
                    result = requests.get(data_url, timeout=20)
                    if result.status_code == 200:
                        data_json =  result.json()
                        # ===== 开始数据清洗 =====
                        # 1 清洗英雄棋子
                        units = data_json.get("units", [])
                        for unit in units:
                            self.CHAMPIONS[unit["name"]] = {
                                "apiName": unit.get("apiName", ""),
                                "cost": unit.get("cost", 0),
                                "size" : 1,
                                "traits": unit.get("traits", []),
                            }

                        # 2 清洗装备
                        items = data_json.get("items", [])
                        api_to_name = {} # 建立 apiName → name 映射
                        for item in items:
                            api = item.get("apiName", "")
                            name = clean_name(item.get("name", ""))
                            if api and name:
                                api_to_name[api] = name

                        for item in items:
                            composition = item.get("composition", [])
                            item_name = clean_name(item.get("name", ""))
                            api = item.get("apiName", "")

                            if not item_name or not api:
                                continue

                            self.ALL_ITEMS.add(item_name)
                            if composition:
                                # 把配方中的 apiName 替换成name
                                cn_composition = [api_to_name.get(c, c) for c in composition]
                                self.COMBINABLE_ITEMS[item_name] = cn_composition

                        # 3 清洗强化符文
                        augments = data_json.get("augments", [])
                        for aug in augments:
                            name = aug.get("name", "")
                            api_name = aug.get("apiName", "")
                            if name and api_name:
                                self.ALL_AUGMENTS.append(name)

                        # 4 清洗羁绊
                        traits = data_json.get("traits", [])
                        for trait in traits:
                            name = trait.get("name", "")
                            api_name = trait.get("apiName", "")
                            effects = trait.get("effects", [])

                            if not name or not api_name:
                                continue

                            # 提取每个等级所需的最小人数
                            breakpoints = []
                            for effect in effects:
                                min_units = effect.get("minUnits", 0)
                                if min_units > 0:
                                    breakpoints.append(min_units)

                            self.TRAITS[name] = sorted(breakpoints)

                except Exception as e:
                    print(e,traceback.format_exc())
            # TODO 其他数据源
            case _:
                pass


# 调试
if __name__ == "__main__":
    gameData = GameDataUpdate(origin="META_TFT",language="CN",tft_set="17")
    print(gameData)
    gameData.pull_latest_data()
    print(gameData.COMBINABLE_ITEMS)
    print(gameData.ALL_ITEMS)
    print(gameData.CHAMPIONS)
    print(gameData.ALL_AUGMENTS)
    print(gameData.TRAITS)