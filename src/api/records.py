from flask import Blueprint, request
from configs.logging_config import logger
from src.database.records_query import RecordsQuery
from utils.common_utils import make_response, validate_request

bp = Blueprint('records', __name__)


@bp.route('/records', methods=['POST'])
def records():
    try:
        data = request.json
        request_searchquery = data.get('searchQuery')
        wx_open_id = request.headers.get('WX-OPEN-ID', 'Guest')

        validation_result = validate_request()
        if validation_result:
            # 如果验证不通过，则返回错误代码
            return validation_result

        rq = RecordsQuery()
        records_dict = rq.get_recent_records(open_id=wx_open_id, keywords=request_searchquery)
        logger.debug(f'{wx_open_id} Records Success')
        return make_response(200, '成功', None, records_dict, True), 200

    except Exception as e:
        logger.error(e)
        return make_response(500, '功能太火爆啦，请稍后再试', None, None, False), 500
