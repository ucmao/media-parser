import json
import sys
import os
import mysql.connector

# 确保项目根目录在Python路径中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 现在可以使用标准的import语句
from configs.general_constants import DATABASE_CONFIG


def connect_to_database():
    """建立数据库连接并返回连接对象"""
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        return conn
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        raise


def fetch_videos_with_empty_or_keyword_titles(conn, keywords):
    """从 parse_library 表中检索标题为空或包含指定关键词的视频记录"""
    cursor = conn.cursor(dictionary=True)
    try:
        # 构建包含多个关键词的 LIKE 条件
        like_conditions = " OR ".join(["title LIKE %s"] * len(keywords))

        # 直接在 SQL 查询中过滤数据
        query = f"""
            SELECT video_id 
            FROM parse_library 
            WHERE title IS NULL OR title = '' OR {like_conditions}
        """

        # 将关键词拼接为 SQL 的 LIKE 格式
        keyword_patterns = [f"%{keyword}%" for keyword in keywords]
        cursor.execute(query, keyword_patterns)
        rows = cursor.fetchall()

        # 提取 video_id
        video_ids_to_delete = {row['video_id'] for row in rows}
        return video_ids_to_delete
    except Exception as e:
        print(f"Error fetching videos: {e}")
        raise
    finally:
        cursor.close()


def delete_video_records(conn, video_ids):
    """从 parse_library 表中删除指定的 video_id 记录"""
    cursor = conn.cursor()
    try:
        # 删除 parse_library 表中的记录
        cursor.execute("DELETE FROM parse_library WHERE video_id IN ({})".format(','.join(['%s'] * len(video_ids))),
                       tuple(video_ids))
        print(f"Deleted {cursor.rowcount} records from parse_library table")
        conn.commit()  # 提交事务
    except Exception as e:
        print(f"Error deleting video records: {e}")
        conn.rollback()  # 回滚事务
        raise
    finally:
        cursor.close()


def update_users_video_records(conn, video_ids):
    """更新 users 表中的 video_records 字段，移除相关的 video_id"""
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id, video_records FROM users")
        users = cursor.fetchall()

        for user in users:
            user_id = user['user_id']
            video_records = user['video_records']

            if video_records:
                try:
                    video_records_dict = json.loads(video_records)
                    # 移除需要删除的 video_id
                    for video_id in video_ids:
                        video_records_dict.pop(video_id, None)

                    # 更新数据库
                    updated_video_records = json.dumps(video_records_dict)
                    cursor.execute(
                        "UPDATE users SET video_records = %s WHERE user_id = %s",
                        (updated_video_records, user_id)
                    )
                except json.JSONDecodeError:
                    print(f"Error decoding video_records for user {user_id}")
                    continue
        conn.commit()  # 提交事务
        print("Successfully updated users' video_records")
    except Exception as e:
        print(f"Error updating users' video_records: {e}")
        conn.rollback()  # 回滚事务
        raise
    finally:
        cursor.close()


def delete_videos_with_keywords(keywords_to_filter=None):
    """主函数，调用其他函数执行删除和更新操作"""
    # 如果没有提供关键词列表，则使用默认值
    if keywords_to_filter is None:
        keywords_to_filter = ["维权", "欺诈", "贪腐"]

    conn = None
    try:
        conn = connect_to_database()
        video_ids_to_delete = fetch_videos_with_empty_or_keyword_titles(conn, keywords_to_filter)

        if video_ids_to_delete:
            print(f"Found {len(video_ids_to_delete)} videos matching criteria to delete")
            # 删除记录并更新用户数据
            delete_video_records(conn, video_ids_to_delete)
            update_users_video_records(conn, video_ids_to_delete)

            for video_id in video_ids_to_delete:
                print(f"Deleted video_id {video_id} from parse_library and updated related records")
        else:
            print("No videos to delete.")
    except Exception as e:
        print(f"An error occurred: {e}")
        if conn:
            conn.rollback()  # 回滚事务
        raise  # 重新抛出异常，以便shell脚本能捕获错误
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    # 检查命令行参数
    if len(sys.argv) > 1:
        # 从命令行参数获取关键词，参数格式为用逗号分隔的关键词
        keywords_str = sys.argv[1]
        keywords_to_filter = [kw.strip() for kw in keywords_str.split(',')]
        delete_videos_with_keywords(keywords_to_filter)
    else:
        # 使用默认关键词列表
        delete_videos_with_keywords()
