from flask import Blueprint, request, jsonify
import requests
from configs.logging_config import logger
from configs.general_constants import WECHAT_APP_ID, WECHAT_APP_SECRET

bp = Blueprint('login', __name__)


@bp.route('/login', methods=['POST'])
def login():
    data = request.json
    code = data.get('code')
    if not code:
        return jsonify({'error': 'Missing code'}), 400
    url = 'https://api.weixin.qq.com/sns/jscode2session'
    params = {
        'appid': WECHAT_APP_ID,  # 你的 AppID
        'secret': WECHAT_APP_SECRET,  # 你的 AppSecret
        'js_code': code,
        'grant_type': 'authorization_code'
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        result = response.json()
        openid = result.get('openid')
        # session_key = result.get('session_key')
        if openid:
            return jsonify({'openid': openid})
        else:
            logger.error('Failed to get openid')
            return jsonify({'error': 'Failed to get openid'}), 500
    else:
        logger.error('Failed to connect to WeChat server')
        return jsonify({'error': 'Failed to connect to WeChat server'}), 500
