from __future__ import annotations
"""PDF 文本清洗  PDF 文本清洗，把页码、页眉页脚、噪音行这些内容去掉"""
import math
import re
from collections import Counter


_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SPACE_RE = re.compile(r"[ \t]+")
_PAGE_NUMBER_RE = re.compile(r"^(?:page\s*)?\d+\s*(?:/|of)?\s*\d*$", re.IGNORECASE)
_NOISE_LINE_RE = re.compile(
    r"^(?:www\.|https?://|第\s*\d+\s*页|页码|版权所有|内部资料|仅供参考).*$",
    re.IGNORECASE,
)
"""
re.compile() 是把正则表达式“编译”成一个可复用的对象
"""
"""
拓展
match()：从字符串开头开始匹配
search()：在整个字符串里找第一个匹配
fullmatch()：要求整个字符串完全匹配
sub()：替换匹配到的内容
"""



"""
先做基础标准化，把换行统一、去掉控制字符、压缩多余空格、合并过多空行，得到更规整的文本
"""
def normalize_pdf_text(text: str) -> str:
    normalized = str(text or "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
    #                       把 \r\n 替换成 \n                 再把 \r 替换成 \n                 再把 \ufeff 替换成空字符串 ""，也就是删掉它
    # \r 是“回车符”（carriage return）
    # 它本身不是换行，而是把光标移回行首。
    # 常见组合是
    # \n：换行
    # \r\n：Windows 的换行
    # \r：老式 Mac/某些文本里的回车
    # 所以你代码里先把 \r\n 和 \r 都统一成 \n
    normalized = _CONTROL_RE.sub("", normalized)  # 检查normalized把匹配到的这些字符  全部替换成空字符串 相当于删除它们
    normalized = "\n".join(_SPACE_RE.sub(" ", line).strip() for line in normalized.split("\n"))
    # _SPACE_RE.sub(" ", line)  将多个空格压缩一个空格
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    # 这一步是在压缩过多空行。
    # 正则 r"\n{3,}" 表示：
    # 连续出现 3 次及以上的换行
    # 把它替换成 "\n\n"，也就是最多保留一个空白段
    return normalized.strip()


"""
扫描多页文本，找出经常重复出现的页眉、页脚、页码这类“页级噪音”，返回一个需要删除的字符串集合
"""
def discover_repeated_page_artifacts(page_texts: list[str], *, sample_lines: int = 2) -> set[str]:
    #  sample_lines: int = 2 --- sample_lines: int = 2
    # * --- 表示 sample_lines 只能用关键字传参，比如 sample_lines=3
    if len(page_texts) < 2:  # 如果只有 1 页，就没法判断“重复内容”，所以直接返回空集合
        return set()

    candidates: list[str] = [] # 准备一个候选列表，用来收集每页最可能是页眉/页脚的内容
    for text in page_texts:    # 逐页处理文本
        lines = [line.strip() for line in normalize_pdf_text(text).split("\n") if line.strip()]
        #        过滤掉空行                 先用 normalize_pdf_text(text) 标准化文本   再按行切开  去掉每行首尾空格
        if not lines:
            continue
        candidates.extend(lines[:sample_lines])  # 取前两行
        candidates.extend(lines[-sample_lines:]) # 后前两行

    threshold = max(2, math.ceil(len(page_texts) * 0.6))  #“重复判定阈值” ：一行内容如果在至少 60% 的页面里都出现，就认为它是重复噪音。
    # 例如 ：10 页文档，阈值是 ceil(10 * 0.6) = 6
    counter = Counter(line for line in candidates if _is_repeatable_artifact(line))
    # 统计 _is_repeatable_artifact(line) 认为“有可能是重复噪音”的行  放进空列表

    return {line for line, count in counter.items() if count >= threshold} # 包含内容：出现次数 >= threshold 且被认为是可重复噪音的行


"""
对单页文本做最终清洗，删除重复噪音、页码、疑似水印、连续重复行，并整理空行
"""
def clean_pdf_page_text(text: str, repeated_artifacts: set[str] | None = None) -> str:
    #  text：一页原始文本   repeated_artifacts：前面扫描出来的“重复噪音行”集合   返回：清洗后的文本
    normalized = normalize_pdf_text(text)  # 先做基础标准化，统一换行、空格、删除控制字符。
    if not normalized:                     # 如果清洗后还是空文本，直接返回空字符串。
        return ""

    repeated_artifacts = repeated_artifacts or set()
    cleaned_lines: list[str] = []          # 准备保存清洗后的结果；previous 用来去掉连续重复行
    previous = ""
    for raw_line in normalized.split("\n"):# 按行处理文本
        line = raw_line.strip()
        if not line:         # 作用；遇到空行时，只保留一个空行占位，不让连续空行太多
            if cleaned_lines and cleaned_lines[-1] != "":  # 保存“清洗后保留下来的行”的列表
                cleaned_lines.append("")                   # 往列表里加一个空字符串，表示一个空行
            continue
        if line in repeated_artifacts:  # 如果这一行是前面识别出的重复页眉/页脚/页码，直接删掉
            continue
        if _looks_like_noise(line):     # 如果这一行本身就像噪音，比如网址、页码、版权声明，也删掉。
            continue
        if line == previous:            # 如果和上一行完全一样，说明是重复内容，删掉
            continue
        cleaned_lines.append(line)      # 保留当前行，并更新“上一行”记录
        previous = line

    joined = "\n".join(cleaned_lines)
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined.strip()

"""
判断某一行是不是“可能会在很多页重复出现的垃圾内容”，比如页码、短噪音行
"""
def _is_repeatable_artifact(line: str) -> bool:
    compact = line.strip()  # 先去掉首尾空格
    if not compact:         # 空行不算
        return False
    if len(compact) > 80:   # 太长的行通常不像页眉页脚，直接排除
        return False
    return _looks_like_noise(compact) or len(compact) <= 40
    # 如果它本身就像噪音，就算
    # 或者它很短，长度不超过 40，也可能是页码、标题、水印，所以也算


"""
 判断一行是否像噪音，例如网址、页码、“版权所有”、“内部资料”、大量下划线或横线等。
"""
def _looks_like_noise(line: str) -> bool:
    compact = line.strip()
    if not compact:
        return True
    if _PAGE_NUMBER_RE.fullmatch(compact):
        return True
    if _NOISE_LINE_RE.fullmatch(compact):
        return True
    if compact.count("_") >= 4 or compact.count("-") >= 8:
        return True
    return False
