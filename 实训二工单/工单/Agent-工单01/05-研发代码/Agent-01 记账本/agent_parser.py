"""
NLP意图解析模块
将自然语言转换为结构化记账数据
工单编号：人工智能NLP-Agent数字人项目-01-记账本任务工单V1.1-20250206
"""

import re
from datetime import date, timedelta
from typing import Optional, Tuple

from config import FAMILY_MEMBERS

# ============================================================
# 成员别名映射
# ============================================================
MEMBER_ALIASES = {
    "我": None,       # "我"以后会提示用户选择具体成员
    "老公": "爸爸",
    "老公公": "爸爸",
    "老婆": "妈妈",
    "老婆婆": "妈妈",
    "孩子": "女儿",
    "小孩": "女儿",
    "儿子": "爸爸",   # fallback — 用户没有儿子，暂且映射爸爸
}

# ============================================================
# 类别关键词映射 — 按匹配优先级排列（先精确后宽泛）
# ============================================================
CATEGORY_KEYWORDS = {
    # 书籍
    "买书": ["买书", "三体", "小说", "教材", "课本", "漫画", "杂志",
             "绘本", "学习资料", "教辅", "课外书", "读书"],
    # 餐饮
    "餐饮": ["买菜", "下馆子", "火锅", "奶茶", "肯德基", "麦当劳", "必胜客",
             "烧烤", "日料", "外卖", "零食", "水果", "蛋糕", "面包",
             "晚餐", "午餐", "早餐", "午饭", "晚饭", "早饭",
             "咖啡", "吃饭", "吃", "饭", "餐", "菜"],
    # 交通
    "交通": ["打车", "滴滴", "地铁", "公交", "高铁", "火车", "飞机",
             "加油", "停车", "过路费", "共享单车", "出租", "出租车",
             "车票", "机票", "通勤"],
    # 鞋类
    "鞋类": ["登山鞋", "运动鞋", "拖鞋", "皮鞋", "球鞋", "跑鞋",
             "布鞋", "棉鞋", "靴子", "高跟鞋", "凉鞋", "帆布鞋",
             "鞋"],
    # 服装
    "服装": ["衣服", "羽绒服", "T恤", "卫衣", "外套", "衬衫",
             "毛衣", "大衣", "西装", "睡衣", "内衣", "袜子", "围巾"],
    # 购物（非特定品类）
    "购物": ["包", "口红", "化妆品", "护肤品", "日用品", "洗衣液",
             "纸巾", "垃圾袋", "收纳", "挂钩", "玩具", "礼物", "礼品"],
    # 数码/电子产品
    "数码": ["手机", "iPhone", "电脑", "笔记本", "平板", "iPad",
             "耳机", "充电器", "数据线", "键盘", "鼠标", "显示器",
             "音箱", "相机", "手表", "手环", "手机壳", "贴膜"],
    # 美妆/护肤
    "美妆": ["SKII", "SK2", "面膜", "精华", "面霜", "洗面奶", "防晒",
             "水乳", "粉底", "口红", "眼影", "腮红", "卸妆", "护肤",
             "化妆品", "护肤品"],
    # 教育
    "教育": ["学费", "培训", "补习", "兴趣班", "网课", "家教",
             "文具", "辅导", "书本费"],
    # 医疗
    "医疗": ["看病", "药", "医院", "挂号", "体检", "牙科", "眼科",
             "医保", "中药", "西药", "打针", "输液"],
    # 娱乐
    "娱乐": ["电影", "门票", "游戏", "玩具", "游乐场", "KTV", "唱K",
             "旅游", "旅行", "度假", "酒店", "民宿", "景点",
             "滑雪", "游泳", "健身", "运动"],
    # 通讯
    "通讯": ["话费", "流量", "宽带", "手机", "流量卡", "电话费",
             "网费", "月租"],
    # 住房
    "住房": ["房租", "水费", "电费", "燃气", "物业", "维修", "装修",
             "暖气", "物业费"],
}

# 常见收入类别
INCOME_CATEGORIES = {
    "工资": ["工资", "薪水", "薪资", "月薪"],
    "报销": ["报销", "报销款", "报销费"],
    "奖金": ["奖金", "年终奖", "绩效", "提成"],
    "红包": ["红包", "压岁钱", "礼金", "份子钱"],
    "投资": ["利息", "收益", "分红", "理财", "基金", "股票"],
}


