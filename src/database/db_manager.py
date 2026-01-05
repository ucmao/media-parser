import mysql.connector
from mysql.connector import MySQLConnection
from typing import Optional, List, Dict
from datetime import datetime
import json
from configs.logging_config import logger


class DBManager:
    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.conn: Optional[MySQLConnection] = None

    def connect(self):
        self.conn = mysql.connector.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            database=self.database,
            port=self.port
        )

    def disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def insert_table_parse_library(self, **kwargs):
        if not self.conn:
            raise Exception("Database not connected")

        # 获取列名和对应的值
        columns = ", ".join(kwargs.keys())
        placeholders = ", ".join(["%s"] * len(kwargs))
        values = list(kwargs.values())

        # 构建 SQL 语句
        sql = f'''
        INSERT INTO parse_library ({columns})
        VALUES ({placeholders})
        '''

        cursor = self.conn.cursor()
        cursor.execute(sql, values)
        self.conn.commit()

    def update_table_parse_library(self, **kwargs):
        if not self.conn:
            raise Exception("Database not connected")

        # 确保 video_id 存在
        video_id = kwargs.pop('video_id', None)
        if not video_id:
            raise ValueError("video_id is required")

        set_clause = ", ".join([f"{key} = %s" for key in kwargs.keys()])
        values = list(kwargs.values()) + [video_id]

        cursor = self.conn.cursor()
        cursor.execute(f'''
        UPDATE parse_library
        SET {set_clause}
        WHERE video_id = %s
        ''', values)
        self.conn.commit()

    def upsert_table_parse_library(self, **kwargs):
        if not self.conn:
            raise Exception("Database not connected")

        # 获取列名和对应的值
        columns = ", ".join(kwargs.keys())
        placeholders = ", ".join(["%s"] * len(kwargs))
        values = list(kwargs.values())

        # 构建 ON DUPLICATE KEY UPDATE 部分
        update_columns = ", ".join([f"{col} = VALUES({col})" for col in kwargs.keys()])

        # 构建 SQL 语句
        sql = f'''
        INSERT INTO parse_library ({columns})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_columns}
        '''

        cursor = self.conn.cursor()
        cursor.execute(sql, values)
        self.conn.commit()

    def insert_table_query_log(self, **kwargs):
        if not self.conn:
            raise Exception("Database not connected")

        # 获取列名和值
        columns = list(kwargs.keys())
        values = list(kwargs.values())

        # 构建插入语句
        placeholders = ", ".join(["%s"] * len(columns))
        columns_str = ", ".join(columns)
        query = f'''
        INSERT INTO user_query_log ({columns_str})
        VALUES ({placeholders})
        '''

        cursor = self.conn.cursor()
        cursor.execute(query, values)
        self.conn.commit()

    def get_details_by_video_id(self, video_id: str, fields: List[str]) -> Optional[Dict]:
        if not self.conn:
            raise Exception("Database not connected")

        if not fields:
            raise ValueError("Fields list cannot be empty")

        field_str = ", ".join(fields)
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute(f'''
        SELECT {field_str}
        FROM parse_library
        WHERE video_id = %s
        ''', (video_id,))
        result = cursor.fetchone()

        if result:
            return result
        else:
            return None

    def batch_insert_table_parse_library(self, data_list):
        if not self.conn:
            raise Exception("Database not connected")

        cursor = self.conn.cursor()
        for data in data_list:
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["%s"] * len(data))
            values = list(data.values())

            sql = f'''
            INSERT INTO parse_library ({columns})
            VALUES ({placeholders})
            '''
            cursor.execute(sql, values)
        self.conn.commit()

    def batch_update_table_parse_library(self, data_list):
        if not self.conn:
            raise Exception("Database not connected")

        cursor = self.conn.cursor()
        for data in data_list:
            video_id = data.pop('video_id', None)
            if not video_id:
                raise ValueError("video_id is required")

            set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
            values = list(data.values()) + [video_id]

            sql = f'''
            UPDATE parse_library
            SET {set_clause}
            WHERE video_id = %s
            '''
            cursor.execute(sql, values)
        self.conn.commit()

    def batch_insert_table_query_log(self, data_list):
        if not self.conn:
            raise Exception("Database not connected")

        cursor = self.conn.cursor()
        for data in data_list:
            columns = list(data.keys())
            values = list(data.values())

            placeholders = ", ".join(["%s"] * len(columns))
            columns_str = ", ".join(columns)
            query = f'''
            INSERT INTO user_query_log ({columns_str})
            VALUES ({placeholders})
            '''
            cursor.execute(query, values)
        self.conn.commit()

    def get_or_create_user_id(self, wx_open_id):
        if not self.conn:
            raise Exception("Database not connected")

        cursor = self.conn.cursor()

        # 查询用户
        query = "SELECT user_id FROM users WHERE open_id = %s"
        cursor.execute(query, (wx_open_id,))
        result = cursor.fetchone()

        if result:
            # 如果用户存在，返回 user_id
            user_id = result[0]
        else:
            # 如果用户不存在，创建新用户并返回 user_id
            insert_query = "INSERT INTO users (open_id) VALUES (%s)"
            cursor.execute(insert_query, (wx_open_id,))
            self.conn.commit()
            user_id = cursor.lastrowid

        return user_id

    def _get_video_data(self, user_id):
        """
        获取用户的 video_records 和 storageLimit。
        """
        if not self.conn:
            raise Exception("Database not connected")

        query = "SELECT video_records, permissions FROM users WHERE user_id = %s"
        cursor = self.conn.cursor()
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        video_records = json.loads(result[0]) if result and result[0] else {}
        permissions = json.loads(result[1]) if result and result[1] else {}
        return video_records, permissions.get('storageLimit', 100)

    def _update_video_data(self, user_id, video_data):
        """
        更新用户的 video_records。
        """
        if not self.conn:
            raise Exception("Database not connected")

        query = "UPDATE users SET video_records = %s WHERE user_id = %s"
        cursor = self.conn.cursor()
        logger.debug(json.dumps(video_data), user_id)
        cursor.execute(query, (json.dumps(video_data), user_id))
        self.conn.commit()

    def add_video(self, user_id, video_id):
        """
        添加 video_id 到用户的 video_records 中，并记录当前时间。
        如果 video_id 已经存在，则更新其时间。
        如果 video_records 数量超过上限，则移除最早的记录。
        """
        if not self.conn:
            raise Exception("Database not connected")

        video_data, limit = self._get_video_data(user_id)

        save_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        video_data[video_id] = save_time

        if len(video_data) > limit:
            # 移除最早的记录
            oldest_video_id = min(video_data, key=video_data.get)
            del video_data[oldest_video_id]

        self._update_video_data(user_id, video_data)

    def remove_video(self, user_id, video_id):
        """
        从用户的 video_records 中删除指定的 video_id。
        """
        if not self.conn:
            raise Exception("Database not connected")

        video_data, _ = self._get_video_data(user_id)

        if video_id not in video_data:
            raise ValueError(f"video_id {video_id} 不存在")

        del video_data[video_id]
        self._update_video_data(user_id, video_data)

    def batch_add_video_score(self, video_ids: list, add_score: int) -> list:
        """
        批量给指定视频累加热度积分（更新 parse_library 表的 score 字段）
        :param video_ids: 视频ID列表（parse_library 表的主键/唯一键）
        :param add_score: 本次要累加的积分（正数）
        :return: 每个视频的处理结果列表
        """
        if not self.conn:
            raise Exception("Database not connected")
        if add_score <= 0:
            raise ValueError("Add score must be a positive integer")  # 确保积分是正数累加
        if not video_ids or not isinstance(video_ids, list):
            raise ValueError("video_ids must be a non-empty list")

        cursor = self.conn.cursor()
        try:
            # 1. 批量更新积分
            placeholders = ', '.join(['%s'] * len(video_ids))
            update_sql = f'''
                UPDATE parse_library 
                SET score = score + %s 
                WHERE video_id IN ({placeholders})
            '''
            
            # 执行更新
            params = [add_score] + video_ids
            cursor.execute(update_sql, params)
            self.conn.commit()
            
            # 2. 获取所有视频的最新积分
            select_sql = f'''
                SELECT video_id, score 
                FROM parse_library 
                WHERE video_id IN ({placeholders})
            '''
            cursor.execute(select_sql, video_ids)
            results = cursor.fetchall()
            
            # 构建结果字典，便于查找
            score_dict = {row[0]: row[1] for row in results}
            
            # 3. 生成每个视频的处理结果
            video_results = []
            for video_id in video_ids:
                if video_id in score_dict:
                    video_results.append({
                        'video_id': video_id,
                        'added_score': add_score,
                        'total_score': score_dict[video_id],
                        'success': True
                    })
                    logger.debug(f"视频[{video_id}]积分累加成功，本次+{add_score}分")
                else:
                    video_results.append({
                        'video_id': video_id,
                        'added_score': 0,
                        'total_score': None,
                        'success': False
                    })
                    logger.warning(f"视频[{video_id}]不存在，积分累加失败")
            
            return video_results

        except Exception as e:
            self.conn.rollback()
            logger.error(f"批量视频积分累加失败：{str(e)}", exc_info=True)
            raise e  # 抛异常让上层处理
        finally:
            cursor.close()

    def add_video_score(self, video_id: str, add_score: int) -> bool:
        """
        给指定视频累加热度积分（直接更新 parse_library 表的 score 字段）
        :param video_id: 视频ID（parse_library 表的主键/唯一键）
        :param add_score: 本次要累加的积分（正数，如分享+8分、解析+10分）
        :return: 累加成功返回 True，失败返回 False
        """
        if not self.conn:
            raise Exception("Database not connected")
        if add_score <= 0:
            raise ValueError("Add score must be a positive integer")  # 确保积分是正数累加

        cursor = self.conn.cursor()
        try:
            # 核心逻辑：按 video_id 找到视频，给 score 字段累加 add_score
            update_sql = '''
                UPDATE parse_library 
                SET score = score + %s 
                WHERE video_id = %s
            '''
            # 执行更新并获取“受影响的行数”（判断视频是否存在）
            cursor.execute(update_sql, (add_score, video_id))
            affected_rows = cursor.rowcount

            if affected_rows == 0:
                # 若视频不存在（无受影响行数），可选择“不处理”或“抛异常”，这里按“不处理”设计
                logger.warning(f"视频[{video_id}]不存在，积分累加失败")
                return False

            self.conn.commit()
            logger.debug(f"视频[{video_id}]积分累加成功，本次+{add_score}分")
            return True

        except Exception as e:
            self.conn.rollback()
            logger.error(f"视频[{video_id}]积分累加失败：{str(e)}", exc_info=True)
            raise e  # 抛异常让上层处理
        finally:
            cursor.close()

    # 可选：新增查询视频当前总积分的方法（方便后续查看）
    def get_video_total_score(self, video_id: str) -> int:
        """查询指定视频的当前总热度积分"""
        if not self.conn:
            raise Exception("Database not connected")

        cursor = self.conn.cursor()
        try:
            query_sql = '''
                SELECT score 
                FROM parse_library 
                WHERE video_id = %s
            '''
            cursor.execute(query_sql, (video_id,))
            result = cursor.fetchone()
            return result[0] if result else 0  # 视频不存在返回 0
        finally:
            cursor.close()


if __name__ == '__main__':
    # 示例调用
    db_manager = DBManager(host='your_host', user='your_user', password='your_password', database='your_database')
    db_manager.connect()

    wx_open_id = 'example_open_id'
    user_id = db_manager.get_or_create_user_id(wx_open_id)
    print(f'User ID: {user_id}')

    # 添加 video_id
    db_manager.add_video(wx_open_id, 'video_id_1')
    print("video_id 添加成功")

    # 再次添加相同的 video_id，更新时间
    db_manager.add_video(wx_open_id, 'video_id_1')
    print("video_id 更新成功")

    # 删除 video_id
    db_manager.remove_video(wx_open_id, 'video_id_1')
    print("video_id 删除成功")

    db_manager.disconnect()
