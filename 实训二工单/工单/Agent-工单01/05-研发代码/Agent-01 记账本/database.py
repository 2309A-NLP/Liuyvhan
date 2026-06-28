"""
数据库操作模块
工单编号：人工智能NLP-Agent数字人项目-01-记账本任务工单V1.1-20250206
"""

import pymysql
from datetime import date, datetime
from typing import Optional
from config import MYSQL_CONFIG


def get_connection():
    """获取数据库连接"""
    return pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)


def add_record(record_date: date, member: str, type_: str, category: str,
               item: str, amount: float) -> dict:
    """添加一条记账记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = """INSERT INTO money_notes
                     (record_date, member, type, category, item, amount)
                     VALUES (%s, %s, %s, %s, %s, %s)"""
            cur.execute(sql, (record_date, member, type_, category, item, amount))
            conn.commit()
            return {"id": cur.lastrowid, "success": True}
    finally:
        conn.close()


def search_records(keyword: str, member: Optional[str] = None) -> list:
    """按关键词搜索记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = """SELECT * FROM money_notes
                     WHERE item LIKE %s"""
            params = [f"%{keyword}%"]
            if member:
                sql += " AND member = %s"
                params.append(member)
            sql += " ORDER BY record_date DESC"
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def get_monthly_summary(year: int, month: int, member: Optional[str] = None,
                        category: Optional[str] = None) -> dict:
    """获取月度汇总"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = ["YEAR(record_date)=%s", "MONTH(record_date)=%s"]
            params = [year, month]

            if member:
                conditions.append("member=%s")
                params.append(member)
            if category:
                conditions.append("category=%s")
                params.append(category)

            where = " AND ".join(conditions)

            # 总收支统计
            sql = f"""SELECT type, COUNT(*) as count, SUM(amount) as total
                      FROM money_notes WHERE {where}
                      GROUP BY type"""
            cur.execute(sql, params)
            summary = cur.fetchall()

            # 详细记录
            sql2 = f"""SELECT * FROM money_notes WHERE {where}
                       ORDER BY record_date DESC"""
            cur.execute(sql2, params)
            records = cur.fetchall()

            return {"summary": summary, "records": records, "total_count": len(records)}
    finally:
        conn.close()


def get_monthly_detail(year: int, month: int) -> dict:
    """获取月度完整明细（按类别汇总）"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 按类别和成员汇总
            sql = """SELECT type, member, category,
                            COUNT(*) as count, SUM(amount) as total
                     FROM money_notes
                     WHERE YEAR(record_date)=%s AND MONTH(record_date)=%s
                     GROUP BY type, member, category
                     ORDER BY type, member, category"""
            cur.execute(sql, (year, month))
            grouped = cur.fetchall()

            # 逐条记录
            sql2 = """SELECT * FROM money_notes
                      WHERE YEAR(record_date)=%s AND MONTH(record_date)=%s
                      ORDER BY record_date ASC"""
            cur.execute(sql2, (year, month))
            records = cur.fetchall()

            return {"grouped": grouped, "records": records}
    finally:
        conn.close()


def delete_record(record_id: int) -> bool:
    """删除一条记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM money_notes WHERE id=%s", (record_id,))
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def delete_records_by_condition(member: str, category: str, keyword: str) -> list:
    """按条件查找待删除的记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = []
            params = []
            if member:
                conditions.append("member=%s")
                params.append(member)
            if category:
                conditions.append("category=%s")
                params.append(category)
            if keyword:
                conditions.append("(item LIKE %s OR category LIKE %s)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])

            where = " AND ".join(conditions) if conditions else "1=1"
            sql = f"SELECT * FROM money_notes WHERE {where} ORDER BY record_date DESC"
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def delete_records(ids: list) -> int:
    """批量删除记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(ids))
            sql = f"DELETE FROM money_notes WHERE id IN ({fmt})"
            cur.execute(sql, ids)
            conn.commit()
            return cur.rowcount
    finally:
        conn.close()


def update_record(record_id: int, record_date: date, member: str, type_: str,
                  category: str, item: str, amount: float) -> bool:
    """修改一条记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = """UPDATE money_notes SET
                     record_date=%s, member=%s, type=%s,
                     category=%s, item=%s, amount=%s
                     WHERE id=%s"""
            cur.execute(sql, (record_date, member, type_, category, item, amount, record_id))
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def get_record_by_id(record_id: int) -> dict:
    """通过ID获取单条记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM money_notes WHERE id=%s", (record_id,))
            return cur.fetchone()
    finally:
        conn.close()
