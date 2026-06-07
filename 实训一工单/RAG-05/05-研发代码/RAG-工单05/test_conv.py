"""快速验证多轮对话支持"""
import sys
sys.path.insert(0, r'C:\Users\刘禹含\Desktop\RAG-工单05')

from app.services.conversation_store import ConversationStore

cs = ConversationStore(max_history=10, ttl_seconds=3600)

# 模拟3轮对话
cs.add_turn("test-001", "他参与的哪个工程荣获了国家科技进步一等奖？", "某视频指挥工程")
cs.add_turn("test-001", "这个公司的法定代表人是谁？", "程家明")
cs.add_turn("test-001", "那武汉力源信息技术股份有限公司呢？")  # 答案还未生成

h = cs.get_history("test-001")
print(f"历史条数: {len(h)}")
for i, turn in enumerate(h):
    print(f"  第{i+1}轮: Q={turn['question'][:40]}... A={turn.get('answer','')[:30]}")

# 更新最后一轮的答案
cs.update_last_answer("test-001", "赵马克")
h = cs.get_history("test-001")
print(f"更新后最后一轮答案: {h[-1]['answer']}")

# 测试 import 完整性
from app.services.query_enhancer_service import QueryEnhancerService
print("QueryEnhancerService import OK")
print("ALL OK")
