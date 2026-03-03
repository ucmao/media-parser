import mysql.connector
import json
from datetime import datetime, timedelta
from configs.general_constants import DATABASE_CONFIG, PLATFORM_MAP
from configs.logging_config import logger


class RecordsQuery:
    def __init__(self):
        self.conn = mysql.connector.connect(**DATABASE_CONFIG)
        self.cursor = self.conn.cursor()
        # 统一设置会话时区为北京时间
        self.cursor.execute("SET time_zone = '+8:00'")

    def close(self):
        self.conn.close()

    def _get_video_data(self, open_id):
        """
        获取用户的 video_records，并按 save_time 倒序排序。
        """
        query = "SELECT video_records FROM users WHERE open_id = %s"
        self.cursor.execute(query, (open_id,))
        result = self.cursor.fetchone()

        if result and result[0]:
            video_records = json.loads(result[0])
            # 按 save_time 倒序排序
            sorted_video_records = dict(sorted(video_records.items(), key=lambda item: item[1], reverse=True))
            return sorted_video_records
        else:
            return {}

    def _filter_videos_by_date(self, video_data, days):
        """
        根据 days 参数过滤 video_records。
        """
        filtered_videos = {}
        current_time = datetime.now()

        for video_id, save_time in video_data.items():
            save_time = datetime.strptime(save_time, '%Y-%m-%d %H:%M:%S')
            if days == 'TODAY':
                if save_time.date() == current_time.date():
                    filtered_videos[video_id] = save_time
            elif days == 'YESTERDAY':
                if save_time.date() == (current_time - timedelta(days=1)).date():
                    filtered_videos[video_id] = save_time
            elif days == 'MONTH':
                if save_time.month == current_time.month and save_time.year == current_time.year:
                    filtered_videos[video_id] = save_time
            elif days == 'LAST_MONTH':
                last_month = current_time - timedelta(days=30)
                if save_time.month == last_month.month and save_time.year == last_month.year:
                    filtered_videos[video_id] = save_time
            elif days == 'ALL':
                filtered_videos[video_id] = save_time
            else:
                if save_time >= current_time - timedelta(days=days):
                    filtered_videos[video_id] = save_time

        return filtered_videos

    def query_videos(self, open_id, days, keywords='', limit=100):
        """
        查询用户的 video_records，并按照时间从近到远排序。
        同时查询每个 video_id 对应的 title、video_url、cover_url 和 platform。
        支持关键词搜索和日期限制。
        """
        video_data = self._get_video_data(open_id)
        filtered_videos = self._filter_videos_by_date(video_data, days)

        # 构建 SQL 查询语句
        if not filtered_videos:
            return []

        query = f"""
        SELECT 
            pl.video_id,
            pl.title, 
            pl.video_url, 
            pl.cover_url,
            pl.platform,
            pl.score
        FROM 
            parse_library pl
        WHERE 
            pl.video_id IN ({', '.join(['%s'] * len(filtered_videos))})
            AND pl.is_visible = 1
        """
        params = list(filtered_videos.keys())

        if keywords:
            query += " AND pl.title LIKE %s"
            params.append(f"%{keywords}%")

        query += " ORDER BY FIELD(pl.video_id, " + ', '.join(['%s'] * len(filtered_videos)) + ")"
        params.extend(filtered_videos.keys())

        self.cursor.execute(query, params)
        results = self.cursor.fetchall()

        videos_info = []
        for row in results:
            video_id = row[0]  # 提取 video_id
            if video_id in filtered_videos:
                videos_info.append({
                    'video_id': video_id,
                    'save_time': filtered_videos[video_id].strftime('%Y-%m-%d %H:%M'),
                    'title': row[1],  # 提取 title
                    'video_url': row[2],  # 提取 video_url
                    'cover_url': row[3],  # 提取 cover_url
                    'platform': PLATFORM_MAP.get(row[4], 'Unknown'),  # 提取 platform
                    'heat': row[5],  # 提取原始 score
                    'showItem': False
                })
            else:
                logger.error(f"Video ID not found in filtered_videos: {video_id}")

        return videos_info

    def get_recent_records(self, open_id='', period='all', keywords='', limit=100):
        # 映射前端传来的 period 到 query_videos 的参数
        PERIOD_MAPPING = {
            'today': 'TODAY',
            'yesterday': 'YESTERDAY',
            '7days': 7,
            '30days': 30,
            '60days': 60,
            '90days': 90,
            '180days': 180,
            '365days': 365,
            'thisMonth': 'MONTH',
            'lastMonth': 'LAST_MONTH',
            'all': 'ALL'
        }
        
        days_param = PERIOD_MAPPING.get(period, 'ALL')
        records_list = self.query_videos(open_id, days_param, keywords, limit)
        
        return {
            'length': len(self._get_video_data(open_id)),
            'search': keywords,
            'period': period,
            'list': records_list
        }


# 示例用法
if __name__ == "__main__":
    records_query = RecordsQuery()
    try:
        result = records_query.get_recent_records('user_open_id', 'example', 50)
        print(result)
    finally:
        records_query.close()
