"""Per-market symbol resolution.

akshare's symbol formats are inconsistent across markets: some functions
want a bare 6-digit code, some want an exchange-prefixed code, US stocks
need an East Money-internal "105.MSFT" market-prefixed code that has to be
looked up from the spot table, and futures history/realtime is keyed by a
Chinese variety name rather than a contract code. This module centralizes
that translation so registry.py's adapters can just call resolve_*() and
get back whatever string akshare actually expects.

Lookups that require hitting a network endpoint (us_stock, cn_futures) are
cached under SYMBOL_TABLE_TTL (default 24h) -- these tables change at most
daily (new listings/contracts), so there's no reason to refetch per call.
"""

from __future__ import annotations

import akshare as ak

from akshare_mcp import fetch
from akshare_mcp.cache import ResponseCache, make_key
from akshare_mcp.config import Settings

_EXCHANGE_PREFIXES = ("sh", "sz", "bj")


def strip_exchange_prefix(symbol: str) -> str:
    """"sh600519" / "SZ000001" -> "600519" / "000001". Used by markets whose
    akshare functions want a bare code (cn_stock, etf, lof, reits, cn_index).
    """
    s = symbol.strip()
    if len(s) > 2 and s[:2].lower() in _EXCHANGE_PREFIXES:
        return s[2:]
    return s


def bond_symbol_candidates(symbol: str) -> list[str]:
    """akshare's bond history/spot functions want an "sh"/"sz"-prefixed
    code, but there's no reliable rule to derive the exchange from the bare
    numeric code alone (ranges overlap between exchanges). If the caller
    already gave an exchange-prefixed symbol, use it as-is; otherwise return
    both candidates in a sensible try-order for the caller to attempt in
    sequence and use whichever succeeds.
    """
    s = symbol.strip().lower()
    if s[:2] in ("sh", "sz"):
        return [s]
    return [f"sh{s}", f"sz{s}"]


def guess_cn_exchange_prefix(code: str) -> str:
    """Guess SH/SZ/BJ from a bare 6-digit A-share code, for the xueqiu
    single-quote fast path (ak.stock_individual_spot_xq wants e.g.
    "SH600519", not a bare "600519"). Standard A-share code ranges:
    6xxxxx = Shanghai, 0xxxxx/3xxxxx = Shenzhen, 4/8/9xxxxx = Beijing.
    """
    lead = code[:1]
    if lead == "6":
        return "SH"
    if lead in ("0", "3"):
        return "SZ"
    if lead in ("4", "8", "9"):
        return "BJ"
    return "SH"


async def resolve_us_stock(symbol: str, settings: Settings, cache: ResponseCache) -> str:
    """"MSFT" -> "105.MSFT" (East Money's market-prefixed US ticker format
    used by stock_us_hist / stock_us_hist_min_em). Already-prefixed input
    passes through untouched.
    """
    s = symbol.strip()
    prefix, _, rest = s.partition(".")
    if rest and prefix.isdigit():
        return s

    suffix = s.upper()
    key = make_key("symtab", market="us_stock", kind="suffix_map")
    table = cache.get(key)
    if table is None:
        df = await fetch.call(settings, "eastmoney", ak.stock_us_spot_em)
        table = {}
        for code in df["代码"].astype(str):
            pre, sep, suf = code.partition(".")
            if sep:
                table[suf.upper()] = code
        cache.set(key, table, settings.symbol_table_ttl)

    if suffix not in table:
        raise ValueError(
            f"unknown us_stock symbol {symbol!r}; use the ticker as listed by "
            f"get_realtime_quotes(market='us_stock')"
        )
    return table[suffix]


# Standard exchange contract-code prefix -> Chinese variety name, for the
# major SHFE/DCE/CZCE/CFFEX/GFEX products. These prefixes are a public,
# stable exchange convention (not derived from any akshare table): akshare's
# own futures_symbol_mark() table maps varieties to a sina-internal request
# node code (e.g. "螺纹钢" -> "lwg_qh"), which has no resemblance to the
# standard contract-code prefix ("RB") a caller would actually type -- so it
# can't be used to resolve one from the other.
_FUTURES_PREFIX_TO_VARIETY: dict[str, str] = {
    # SHFE
    "RB": "螺纹钢", "HC": "热卷", "CU": "沪铜", "AL": "沪铝", "ZN": "沪锌",
    "PB": "沪铅", "NI": "沪镍", "SN": "沪锡", "AU": "沪金", "AG": "沪银",
    "RU": "橡胶", "BU": "沥青", "FU": "燃油", "SP": "纸浆", "SS": "不锈钢",
    "WR": "线材", "BC": "国际铜",
    # DCE
    "M": "豆粕", "Y": "豆油", "A": "豆一", "B": "豆二", "C": "玉米",
    "CS": "淀粉", "I": "铁矿石", "J": "焦炭", "JM": "焦煤", "L": "塑料",
    "V": "PVC", "PP": "聚丙烯", "EG": "乙二醇", "EB": "苯乙烯", "PG": "LPG",
    "JD": "鸡蛋", "RR": "粳米", "LH": "生猪",
    # CZCE
    "SR": "白糖", "CF": "棉花", "TA": "PTA", "MA": "甲醇", "FG": "玻璃",
    "SA": "纯碱", "OI": "菜油", "RM": "菜粕", "RS": "菜籽", "JR": "粳稻",
    "WH": "强麦", "PM": "普麦", "SF": "硅铁", "SM": "锰硅", "UR": "尿素",
    "PK": "花生", "PF": "短纤", "AP": "苹果", "CJ": "红枣", "ZC": "动力煤",
    # CFFEX
    "IF": "沪深300股指", "IH": "上证50股指", "IC": "中证500股指", "IM": "中证1000股指",
    "T": "10年国债", "TF": "5年国债", "TS": "2年国债", "TL": "30年国债",
    # GFEX
    "SI": "工业硅", "LC": "碳酸锂",
}


def resolve_futures_variety(symbol: str) -> str:
    """"RB2510" / "rb0" -> "螺纹钢" (the Chinese variety name futures_zh_realtime
    expects). A Chinese variety name passed in directly is returned as-is.
    """
    s = symbol.strip()
    if not s.isascii():
        return s

    code = "".join(ch for ch in s if not ch.isdigit()).upper()
    if code not in _FUTURES_PREFIX_TO_VARIETY:
        raise ValueError(
            f"unrecognized futures contract prefix {code!r} derived from symbol {symbol!r}; "
            "pass a Chinese variety name (e.g. '螺纹钢') or a standard contract code (e.g. 'RB2510', 'rb0')"
        )
    return _FUTURES_PREFIX_TO_VARIETY[code]
