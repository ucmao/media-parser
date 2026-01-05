import os
import uuid
from flask import Blueprint, request, jsonify
from configs.logging_config import logger
from src.database.userinfo_query import UserInfoQuery
from utils.common_utils import make_response, validate_request
from configs.general_constants import SAVE_AVATAR_PATH, DOMAIN

bp = Blueprint('upload_userinfo', __name__)


@bp.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '文件名为空'}), 400
        
        # 生成唯一文件名
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(SAVE_AVATAR_PATH, filename)
        
        file.save(filepath)
        
        # 构建永久访问 URL
        # 处理 DOMAIN 可能自带协议的情况
        base_domain = DOMAIN.replace('https://', '').replace('http://', '')
        url = f"https://{base_domain}/static/avatars/{filename}"
        
        return jsonify({
            'success': True,
            'url': url
        })
        
    except Exception as e:
        logger.error(f"Upload avatar error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


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
