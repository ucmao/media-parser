from flask import jsonify


def make_response(retcode, retdesc, data, succ):
    # 生成统一的响应格式
    return jsonify({
        'retcode': retcode,
        'retdesc': retdesc,
        'data': data,
        'succ': succ
    })
