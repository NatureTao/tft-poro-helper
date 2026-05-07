"""
国际化 / 本地化模块
"""
from enum import Enum
from typing import Dict


class Language(Enum):
    ZH_CN = "zh_CN"
    ZH_TW = "zh_TW"
    EN_US = "en_US"


# ======================================================================
# 所有需要翻译的 key（新增 key 必须在这里注册）
# ======================================================================
class I18nKey:
    """翻译 key 枚举"""
    HOME_PAGE_NAME  = "home_page_name"
    START_BOT = "start_bot"
    STOP_BOT = "stop_bot"
    MATCH = "match"
    RANK = "rank"
    NORMAL = "normal"
    DEBUG = "debug"
    LANGUAGE = "language"
    MODE_SELECT = "mode_select"
    LOG_LEVEL = "log_level"
    STATS = "stats"
    THIS_GAME = "this_game"
    TOTAL_GAMES = "total_games"
    RUNTIME = "runtime"
    PASS = "pass"
    TFT_RANK = "tft_rank"
    RUN_LOG = "run_log"
    CLEAR = "clear"
    SOLO_RANK = "solo_rank"
    FLEX_RANK = "flex_rank"
    TURBO_RANK = "turbo_rank"


# ======================================================================
# 翻译字典（每种语言必须覆盖所有 I18nKey）
# ======================================================================
TRANSLATIONS: Dict[Language, Dict[str, str]] = {
    Language.ZH_CN: {
        I18nKey.HOME_PAGE_NAME: "首页",
        I18nKey.START_BOT: "开始挂机",
        I18nKey.STOP_BOT: "结束挂机",
        I18nKey.LANGUAGE: "语言",
        I18nKey.MODE_SELECT: "模式选择",
        I18nKey.MATCH: "匹配",
        I18nKey.RANK: "排位",
        I18nKey.LOG_LEVEL: "日志等级",
        I18nKey.NORMAL: "正常",
        I18nKey.DEBUG: "调试",

        I18nKey.STATS: "挂机统计",
        I18nKey.THIS_GAME: "本次对局",
        I18nKey.TOTAL_GAMES: "累计对局",
        I18nKey.RUNTIME: "运行时长",
        I18nKey.PASS: "通行证",
        I18nKey.TFT_RANK: "云顶段位",
        I18nKey.RUN_LOG: "运行日志",
        I18nKey.CLEAR: "清空",
        I18nKey.SOLO_RANK: "单双",
        I18nKey.FLEX_RANK: "灵活",
        I18nKey.TURBO_RANK: "狂暴",
    },
    Language.ZH_TW: {
        I18nKey.START_BOT: "開始掛機",
        I18nKey.STOP_BOT: "結束掛機",
        I18nKey.MATCH: "匹配",
        I18nKey.RANK: "積分",
        I18nKey.NORMAL: "正常",
        I18nKey.DEBUG: "除錯",
        I18nKey.LANGUAGE: "語言",
        I18nKey.MODE_SELECT: "模式選擇",
        I18nKey.LOG_LEVEL: "日誌等級",
        I18nKey.STATS: "掛機統計",
        I18nKey.THIS_GAME: "本次對局",
        I18nKey.TOTAL_GAMES: "累計對局",
        I18nKey.RUNTIME: "執行時間",
        I18nKey.PASS: "通行證",
        I18nKey.TFT_RANK: "聯盟戰棋段位",
        I18nKey.RUN_LOG: "執行日誌",
        I18nKey.CLEAR: "清除",
        I18nKey.SOLO_RANK: "單雙",
        I18nKey.FLEX_RANK: "彈性",
        I18nKey.TURBO_RANK: "狂暴",
    },
    Language.EN_US: {
        I18nKey.START_BOT: "Start Bot",
        I18nKey.STOP_BOT: "Stop Bot",
        I18nKey.MATCH: "Normal",
        I18nKey.RANK: "Ranked",
        I18nKey.NORMAL: "Normal",
        I18nKey.DEBUG: "Debug",
        I18nKey.LANGUAGE: "Language",
        I18nKey.MODE_SELECT: "Game Mode",
        I18nKey.LOG_LEVEL: "Log Level",
        I18nKey.STATS: "Statistics",
        I18nKey.THIS_GAME: "This Session",
        I18nKey.TOTAL_GAMES: "Total Games",
        I18nKey.RUNTIME: "Runtime",
        I18nKey.PASS: "Battle Pass",
        I18nKey.TFT_RANK: "TFT Rank",
        I18nKey.RUN_LOG: "Console",
        I18nKey.CLEAR: "Clear",
        I18nKey.SOLO_RANK: "Solo",
        I18nKey.FLEX_RANK: "Flex",
        I18nKey.TURBO_RANK: "Turbo",
    },
}


# ======================================================================
# 全局翻译管理
# ======================================================================

class I18n:
    """全局翻译单例"""

    _current_lang = Language.ZH_CN

    @classmethod
    def set_language(cls, lang: Language):
        cls._current_lang = lang

    @classmethod
    def get(cls, key: str) -> str:
        return TRANSLATIONS.get(cls._current_lang, {}).get(key, key)

    @classmethod
    def current_lang(cls) -> Language:
        return cls._current_lang

    @classmethod
    def validate(cls) -> bool:
        """校验所有语言的 key 是否完整"""
        all_keys = set(vars(I18nKey).values())
        for lang, trans in TRANSLATIONS.items():
            missing = all_keys - set(trans.keys())
            if missing:
                print(f"[I18n] {lang.value} 缺少 key: {missing}")
                return False
        return True