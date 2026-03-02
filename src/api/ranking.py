from flask import Blueprint, request
from configs.logging_config import logger
from configs.general_constants import DATABASE_CONFIG
from src.database.ranking_query import RankingQuery
from src.database.db_manager import DBManager
from utils.common_utils import make_response, validate_request

bp = Blueprint('ranking', __name__)

# 榜单关闭时的空结构
_EMPTY_RANKING = {
    'search': '',
    'period': '7days',
    'list': []
}


def _is_ranking_enabled():
    """读取 app_config 中榜单总开关，表不存在或未配置时默认开启"""
    try:
        db = DBManager(**DATABASE_CONFIG)
        db.connect()
        cursor = db.conn.cursor(dictionary=True)
        cursor.execute("SELECT config_value FROM app_config WHERE config_key = 'ranking_enabled'")
        row = cursor.fetchone()
        db.disconnect()
        return row is None or row.get('config_value') == '1'
    except Exception as e:
        logger.debug(f"ranking_enabled check failed, default on: {e}")
        return True


@bp.route('/ranking', methods=['POST'])
def ranking():
    try:
        data = request.json
        request_searchquery = data.get('searchQuery')
        request_period = data.get('period', '7days') # 默认 7 天
        wx_open_id = request.headers.get('WX-OPEN-ID', 'Guest')

        validation_result = validate_request()
        if validation_result:
            return validation_result

        if not _is_ranking_enabled():
            ranking_dict = dict(_EMPTY_RANKING)
            ranking_dict['search'] = request_searchquery or ''
            ranking_dict['period'] = request_period
            ranking_dict['maintenance_mode'] = True
            return make_response(200, '成功', None, ranking_dict, True), 200

        sq = RankingQuery()
        try:
            ranking_dict = sq.get_recent_ranking(period=request_period, keywords=request_searchquery)
            ranking_dict['maintenance_mode'] = not sq.has_visible_videos()
        finally:
            sq.close()
            
        logger.debug(f'{wx_open_id} Ranking Success (Period: {request_period})')
        return make_response(200, '成功', None, ranking_dict, True), 200

    except Exception as e:
        logger.error(e)
        return make_response(500, '功能太火爆啦，请稍后再试', None, None, False), 500
