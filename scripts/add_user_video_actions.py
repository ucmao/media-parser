# scripts/add_user_video_actions.py
"""
为已有数据库添加 user_video_actions 表（用户-视频-行为去重日志）。
依赖项目里的 DATABASE_CONFIG，确保在 parse-ucmao-backend 根目录下运行：
    python scripts/add_user_video_actions.py
"""

import mysql.connector
from mysql.connector import errorcode

from configs.general_constants import DATABASE_CONFIG
from configs.logging_config import logger


DDL_SQL = """
CREATE TABLE IF NOT EXISTS `user_video_actions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `user_id` int(11) NOT NULL COMMENT '用户ID，对应 users.user_id',
  `video_id` varchar(50) COLLATE utf8mb4_general_ci NOT NULL COMMENT '视频ID，对应 parse_library.video_id',
  `action_type` varchar(50) COLLATE utf8mb4_general_ci NOT NULL COMMENT '行为类型，如 parse、shareFriend 等',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '行为发生时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_user_video_action` (`user_id`, `video_id`, `action_type'),
  KEY `idx_video_action` (`video_id`, `action_type`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_general_ci
  COMMENT='用户-视频-行为去重日志表';
"""


def main():
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SET NAMES utf8mb4")
        cursor.execute(DDL_SQL)
        conn.commit()
        print("✅ user_video_actions 表迁移完成（已存在则忽略）。")
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("❌ 数据库账号或密码错误，请检查 DATABASE_CONFIG")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("❌ 数据库不存在，请先创建数据库")
        else:
            print(f"❌ 执行迁移时出错: {err}")
        logger.error(f"add_user_video_actions migration failed: {err}", exc_info=True)
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()