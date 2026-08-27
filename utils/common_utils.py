from flask import jsonify


def make_response(retcode, retdesc, data, succ, error_code=None):
    """生成统一响应；失败时可提供供调用方判断的稳定错误码。"""
    response = {
        'retcode': retcode,
        'retdesc': retdesc,
        'data': data,
        'succ': succ
    }
    if error_code:
        response['error_code'] = error_code
    return jsonify(response)