def detect_type(text: str) -> str:
    """判断收支类型"""
    income_keywords = ["收入", "收到", "报销", "工资", "奖金", "赚", "进账",
                       "红包", "利息", "收益", "分红", "退款", "返现",
                       "发了", "发了工资", "挣了"]
    for kw in income_keywords:
        if kw in text:
            return "收入"
    return "支出"


def detect_category(text: str, type_: str) -> str:
    """根据文本自动归类 — 优先匹配最长关键词，避免短词误匹配"""
    if type_ == "收入":
        # 按关键词长度降序排列，优先匹配更长更精确的
        for cat, keywords in INCOME_CATEGORIES.items():
            for kw in sorted(keywords, key=len, reverse=True):
                if kw in text:
                    return cat
        return "其他收入"

    # 支出：按关键词长度降序匹配
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in sorted(keywords, key=len, reverse=True):
            if kw in text:
                return cat

    return "其他支出"


def extract_member(text: str) -> Optional[str]:
    """提取家庭成员 — 支持别名"""
    # 先匹配精确成员名
    for member in FAMILY_MEMBERS:
        if member in text:
            return member

    # 再匹配别名
    for alias, mapped in MEMBER_ALIASES.items():
        if alias in text:
            return mapped

    return None


def extract_date(text: str, today: Optional[date] = None) -> Tuple[Optional[date], str]:
    """提取日期
    返回 (date, 剩余文本)
    """
    if today is None:
        today = date.today()

    # 大前天 / 前天 / 昨天 / 今天（按长度降序）
    for keyword, days in [("大前天", 3), ("前天", 2), ("昨天", 1), ("今天", 0)]:
        if keyword in text:
            text = text.replace(keyword, "").strip()
            return today - timedelta(days=days), text

    # x月x日 / x月x号
    m = re.search(r'(\d{1,2})月(\d{1,2})[日号]?', text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = today.year
        if month > today.month and today.month <= 2:
            year -= 1
        elif month < today.month:
            year = today.year
        else:
            year = today.year if day <= today.day else (today.year - 1)
        try:
            parsed = date(year, month, day)
            text = text.replace(m.group(0), "").strip()
            return parsed, text
        except ValueError:
            pass

    # 2025年1月14日
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})[日号]?', text)
    if m:
        try:
            parsed = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            text = text.replace(m.group(0), "").strip()
            return parsed, text
        except ValueError:
            pass

    return today, text


def extract_amount(text: str) -> Optional[float]:
    """提取金额 — 支持多种格式"""
    # 1. "花了/交了/冲了/充了/付了/给了/用了XX元"
    m = re.search(r'(?:花了|交了|冲了|充了|付了|给了|用了|收到|工资|挣了|赚了)(\d+(?:\.\d+)?)', text)
    if m:
        return float(m.group(1))

    # 2. "XX元" / "XX块" / "XX块钱"
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:元|块|块钱|元钱)', text)
    if m:
        return float(m.group(1))

    # 3. "交了XX" / "交了XX话费" — 金额在动词后
    m = re.search(r'(?:交|充|冲|付|给)(?:了)?(\d+(?:\.\d+)?)', text)
    if m:
        return float(m.group(1))

    # 4. "XX元" in compound (e.g., "50元话费")
    m = re.search(r'(\d+(?:\.\d+)?)元', text)
    if m:
        return float(m.group(1))

    # 5. 末尾纯数字
    m = re.search(r'(\d+(?:\.\d+)?)\s*$', text)
    if m:
        return float(m.group(1))

    return None


# 动作动词列表 — 按长度降序排列，优先匹配长的
ACTION_VERBS = sorted([
    "收到了", "收到了", "收到",
    "支出了", "支出",
    "花费了", "花费", "花了",
    "消费了", "消费",
    "用了", "用了",
    "付了款", "付了", "付款", "支付",
    "买了",   # 保留"买了"而不是"买了?"，避免误吞"买菜"中的"买"
    "买了",
    "冲了话费", "冲了", "充值", "充了",
    "交了话费", "交了", "交话费",
    "给了", "给",   # "给"在末尾时才去掉
    "赚了", "挣了", "进账",
    "报销了", "报销",
    "发了", "发工资",
], key=len, reverse=True)

# 完整量词模式 — 匹配完整词组而非单个字符
QUANTIFIER_PATTERNS = [
    (r'一[双个本条只张把瓶盒袋杯份碗盘件双套副对打]', ''),
    (r'两[双个本条只张]', ''),
    (r'这[个本条只张件双]', ''),
    (r'那[个本条只张件双]', ''),
    (r'每[个本条只张件]', ''),
    (r'几[个本条只张件]', ''),
]


