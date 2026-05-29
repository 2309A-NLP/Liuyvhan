from __future__ import annotations
"""
拼角色提示词
"""
from models.schemas import RetrievedChunk, RoleProfile


COMMON_RESPONSE_RULES = """
通用回复规则：
- 优先回答用户当前这一轮的问题，不要机械重复上一轮答案。
- 如果用户一轮里问了多个问题，要拆开分别回答。
- 只有在检索知识确实相关时才引用；如果证据不足，要明确说明。
- 不要每轮都使用固定模板、冗长免责声明或空泛开场白。
- 回答重点要落在用户当前诉求上，而不是只介绍角色设定。
- 默认使用简体中文。除非用户明确要求，否则不要输出英文标题、中英混杂段落或英文术语堆砌。
- 不要输出 HTML 标签、调试信息、占位词或异常碎片，例如 `<br>`、`response`、`assistant`、`kuk`。
- 如果发现内容和当前问题不一致，要优先纠正当前回答，而不是继续扩写错误方向。
- 需要引用资料时，自然提到资料标题即可，不要原样堆砌大段原文。
""".strip()

SHORT_MEMORY_PREVIEW_CHARS = 180
LONG_MEMORY_PREVIEW_CHARS = 180
KNOWLEDGE_PREVIEW_CHARS = 220


def build_system_prompt(
    role: RoleProfile,
    user_message: str,
    short_memory: list[dict],
    long_memory: list[dict],
    references: list[RetrievedChunk],
) -> str:
    # system prompt 是整个 RAG 链路里最关键的“上下文打包点”：
    # 它把角色设定、用户当前问题、短期记忆、长期记忆和检索结果
    # 一次性组织成模型可读的输入背景。
    rules_block = "\n".join(f"- {rule}" for rule in role.system_rules) or "- 遵守角色边界。"
    short_memory_block = _format_short_memory(short_memory)
    long_memory_block = _format_long_memory(long_memory)
    knowledge_block = _format_knowledge(references)

    return f"""
你现在正在进行角色扮演式问答，请始终保持该角色身份，并优先解决用户当前这一轮的问题。

角色资料：
- 角色 ID：{role.role_id}
- 角色名称：{role.name}
- 角色领域：{role.domain}
- 角色描述：{role.description}
- 性格：{role.personality}
- 语气：{role.tone}

角色专属规则：
{rules_block}

当前用户问题：
{user_message}

最近短期记忆：
{short_memory_block}

相关长期记忆：
{long_memory_block}

当前命中的检索知识：
{knowledge_block}

额外要求：
- 当前用户问题的优先级高于历史记忆。
- 如果记忆不相关，就忽略，不要生硬套用。
- 如果检索知识无法直接回答问题，要明确说明缺少什么，不要假装证据充分。
- 优先给出直接回答，再给简短判断和可执行下一步。
- 保持角色语气，但清晰、自然、相关性比表演感更重要。
- 不要输出 HTML 标签、调试词、模板残片或异常英文碎片。

{COMMON_RESPONSE_RULES}
""".strip()


def _format_short_memory(short_memory: list[dict]) -> str:
    if not short_memory:
        return "- 暂无近期历史。"
    # 这里只截最近几条，避免 system prompt 无限制变长。
    return "\n".join(
        f"- {item.get('role', 'unknown')}: {_clip_text(item.get('content', ''), SHORT_MEMORY_PREVIEW_CHARS)}"
        for item in short_memory[-6:]
    )


def _format_long_memory(long_memory: list[dict]) -> str:
    if not long_memory:
        return "- 暂无相关长期记忆。"
    lines: list[str] = []
    for item in long_memory[:3]:
        content = _clip_text(item.get("content", ""), LONG_MEMORY_PREVIEW_CHARS)
        source = item.get("source", "memory")
        lines.append(f"- 来源：{source}；内容：{content}")
    return "\n".join(lines)


def _format_knowledge(references: list[RetrievedChunk]) -> str:
    if not references:
        return "- 本轮暂无命中知识。"
    # 检索结果不会原样整篇塞给模型，而是做成“标题 + 来源 + 分数 + 摘要”。
    return "\n".join(
        f"- 标题：{item.title}；来源：{item.source}；相关度：{item.score}；内容：{_clip_text(item.content, KNOWLEDGE_PREVIEW_CHARS)}"
        for item in references
    )


def _clip_text(text: str, limit: int) -> str:
    normalized = " ".join(str(text).split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."
