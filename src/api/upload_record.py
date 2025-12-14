from flask import Blueprint, request
from configs.logging_config import logger
from utils.common_utils import make_response, validate_request
from src.database.data_storage_manager import DataStorageManager

bp = Blueprint('upload_record', __name__)


@bp.route('/upload_record', methods=['POST'])
def upload_record():
    try:
        data = request.json
        request_video_ids = data.get('video_ids')
        request_type = data.get('type')
        wx_open_id = request.headers.get('WX-OPEN-ID', 'Guest')

        validation_result = validate_request(request_video_ids, request_type)
        if validation_result:
            # 如果验证不通过，则返回错误代码
            return validation_result

        user_id = DataStorageManager.get_or_create_user_id(wx_open_id)
        manager = DataStorageManager(user_id=user_id)

        if request_type == 'update':
            manager.add_record_list(user_id, request_video_ids)
            logger.debug(f'{wx_open_id} Update Records Success')
            return make_response(200, '成功', None, None, True), 200
        elif request_type == 'delete':
            manager.delete_record_list(user_id, request_video_ids)
            logger.debug(f'{wx_open_id} Delete Records Success')
            return make_response(200, '成功', None, None, True), 200
        else:
            logger.error(f'{wx_open_id} Update Or Delete Records Failed')
            return make_response(500, '失败', None, None, False), 500

    except Exception as e:
        logger.error(e)
        return make_response(500, '功能太火爆啦，请稍后再试', None, None, False), 500
