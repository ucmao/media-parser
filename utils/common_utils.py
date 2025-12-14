from flask import jsonify, request
from configs.logging_config import logger
from utils.vigenere_cipher import VigenereCipher
import time


def make_response(retcode, retdesc, data, ranking, succ):
    # 生成统一的响应格式
    return jsonify({
        'retcode': retcode,
        'retdesc': retdesc,
        'data': data,
        'ranking': ranking,
        'succ': succ
    })


def validate_timestamp(request_timestamp):
    # 验证时间戳是否在合理的时间窗口内
    current_timestamp = int(time.time() * 1000)  # 获取当前时间戳（毫秒）
    time_window = 5 * 60 * 1000  # 5分钟的时间窗口
    return abs(current_timestamp - request_timestamp) <= time_window


def validate_request(*args):
    x_timestamp = request.headers.get('X-Timestamp', '')
    x_gclt_text = request.headers.get('X-GCLT-Text', '')
    x_egct_text = request.headers.get('X-EGCT-Text', '')

    # 检查是否有缺失的参数
    missing_params = [param for param in args if not param]
    if missing_params:
        # 如果有缺失的参数，记录日志并返回400错误
        missing_param_names = ', '.join(missing_params)
        logger.error(f'Missing {missing_param_names} in request')
        return make_response(400, f'Missing {missing_param_names} in request', None, None, False), 400

    if not x_timestamp:
        logger.error('Missing timestamp in request')
        return make_response(400, 'Missing timestamp in request', None, None, False), 400

    if not validate_timestamp(int(x_timestamp)):
        logger.error('Invalid timestamp')
        return make_response(400, 'Invalid timestamp', None, None, False), 400

    if not VigenereCipher(x_timestamp).verify_decryption(x_egct_text, x_gclt_text):
        logger.error('Decryption verification failed')
        return make_response(400, 'Decryption verification failed', None, None, False), 400

    return None
