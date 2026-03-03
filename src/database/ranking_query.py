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
        # 衰减系数
        DECAY_K = 0.01

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
        explore_count = min(5, limit)
        main_limit = limit

        # 1. 主榜：直接在 SQL 中计算 effective_score
        # 公式：100 + (score * 10 / (1 + 发布至今的小时数 * 0.01)) + (video_id 末尾 ASCII 码 % 10)
        select_fields = f"""
            video_id, platform, title, video_url, cover_url, score as raw_score,
            FLOOR(100 + (score * 10 / (1 + TIMESTAMPDIFF(HOUR, create_at, NOW()) * {DECAY_K}))) + (ASCII(RIGHT(video_id, 1)) % 10) as effective_score,
            TIMESTAMPDIFF(HOUR, create_at, NOW()) as hours_age
        """

        if keywords:
            main_sql = f"""
            SELECT {select_fields}
            FROM parse_library
            WHERE {date_filter} AND title LIKE %s AND is_visible = 1
            ORDER BY effective_score DESC, create_at DESC
            LIMIT {main_limit}
            """
            self.cursor.execute(main_sql, (f"%{keywords}%",))
        else:
            main_sql = f"""
            SELECT {select_fields}
            FROM parse_library
            WHERE {date_filter} AND is_visible = 1
            ORDER BY effective_score DESC, create_at DESC
            LIMIT {main_limit}
            """
            self.cursor.execute(main_sql)

        main_results = self.cursor.fetchall()

        # 2. 探索位：同样计算 effective_score 以保持格式一致
        if explore_count > 0:
            if keywords:
                where_clause = f"WHERE {date_filter} AND title LIKE %s AND is_visible = 1"
                params = [f"%{keywords}%"]
            else:
                where_clause = f"WHERE {date_filter} AND is_visible = 1"
                params = []

            explore_sql = f"""
            SELECT {select_fields}
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
        else:
            explore_results = []

        # 3. 混合结果：逻辑与之前一致
        final_results_with_type = [] # 存储 (row, is_new)
        seen_ids = set()

        # 添加主榜前 3
        for i in range(min(3, len(main_results))):
            row = main_results[i]
            if row[0] not in seen_ids:
                final_results_with_type.append((row, False))
                seen_ids.add(row[0])

        # 添加探索位 (插队到 4-6 名)
        for row in explore_results:
            if len(final_results_with_type) >= 6:
                break
            if row[0] not in seen_ids:
                # 如果这个素材非常新（例如 24 小时内），则标记为新
                is_new_discovery = row[7] <= 24 
                final_results_with_type.append((row, is_new_discovery))
                seen_ids.add(row[0])

        # 填充剩余的主榜内容
        for row in main_results:
            if len(final_results_with_type) >= limit:
                break
            if row[0] not in seen_ids:
                final_results_with_type.append((row, False))
                seen_ids.add(row[0])
        
        # 4. 格式化结果：将 effective_score 映射给 query_count 供前端显示
        videos_info = []
        for row, is_new in final_results_with_type:
            videos_info.append({
                'video_id': row[0],
                'platform': PLATFORM_MAP.get(row[1], 'Unknown'),
                'title': row[2],
                'video_url': row[3],
                'cover_url': row[4],
                'query_count': int(row[6]),  # 使用衰减后的 effective_score
                'raw_score': row[5],         # 原始总分留底
                'is_new': is_new,            # 是否是新内容（用于前端显示 NEW 标签）
                'showItem': False
            })

        return videos_info

    def has_visible_videos(self):
        """全库是否存在任意一条 is_visible=1 的记录"""
        try:
            self.cursor.execute("SELECT 1 FROM parse_library WHERE is_visible = 1 LIMIT 1")
            return self.cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"has_visible_videos error: {e}")
            return False

    def get_recent_ranking(self, period='7days', keywords='', limit=100):
        # 映射前端传来的 period 到 get_recent_query_ranking 的参数
        PERIOD_MAPPING = {
            '7days': 7,
            '30days': 30,
            '90days': 90,
            '180days': 180,
            '365days': 365,
            'all': 'ALL',
            'today': 'TODAY',
            'yesterday': 'YESTERDAY'
        }
        
        days_param = PERIOD_MAPPING.get(period, 7)
        ranking_list = self.get_recent_query_ranking(days_param, keywords, limit)
        
        return {
            'search': keywords,
            'period': period,
            'list': ranking_list
        }