def extract_item(text: str, category: str, member: str) -> str:
    """从文本中提取事项名称"""
    item = text

    # 1. 去除成员名
    if member:
        item = item.replace(member, "")
    for m in FAMILY_MEMBERS:
        item = item.replace(m, "")

    # 2. 去除别名
    for alias in MEMBER_ALIASES:
        item = item.replace(alias, "")

    # 3. 去除日期关键词
    item = re.sub(
        r'(今天|昨天|前天|大前天|\d+月\d+[日号]?|\d{4}年\d+月\d+[日号]?)',
        '', item
    ).strip()

    # 4. 去除"给"和"把"在开头
    item = re.sub(r'^[给把将]', '', item).strip()

    # 5. 去除金额（带单位和不带单位的）
    item = re.sub(r'\d+(?:\.\d+)?\s*(?:元|块|块钱|元钱)', '', item).strip()
    item = re.sub(r'\d+(?:\.\d+)?\s*$', '', item).strip()
    item = re.sub(r'\d+(?:\.\d+)?', '', item).strip()  # 去除所有残留数字

    # 6. 去除动作动词
    for verb in ACTION_VERBS:
        item = item.replace(verb, "").strip()

    # 7. 去除完整量词词组
    for pattern, replacement in QUANTIFIER_PATTERNS:
        item = re.sub(pattern, replacement, item).strip()

    # 8. 去除单个残留量词字符（不在词组中的）
    item = re.sub(r'^[双个本条件条只张把瓶盒袋杯份碗盘]', '', item).strip()

    # 9. 去除"了"的残留
    item = re.sub(r'了', '', item).strip()

    # 10. 去除"的"在末尾
    item = re.sub(r'的$', '', item).strip()

    # 11. 去掉开头"买"后跟非中文（如"买SKII"→"SKII"、"买iPhone"→"iPhone"）
    item = re.sub(r'^买([A-Za-z0-9])', r'\1', item).strip()

    # 12. 去除多余空白
    item = re.sub(r'\s+', '', item)

    # 13. 如果item为空，使用类别名
    if not item:
        item = category

    # 13. 报销类自动补全
    if item == "报销":
        item = "报销款"

    return item


def parse_input(user_input: str) -> dict:
    """
    解析用户输入，返回结构化记账数据
    返回: {
        "success": bool,
        "data": {record_date, member, type, category, item, amount} | None,
        "message": str,
        "missing": [str]
    }
    """
    text = user_input.strip()

    # 提取日期
    record_date, remaining = extract_date(text)

    # 提取成员
    member = extract_member(remaining)

    # 提取金额
    amount = extract_amount(text)  # 从原始文本提取，信息最完整

    # 提取收支类型
    type_ = detect_type(text)

    # 提取类别
    category = detect_category(text, type_)

    # 提取事项
    item = extract_item(remaining, category, member)

    # 构建数据
    data = {
        "record_date": record_date,
        "member": member,
        "type": type_,
        "category": category,
        "item": item,
        "amount": round(amount, 2) if amount is not None else None,
    }

    # 检查缺失字段
    missing = []
    if not data["member"]:
        missing.append("成员")
    if data["amount"] is None:
        missing.append("金额")

    result = {
        "success": len(missing) == 0,
        "data": data,
        "message": "",
        "missing": missing,
    }

    if missing:
        fields = "、".join(missing)
        result["message"] = f"信息不完整，缺少{fields}，请补充完整。"

    return result


if __name__ == "__main__":
    # 测试用例
    tests = [
        "今天女儿买了双登山鞋499元",
        "7月5日妈妈收到报销1000元",
        "三体花了50",
        "今天买了本书",
        "昨天爸爸吃饭花了80元",
        # 新增测试
        "女儿今天冲了一张流量卡 花了50元",
        "妈妈今天买菜花了20元",
        "女儿交50话费",
        "给女儿交了50话费",
        "老公今天iPhone花了8000",
        "妈妈买SKII花了1500",
        "昨天爸爸交了100话费",
        "女儿今天买了双鞋500",
        "今天女儿买了本三体30",
        "今天买菜20",
        "交了50话费",
        "充了一张流量卡",
    ]
    for t in tests:
        result = parse_input(t)
        d = result["data"]
        status = "✓" if result["success"] else f"✗ 缺{''.join(result['missing'])}"
        print(f"{status} | {t}")
        print(f"   成员={d['member']} 类别={d['category']} 事项={d['item']} 金额={d['amount']}")
