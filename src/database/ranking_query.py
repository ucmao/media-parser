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

        # 预留部分“探索位”给最新内容做保底曝光
        explore_count = min(5, limit)  # 每个榜单最多 5 条探索位
        main_limit = max(limit - explore_count, 0)

        results = []

        # 1. 主榜：在同一时间窗口内，对 score 做时间衰减排序
        if main_limit > 0:
            if keywords:
                main_sql = f"""
                SELECT video_id, platform, title, video_url, cover_url, score
                FROM parse_library
                WHERE {date_filter} AND title LIKE %s AND is_visible = 1
                ORDER BY score / (1 + TIMESTAMPDIFF(DAY, updated_at, NOW()) * 0.5) DESC, score DESC
                LIMIT {main_limit}
                """
                self.cursor.execute(main_sql, (f"%{keywords}%",))
            else:
                main_sql = f"""
                SELECT video_id, platform, title, video_url, cover_url, score
                FROM parse_library
                WHERE {date_filter} AND is_visible = 1
                ORDER BY score / (1 + TIMESTAMPDIFF(DAY, updated_at, NOW()) * 0.5) DESC, score DESC
                LIMIT {main_limit}
                """
                self.cursor.execute(main_sql)

            main_results = self.cursor.fetchall()
            results.extend(main_results)
        else:
            main_results = []

        # 2. 探索位：优先给“最新 create_at 的视频”保底曝光，排除已经在主榜中的视频
        if explore_count > 0:
            existing_ids = [row[0] for row in main_results]

            if keywords:
                where_clause = f"WHERE {date_filter} AND title LIKE %s AND is_visible = 1"
                params = [f"%{keywords}%"]
            else:
                where_clause = f"WHERE {date_filter} AND is_visible = 1"
                params = []

            if existing_ids:
                placeholders = ','.join(['%s'] * len(existing_ids))
                where_clause += f" AND video_id NOT IN ({placeholders})"
                params.extend(existing_ids)

            explore_sql = f"""
            SELECT video_id, platform, title, video_url, cover_url, score
            FROM parse_library
            {where_clause}
            ORDER BY create_at DESC
            LIMIT {explore_count}
            """
            if params:
                self.cursor.execute(explore_sql, tuple(params))
            else:
                self.cursor.execute(explore_sql)

            explore_results = self.cursor.fetchall()
            results.extend(explore_results)

        # 3. 格式化结果
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

    def has_visible_videos(self):
        """全库是否存在任意一条 is_visible=1 的记录（用于区分全站隐身与搜索无结果）"""
        try:
            self.cursor.execute("SELECT 1 FROM parse_library WHERE is_visible = 1 LIMIT 1")
            return self.cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"has_visible_videos error: {e}")
            return False

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
