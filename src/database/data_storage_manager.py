from src.database.db_manager import DBManager
from configs.general_constants import DATABASE_CONFIG
from configs.logging_config import logger


class DataStorageManager:
    def __init__(self, video_id=None, real_url=None, user_id=None):
        self.video_id = video_id
        self.query_info = {
            'video_id': video_id,
            'real_url': real_url,
            'user_id': user_id
        }
        self.update_dict = {'video_id': video_id}

    @staticmethod
    def _connect_db():
        manager = DBManager(**DATABASE_CONFIG)
        manager.connect()
        return manager

    @staticmethod
    def _disconnect_db(manager):
        manager.disconnect()

    @staticmethod
    def get_or_create_user_id(wx_open_id):
        manager = DataStorageManager._connect_db()
        open_id = manager.get_or_create_user_id(wx_open_id)
        DataStorageManager._disconnect_db(manager)
        return open_id

    def get_db_data(self):
        manager = DataStorageManager._connect_db()
        try:
            dl_dict = manager.get_details_by_video_id(self.video_id, ['video_id', 'platform', 'title', 'video_url', 'cover_url', 'is_visible'])
            if dl_dict:
                # 如果视频被设置为隐藏，则返回 None，强制系统重新解析或提示
                if dl_dict.get('is_visible') == 0:
                    return None
                # 移除内部使用的字段再返回
                dl_dict.pop('is_visible', None)
                return dl_dict
            return None
        finally:
            DataStorageManager._disconnect_db(manager)

    def update_parse(self, data_dict):
        manager = DataStorageManager._connect_db()
        try:
            if data_dict.get('video_url'):
                self.update_dict.update(data_dict)
                manager.update_table_parse_library(**self.update_dict)
        finally:
            DataStorageManager._disconnect_db(manager)

    def update_parse_add_records(self, data_dict, user_id, video_id):
        manager = DataStorageManager._connect_db()
        try:
            if data_dict.get('video_url'):
                self.update_dict.update(data_dict)
                self.update_dict['last_user_id'] = user_id
                manager.update_table_parse_library(**self.update_dict)
                manager.add_video(user_id, video_id)
        finally:
            DataStorageManager._disconnect_db(manager)

    def upsert_parse_add_records(self, data_dict, user_id, video_id):
        manager = DataStorageManager._connect_db()
        try:
            if data_dict.get('video_url'):
                self.update_dict.update(data_dict)
                self.update_dict['last_user_id'] = user_id
                manager.upsert_table_parse_library(**self.update_dict)
                manager.add_video(user_id, video_id)
        finally:
            DataStorageManager._disconnect_db(manager)

    @staticmethod
    def add_record_list(user_id, video_ids):
        manager = DataStorageManager._connect_db()
        try:
            for video_id in video_ids:
                manager.add_video(user_id, video_id)
        finally:
            DataStorageManager._disconnect_db(manager)

    @staticmethod
    def delete_record_list(user_id, video_ids):
        manager = DataStorageManager._connect_db()
        try:
            for video_id in video_ids:
                manager.remove_video(user_id, video_id)
        finally:
            DataStorageManager._disconnect_db(manager)

    @staticmethod
    def batch_save_mysql(videos, request_searchquery, user_id):
        manager = DataStorageManager._connect_db()
        try:
            insert_data = []
            update_data = []
            query_log_data = []
            for video in videos:
                video_id = video.get('video_id')
                dl_dict = manager.get_details_by_video_id(video_id, ['platform', 'title', 'video_url', 'cover_url'])
                query_info = {
                    'video_id': video_id,
                    'keywords': request_searchquery,
                    'user_id': user_id
                }
                if dl_dict:
                    update_data.append(video)
                    query_log_data.append(query_info)
                else:
                    insert_data.append(video)
                    query_log_data.append(query_info)
            # 批量插入和更新
            if insert_data:
                manager.batch_insert_table_parse_library(insert_data)
            if update_data:
                manager.batch_update_table_parse_library(update_data)
        finally:
            DataStorageManager._disconnect_db(manager)

    def batch_add_score(self, video_ids: list, add_score: int) -> list:
        """
        对外暴露的“批量视频积分累加”接口（直接操作 parse_library 表）
        :param video_ids: 要累加积分的视频ID列表
        :param add_score: 本次累加的积分（正数）
        :return: 每个视频的处理结果列表
        """
        manager = self._connect_db()
        try:
            # 调用 DBManager 的批量视频积分累加方法
            return manager.batch_add_video_score(video_ids=video_ids, add_score=add_score)
        except Exception as e:
            logger.error(f"DataStorageManager 批量累加视频积分失败：{str(e)}", exc_info=True)
            # 返回全部失败的结果
            return [{'video_id': vid, 'added_score': 0, 'total_score': None, 'success': False} for vid in video_ids]
        finally:
            self._disconnect_db(manager)

    def add_score(self, video_id: str, add_score: int) -> bool:
        """
        对外暴露的“视频积分累加”接口（直接操作 parse_library 表）
        :param video_id: 要累加积分的视频ID
        :param add_score: 本次累加的积分（正数）
        :return: 成功返回 True，失败返回 False
        """
        manager = self._connect_db()
        try:
            # 调用 DBManager 的视频积分累加方法
            return manager.add_video_score(video_id=video_id, add_score=add_score)
        except Exception as e:
            logger.error(f"DataStorageManager 累加视频[{video_id}]积分失败：{str(e)}", exc_info=True)
            return False
        finally:
            self._disconnect_db(manager)

    # 可选：对外暴露“查询视频总积分”的接口
    def get_video_total_score(self, video_id: str) -> int:
        """查询指定视频的当前总热度积分"""
        manager = self._connect_db()
        try:
            return manager.get_video_total_score(video_id=video_id)
        except Exception as e:
            logger.error(f"查询视频[{video_id}]总积分失败：{str(e)}", exc_info=True)
            return 0
        finally:
            self._disconnect_db(manager)
