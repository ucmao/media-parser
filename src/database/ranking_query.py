import mysql.connector
from configs.general_constants import DATABASE_CONFIG, PLATFORM_MAP
from configs.logging_config import logger


class RankingQuery:
    def __init__(self):
        try:
            self.conn = mysql.connector.connect(**DATABASE_CONFIG)
            self.cursor = self.conn.cursor()
            logger.debug("数据库连接成功")
        except Exception as e:
            logger.error(f"数据库连接失败: {str(e)}")
            raise

    def close(self):
        if hasattr(self, 'conn') and self.conn.is_connected():
            self.cursor.close()
            self.conn.close()
            logger.debug("数据库连接已关闭")

    def get_recent_query_ranking(self, days, keywords='', limit=100):
        # 使用实际存在的 create_at 字段进行时间筛选
        if days == 'MONTH':
            date_filter = "DATE_FORMAT(create_at, '%Y-%m') = DATE_FORMAT(CURRENT_DATE, '%Y-%m')"
        elif days == 'LAST_MONTH':
            date_filter = "DATE_FORMAT(create_at, '%Y-%m') = DATE_FORMAT(DATE_SUB(CURRENT_DATE, INTERVAL 1 MONTH), '%Y-%m')"
        elif days == 'ALL':
            date_filter = "1=1"  # 不筛选时间
        elif days == 'TODAY':
            date_filter = "DATE(create_at) = CURRENT_DATE"
        elif days == 'YESTERDAY':
            date_filter = "DATE(create_at) = DATE_SUB(CURRENT_DATE, INTERVAL 1 DAY)"
        else:
            date_filter = f"create_at >= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL {days} DAY)"

        # 构建查询语句
        if keywords:
            query = f"""
            SELECT video_id, platform, title, video_url, cover_url, score
            FROM parse_library
            WHERE {date_filter} AND title LIKE %s AND is_visible = 1
            ORDER BY score DESC
            LIMIT {limit}
            """
            self.cursor.execute(query, (f"%{keywords}%",))
        else:
            query = f"""
            SELECT video_id, platform, title, video_url, cover_url, score
            FROM parse_library
            WHERE {date_filter} AND is_visible = 1
            ORDER BY score DESC
            LIMIT {limit}
            """
            self.cursor.execute(query)
        
        results = self.cursor.fetchall()

        # 格式化结果
        videos_info = []
        for row in results:
            videos_info.append({
                'video_id': row[0],
                'platform': PLATFORM_MAP.get(row[1], 'Unknown'),
                'title': row[2],
                'video_url': row[3],
                'cover_url': row[4],
                'query_count': row[5],  # 直接使用score作为热度值
                'showItem': False
            })

        return videos_info

    def get_recent_ranking(self, keywords='', limit=100):
        return {
            'search': keywords,
            # 'today': self.get_recent_query_ranking('TODAY', keywords, limit),
            # 'yesterday': self.get_recent_query_ranking('YESTERDAY', keywords, limit),
            '7days': self.get_recent_query_ranking(7, keywords, limit),
            '30days': self.get_recent_query_ranking(30, keywords, limit),
            # '60days': self.get_recent_query_ranking(60, keywords, limit),
            '90days': self.get_recent_query_ranking(90, keywords, limit),
            '180days': self.get_recent_query_ranking(180, keywords, limit),
            '365days': self.get_recent_query_ranking(365, keywords, limit),
            # 'thisMonth': self.get_recent_query_ranking('MONTH', keywords, limit),
            # 'lastMonth': self.get_recent_query_ranking('LAST_MONTH', keywords, limit),
            'all': self.get_recent_query_ranking('ALL', keywords, limit),
        }
