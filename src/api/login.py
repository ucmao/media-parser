import random
from flask import Blueprint, request, jsonify
import requests
from configs.logging_config import logger
from configs.general_constants import WECHAT_APP_ID, WECHAT_APP_SECRET, DOMAIN

bp = Blueprint('login', __name__)

def generate_random_nickname():
    """生成 3-5 个汉字的随机昵称"""
    # 精选常用美感汉字库
    chars = (
        "云深不知处月明风清晚秋初雪小桥流水暮色微光星辰大海青空漫步离人思语归途"
        "山川岁月人间烟火浮生若梦浅笑安然时光荏苒静谧清浅长风破浪锦瑟流年半夏微凉"
    )
    length = random.randint(3, 5)
    # 使用 random.choices 允许重复字，或者 random.sample 不允许重复字
    # 这里用 choices 因为字库较大且允许重复组合更有趣
    return "".join(random.choices(chars, k=length))

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
        if openid:
            from src.database.db_manager import DBManager
            from configs.general_constants import DATABASE_CONFIG
            
            db = DBManager(**DATABASE_CONFIG)
            db.connect()
            cursor = db.conn.cursor(dictionary=True)
            
            # 检查用户是否存在，并获取信息
            cursor.execute("SELECT nickname, avatar_url FROM users WHERE open_id = %s", (openid,))
            user = cursor.fetchone()
            
            if not user:
                # 如果是新用户，则生成随机信息并创建
                new_nickname = generate_random_nickname()
                # 处理 DOMAIN 可能自带协议的情况
                base_domain = DOMAIN.replace('https://', '').replace('http://', '')
                default_avatar = f"https://{base_domain}/static/images/default-avatar.png"
                
                cursor.execute(
                    "INSERT INTO users (open_id, nickname, avatar_url) VALUES (%s, %s, %s)", 
                    (openid, new_nickname, default_avatar)
                )
                db.conn.commit()
                user = {'nickname': new_nickname, 'avatar_url': default_avatar}
            
            db.disconnect()
            
            return jsonify({
                'openid': openid,
                'nickname': user.get('nickname'),
                'avatar_url': user.get('avatar_url')
            })
        else:
            logger.error('Failed to get openid')
            return jsonify({'error': 'Failed to get openid'}), 500
    else:
        logger.error('Failed to connect to WeChat server')
        return jsonify({'error': 'Failed to connect to WeChat server'}), 500
