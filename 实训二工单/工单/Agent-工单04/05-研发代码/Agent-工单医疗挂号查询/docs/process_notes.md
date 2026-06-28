# 实现过程记录

1. 先搭建 FastAPI + SQLAlchemy + SQLite 基础骨架。
2. 将 Agent 设计为“只调用工具，不直接碰数据库”。
3. 工具内部转调 `DoctorService`、`SlotService`、`RegistrationService`。
4. 使用 `seed_data.py` 构造覆盖 6 个核心案例的最小业务数据。
5. 以 pytest 覆盖核心场景和 30+ 变体场景。
