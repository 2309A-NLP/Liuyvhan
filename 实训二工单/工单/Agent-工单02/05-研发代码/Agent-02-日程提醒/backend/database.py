"""
日程管家 - 数据库操作层
工单：人工智能 NLP-Agent 数字人项目-日程管家任务

强制规范：
- 所有日程操作必须调用数据库
- 字段：id, content, event_time, repeat_rule, created_at, status
- 每次操作记录日志（验收用）
"""

import datetime
import decimal
import logging
from typing import Any

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool

from config import SETTINGS

logger = logging.getLogger(__name__)

_pool: MySQLConnectionPool | None = None


def get_pool() -> MySQLConnectionPool:
    """获取数据库连接池（单例）"""
    global _pool
    if _pool is None:
        _pool = MySQLConnectionPool(
            pool_name="schedule_reminder_pool",
            pool_size=5,
            host=SETTINGS.mysql_host,
            port=SETTINGS.mysql_port,
            user=SETTINGS.mysql_user,
            password=SETTINGS.mysql_password,
            database=SETTINGS.mysql_database,
            charset=SETTINGS.mysql_charset,
        )
    return _pool


def init_database() -> None:
    """初始化数据库和 schedules 表"""
    # 先连接 mysql 实例（不指定 database）来创建 database
    conn = mysql.connector.connect(
        host=SETTINGS.mysql_host,
        port=SETTINGS.mysql_port,
        user=SETTINGS.mysql_user,
        password=SETTINGS.mysql_password,
        charset=SETTINGS.mysql_charset,
    )
    cursor = conn.cursor()
    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS `{SETTINGS.mysql_database}` "
        f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    cursor.execute(f"USE `{SETTINGS.mysql_database}`")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id          INT             AUTO_INCREMENT PRIMARY KEY COMMENT '日程编号',
            content     VARCHAR(500)    NOT NULL        COMMENT '日程事项内容',
            event_time  DATETIME        NOT NULL        COMMENT '提醒时间',
            repeat_rule VARCHAR(100)    DEFAULT ''      COMMENT '循环规则：每天/工作日/每周X/自定义/空(一次性)',
            status      VARCHAR(20)     DEFAULT 'active' COMMENT '状态：active(待提醒)/completed(已完成)/cancelled(已取消)',
            created_at  DATETIME        DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            INDEX idx_event_time (event_time),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='日程提醒表'
    """)
    conn.commit()
    cursor.close()
    conn.close()
    logger.info("✅ 数据库初始化完成: %s.schedules", SETTINGS.mysql_database)


# ============================================================
# 日程 CRUD（每次操作必须记录日志 — 验收要求）
# ============================================================

def add_schedule(content: str, event_time: str, repeat_rule: str = "") -> int:
    """新增一条日程记录，返回日程ID"""
    pool = get_pool()
    conn = pool.get_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO schedules (content, event_time, repeat_rule, status)
        VALUES (%s, %s, %s, 'active')
    """
    cursor.execute(sql, (content, event_time, repeat_rule))
    conn.commit()
    record_id = cursor.lastrowid
    cursor.close()
    conn.close()
    logger.info("📝 [DB] 新增日程 id=%s: %s | %s | 循环:%s",
                record_id, event_time, content, repeat_rule or "无")
    return record_id


def query_schedules(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """查询日程，支持按时间范围、状态筛选"""
    conditions: list[str] = ["1=1"]
    params: list[Any] = []

    if filters:
        if "date_from" in filters and filters["date_from"]:
            conditions.append("event_time >= %s")
            params.append(filters["date_from"])
        if "date_to" in filters and filters["date_to"]:
            conditions.append("event_time <= %s")
            params.append(filters["date_to"])
        if "status" in filters and filters["status"]:
            conditions.append("status = %s")
            params.append(filters["status"])
        if "content_like" in filters and filters["content_like"]:
            conditions.append("content LIKE %s")
            params.append(f"%{filters['content_like']}%")

    where_clause = " AND ".join(conditions)
    sql = f"SELECT * FROM schedules WHERE {where_clause} ORDER BY event_time ASC, id ASC"

    pool = get_pool()
    conn = pool.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    result = []
    for row in rows:
        item: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, datetime.datetime):
                item[key] = value.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(value, datetime.date):
                item[key] = value.isoformat()
            elif isinstance(value, decimal.Decimal):
                item[key] = float(value)
            else:
                item[key] = value
        result.append(item)

    logger.info("📝 [DB] 查询日程 %s => %d 条", filters or {}, len(result))
    return result


def delete_schedule(schedule_id: int) -> bool:
    """根据ID删除日程"""
    pool = get_pool()
    conn = pool.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM schedules WHERE id = %s", (schedule_id,))
    affected = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    logger.info("📝 [DB] 删除日程 id=%s, 影响行数=%d", schedule_id, affected)
    return affected > 0


def update_schedule(schedule_id: int, **kwargs: Any) -> bool:
    """更新日程字段（content, event_time, repeat_rule, status）"""
    allowed = {"content", "event_time", "repeat_rule", "status"}
    updates: list[str] = []
    params: list[Any] = []
    for key, value in kwargs.items():
        if key in allowed and value is not None:
            updates.append(f"{key} = %s")
            params.append(value)
    if not updates:
        return False
    params.append(schedule_id)
    sql = f"UPDATE schedules SET {', '.join(updates)} WHERE id = %s"
    pool = get_pool()
    conn = pool.get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, tuple(params))
    affected = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    logger.info("📝 [DB] 更新日程 id=%s: %s", schedule_id, kwargs)
    return affected > 0


def get_schedule_by_id(schedule_id: int) -> dict[str, Any] | None:
    """根据ID获取单条日程"""
    pool = get_pool()
    conn = pool.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM schedules WHERE id = %s", (schedule_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        item: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, datetime.datetime):
                item[key] = value.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(value, datetime.date):
                item[key] = value.isoformat()
            elif isinstance(value, decimal.Decimal):
                item[key] = float(value)
            else:
                item[key] = value
        return item
    return None


def get_due_schedules() -> list[dict[str, Any]]:
    """获取当前时间到期的 active 日程（前后1分钟窗口）"""
    now = datetime.datetime.now()
    due_start = (now - datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    due_end = (now + datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    pool = get_pool()
    conn = pool.get_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT * FROM schedules
        WHERE status = 'active'
          AND event_time >= %s
          AND event_time <= %s
        ORDER BY event_time ASC
    """
    cursor.execute(sql, (due_start, due_end))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    result = []
    for row in rows:
        item: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, datetime.datetime):
                item[key] = value.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(value, datetime.date):
                item[key] = value.isoformat()
            elif isinstance(value, decimal.Decimal):
                item[key] = float(value)
            else:
                item[key] = value
        result.append(item)

    if result:
        logger.info("📝 [DB] 到期提醒检查 => %d 条", len(result))
    return result
