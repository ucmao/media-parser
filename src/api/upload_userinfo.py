from flask import Blueprint, request
from configs.logging_config import logger
from src.database.userinfo_query import UserInfoQuery
from utils.common_utils import make_response, validate_request

bp = Blueprint('upload_userinfo', __name__)


@bp.route('/upload_userinfo', methods=['POST'])
def upload_userinfo():
    try:
        data = request.json
        request_userinfo = data.get('userInfo', '')
        request_permissions = data.get('permissions', '')
        wx_open_id = request.headers.get('WX-OPEN-ID', 'Guest')

        validation_result = validate_request()
        if validation_result:
            # 如果验证不通过，则返回错误代码
            return validation_result

        user_query = UserInfoQuery()
        if request_userinfo:
            user_query.update_user_info(wx_open_id, request_userinfo)
        success, permissions = user_query.compare_and_update_permissions(wx_open_id, request_permissions)
        user_query.close()
        if success:
            logger.debug(f"{wx_open_id} Permissions Update Success")
            return make_response(200, '权限更新成功', {'permissions': permissions}, None, True), 200
        else:
            logger.error(f"{wx_open_id} Permissions Update Failed")
            return make_response(500, '权限更新失败', None, None, False), 500

    except Exception as e:
        logger.error(e)
        return make_response(500, '功能太火爆啦，请稍后再试', None, None, False), 500
