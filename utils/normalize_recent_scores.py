import sys
import os
import mysql.connector
from datetime import datetime, timedelta

# --- 配置和路径设置（假设这里的导入路径是正确的） ---

# 确保项目根目录在Python路径中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 假设这个导入是成功的，并包含数据库配置
# 注意：此处的 DATABASE_CONFIG 变量必须存在于 configs.general_constants 模块中
try:
    from configs.general_constants import DATABASE_CONFIG
except ImportError:
    # 提供一个安全的默认配置，以防导入失败，实际使用时应替换为真实配置
    DATABASE_CONFIG = {
        'host': 'your_host',
        'user': 'your_user',
        'password': 'your_password',
        'database': 'your_db'
    }
    print("⚠️ 警告: 无法导入 configs.general_constants。使用默认配置。")


# --- 数据库连接函数 ---

def connect_to_database():
    """建立数据库连接并返回连接对象"""
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        return conn
    except Exception as e:
        # 失败时打印错误并重新抛出异常
        print(f"❌ 数据库连接失败: {e}")
        raise


# --- 🎯 修正后的更新函数：处理过去 24 小时内的数据 ---

def update_scores_in_last_24_hours(conn):
    """
    更新 parse_library 表中，创建时间在 '过去 24 小时内' 且 score > 100 的记录，
    将它们的 score 设为 50。
    """
    cursor = conn.cursor()

    # 统一设置会话时区为北京时间
    cursor.execute("SET time_zone = '+8:00'")

    # 获取当前数据库时间用于日志
    cursor.execute("SELECT NOW()")
    db_now = cursor.fetchone()[0]

    print(f"⏰ 当前数据库时间 (北京): {db_now}")
    print(f"🕒 正在执行更新。目标范围: 过去 24 小时内创建 且 score > 100")
    print("----------------------------------------")

    # 直接在 SQL 中使用 DATE_SUB(NOW(), INTERVAL 24 HOUR)
    # 确保 create_at 比较是基于数据库当前时间的，避免 Python 与数据库时钟不一致
    query = """
        UPDATE parse_library
        SET score = 50, updated_at = NOW()
        WHERE score > 100
        AND create_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
    """

    try:
        cursor.execute(query)

        affected_rows = cursor.rowcount
        conn.commit()  # 提交事务

        print(f"✅ 成功更新 {affected_rows} 条记录。")
        print(f"条件: create_at >= 24小时前 且 score > 100。")

    except mysql.connector.Error as e:
        # 捕获数据库错误，回滚并打印
        print(f"❌ 数据库更新错误: {e}")
        conn.rollback()
        raise
    except Exception as e:
        # 捕获其他错误，回滚并打印
        print(f"❌ 发生了其他错误: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()


# --- 主执行函数 ---

def execute_score_update():
    """主函数，调用数据库连接和分数更新操作"""
    conn = None
    try:
        conn = connect_to_database()
        update_scores_in_last_24_hours(conn)

    except Exception:
        # 捕获并处理所有异常，确保后续流程不会被中断，并且保证连接关闭
        # 详细错误已经在 update_scores_in_last_24_hours 内部打印
        pass

    finally:
        if conn and conn.is_connected():
            conn.close()
            print("🔗 数据库连接已关闭。")


# --- 调用执行函数 ---

if __name__ == '__main__':
    execute_score_update()