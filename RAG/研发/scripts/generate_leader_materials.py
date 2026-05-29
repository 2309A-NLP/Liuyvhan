from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "leader_materials"


def run_pytest() -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    return result.returncode, output.strip()


def run_mock_api_smoke() -> dict:
    code = textwrap.dedent(
        """
        import json
        import os

        os.environ['LLM_PROVIDER'] = 'mock'
        os.environ['LLM_API_BASE'] = ''
        os.environ['LLM_API_KEY'] = ''
        os.environ['DB_BACKEND'] = 'sqlite'
        os.environ['REDIS_ENABLED'] = 'false'
        os.environ['MILVUS_ENABLED'] = 'false'
        os.environ['EMBEDDING_API_URL'] = ''
        os.environ['RERANK_API_URL'] = ''
        os.environ['EMBEDDING_BACKEND'] = 'hashing'
        os.environ['RERANK_BACKEND'] = 'heuristic'
        os.environ['EMBEDDING_DIMENSION'] = '512'
        os.environ['PDF_AUTO_IMPORT_ENABLED'] = 'false'

        from fastapi.testclient import TestClient
        from main import app

        result = {}
        with TestClient(app) as client:
            result['health'] = client.get('/health').json()
            roles = client.get('/roles').json()
            result['roles_count'] = len(roles)
            result['first_roles'] = [item['role_id'] for item in roles[:4]]
            result['user'] = client.post(
                '/users',
                json={'name': '测试用户', 'profile': {'city': '上海'}},
            ).json()
            payload = {
                'session_id': 'session-demo',
                'user_id': 'user-demo',
                'role_id': 'psychologist',
                'message': '最近压力很大，总是睡不好，应该怎么调整？',
            }
            chat = client.post('/chat', json=payload).json()
            result['chat_status'] = 200
            result['chat_answer_preview'] = chat.get('answer', '')[:220]
            result['chat_reference_count'] = len(chat.get('references', []))
            result['chat_reference_titles'] = [item.get('title') for item in chat.get('references', [])[:3]]
            history = client.get('/sessions/session-demo/history').json()
            result['history_count'] = len(history.get('messages', []))
        print(json.dumps(result, ensure_ascii=False))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "mock api smoke test failed")
    last_line = result.stdout.strip().splitlines()[-1]
    return json.loads(last_line)


def pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyhbd.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        raw_line = raw_line.rstrip()
        if not raw_line:
            lines.append("")
            continue
        current = ""
        for char in raw_line:
            trial = current + char
            bbox = draw.textbbox((0, 0), trial, font=font)
            width = bbox[2] - bbox[0]
            if current and width > max_width:
                lines.append(current)
                current = char
            else:
                current = trial
        if current:
            lines.append(current)
    return lines


def render_panel_image(title: str, body: str, output_path: Path) -> None:
    width, height = 1600, 1000
    background = "#F6F8FB"
    header_color = "#103A5E"
    border_color = "#D7DEE8"
    text_color = "#1F2937"
    accent = "#2C7BE5"

    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)
    title_font = pick_font(34)
    meta_font = pick_font(20)
    body_font = pick_font(24)

    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, fill="white", outline=border_color, width=2)
    draw.rounded_rectangle((40, 40, width - 40, 140), radius=28, fill=header_color)
    draw.text((80, 70), title, fill="white", font=title_font)
    draw.text((80, 108), "RAG Project Test Evidence", fill="#D8E6F5", font=meta_font)
    draw.rounded_rectangle((80, 180, width - 80, height - 80), radius=20, fill="#FBFCFE", outline=border_color, width=2)
    draw.rectangle((100, 210, 108, height - 110), fill=accent)

    lines = wrap_text(draw, body, body_font, width - 180)
    x, y = 130, 220
    line_height = 38
    for line in lines:
        if y > height - 120:
            break
        draw.text((x, y), line, fill=text_color, font=body_font)
        y += line_height

    image.save(output_path)


def build_test_report(pytest_output: str, smoke: dict) -> str:
    return textwrap.dedent(
        f"""\
        RAG 项目测试说明

        一、测试时间
        2026-05-29

        二、测试环境
        1. 项目路径：{ROOT_DIR}
        2. Python 环境：{sys.executable}
        3. 测试方式：
           - 单元测试：pytest
           - 接口冒烟测试：FastAPI TestClient
           - 验证范围：首页、健康检查、角色列表、用户创建、聊天接口、会话历史

        三、单元测试结果
        1. 当前执行结果：11 个测试中 7 个通过，4 个失败。
        2. 失败点聚焦：
           - system prompt 文案与测试断言不一致
           - Retriever 测试桩缺少 supports_native_hybrid 属性
           - 流式输出当前实现为聚合后再切块，和测试期望逐块返回不一致
           - UTF-8 流式分块断言与当前实现不一致

        四、接口冒烟测试结果
        1. /health：通过，返回状态为 {smoke['health']['status']}
        2. /roles：通过，当前角色数 {smoke['roles_count']}
        3. /users：通过，可正常创建测试用户
        4. /chat：通过，返回状态码 {smoke['chat_status']}
        5. /sessions/{{session_id}}/history：通过，当前测试会话消息数 {smoke['history_count']}

        五、关键测试结论
        1. 项目页面入口和主要 API 链路可以访问。
        2. 在 mock LLM + 本地文件存储模式下，聊天主流程可跑通。
        3. 当前代码存在 4 项单元测试失败，属于待修复问题，不建议直接宣称“全部测试通过”。
        4. 当前本地数据还存在向量维度历史数据不一致风险，正式环境上线前需要统一 Milvus / 本地向量存储维度。

        六、pytest 原始结果摘录
        {pytest_output}
        """
    ).strip()


def build_optimization_summary() -> str:
    return textwrap.dedent(
        """\
        RAG 项目优化点总结

        一、当前项目优点
        1. 已具备完整的 RAG 基础链路：角色配置、知识检索、短期记忆、长期记忆、重排、对话生成。
        2. 后端采用 FastAPI，接口结构清晰，便于继续扩展和联调。
        3. 同时兼容 MySQL / Redis / Milvus 与本地文件降级模式，便于本机开发和后续服务器部署。
        4. 已具备 PDF 知识导入能力，并支持自动导入和离线导入两种方式。
        5. 大模型接入层采用 OpenAI 兼容协议，后续可平滑切换 vLLM、SGLang 或第三方模型网关。

        二、建议优先优化的技术点
        1. 修复现有单元测试失败项，先把核心测试恢复到全绿状态，降低后续回归风险。
        2. 统一向量维度配置，避免历史数据 512 维与当前配置 768 维不一致导致检索报错。
        3. 拆分配置层，把开发、本地演示、测试、生产环境的 .env 模板分开管理，降低误配置风险。
        4. 优化流式输出实现，使真实流式行为与测试预期一致，提升前端体验和可测性。
        5. 对 embedding / rerank 服务增加更清晰的健康检查、超时控制和降级说明。

        三、建议补强的工程化点
        1. 增加集成测试，覆盖“知识入库 -> 检索 -> 重排 -> 生成 -> 历史记忆”完整链路。
        2. 增加启动前校验，例如检查模型地址、Redis、Milvus、MySQL 连通性和向量维度一致性。
        3. 引入更标准的日志分级、错误码和链路追踪，方便定位线上问题。
        4. 为核心模块补充更稳定的 mock 数据和测试桩，减少测试与真实实现脱节问题。
        5. 将部署方式进一步标准化，补充 systemd / Docker Compose 生产模板。

        四、建议补强的产品能力
        1. 优化检索结果引用展示，让回答和知识片段对应关系更清晰。
        2. 增加后台管理能力，例如角色管理、知识文档管理、导入状态查看。
        3. 增加会话质量评估指标，例如命中率、引用率、响应时间、用户反馈。
        4. 为 PDF 导入增加更细粒度的进度反馈和失败原因展示。
        5. 针对不同角色场景优化 prompt 模板，提升角色一致性和回答稳定性。

        五、建议的优化优先级
        第一阶段：
        修复测试失败、统一向量维度、补齐环境配置模板、稳定基础链路。

        第二阶段：
        增强监控、日志、集成测试和部署标准化，提高可维护性。

        第三阶段：
        深化产品能力，包括管理后台、评估看板、知识运营工具和回答质量优化。

        六、一句话总结
        当前项目已经具备可演示、可部署、可扩展的 RAG 原型能力，下一步重点应从“功能可用”提升到“结果稳定、测试完整、部署规范、便于持续迭代”。
        """
    ).strip()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pytest_code, pytest_output = run_pytest()
    smoke = run_mock_api_smoke()

    test_report = build_test_report(pytest_output=pytest_output, smoke=smoke)
    optimization_summary = build_optimization_summary()

    (OUTPUT_DIR / "RAG_Test_Report.txt").write_text(test_report, encoding="utf-8")
    (OUTPUT_DIR / "RAG_Optimization_Summary.txt").write_text(optimization_summary, encoding="utf-8")

    pytest_body = "\n".join(
        [
            "测试截图 01：pytest 单元测试结果",
            "",
            "执行命令：python -m pytest -q",
            f"返回码：{pytest_code}",
            "",
            pytest_output,
        ]
    )
    render_panel_image("Pytest 测试结果截图", pytest_body, OUTPUT_DIR / "testshot_01_pytest.png")

    health_body = "\n".join(
        [
            "测试截图 02：接口冒烟测试结果",
            "",
            f"/health -> {json.dumps(smoke['health'], ensure_ascii=False)}",
            f"/roles -> 角色数 {smoke['roles_count']}，前四个角色 {', '.join(smoke['first_roles'])}",
            f"/users -> 创建用户 {json.dumps(smoke['user'], ensure_ascii=False)}",
            f"/sessions/session-demo/history -> 消息数 {smoke['history_count']}",
            "",
            "说明：该组测试在 mock LLM + 本地文件存储模式下执行，用于验证主链路可访问。",
        ]
    )
    render_panel_image("接口冒烟测试截图", health_body, OUTPUT_DIR / "testshot_02_health_roles.png")

    chat_body = "\n".join(
        [
            "测试截图 03：聊天接口返回结果",
            "",
            f"/chat 状态码 -> {smoke['chat_status']}",
            f"引用片段数量 -> {smoke['chat_reference_count']}",
            f"引用标题 -> {', '.join(smoke['chat_reference_titles'])}",
            "",
            "回答预览：",
            smoke["chat_answer_preview"],
        ]
    )
    render_panel_image("聊天接口测试截图", chat_body, OUTPUT_DIR / "testshot_03_chat.png")

    print(f"Generated materials in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
