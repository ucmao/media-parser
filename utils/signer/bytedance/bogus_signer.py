import os
import urllib.parse
import random
from py_mini_racer._mini_racer import MiniRacer


class BogusSigner:
    """字节跳动 / 抖音系（a_bogus, x_bogus, ms_token）JS 签名与 Token 生成器。"""

    def __init__(self):
        self.user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/123.0.0.0 Safari/537.36'
        )

        js_path = os.path.dirname(os.path.abspath(__file__))
        self.x_bogus_js_path = os.path.join(js_path, 'x_bogus.js')
        self.a_bogus_js_path = os.path.join(js_path, 'a_bogus.js')

        with open(self.x_bogus_js_path, 'r', encoding='utf-8') as f:
            x_bogus_js_code = f.read()
        self.x_bogus_ctx = MiniRacer()
        self.x_bogus_ctx.eval(x_bogus_js_code)

        with open(self.a_bogus_js_path, 'r', encoding='utf-8') as f:
            a_bogus_js_code = f.read()
        self.a_bogus_ctx = MiniRacer()
        self.a_bogus_ctx.eval(a_bogus_js_code)

    def get_xbogus(self, req_url, user_agent):
        """生成 x_bogus 签名。"""
        query = urllib.parse.urlparse(req_url).query
        return self.x_bogus_ctx.call('sign', query, user_agent)

    def get_abogus(self, req_url, user_agent):
        """生成 a_bogus 签名。"""
        query = urllib.parse.urlparse(req_url).query
        return self.a_bogus_ctx.call('generate_a_bogus', query, user_agent)

    def get_ms_token(self, randomlength=107):
        """根据传入长度生成随机 ms_token 字符串。"""
        random_str = ''
        base_str = 'ABCDEFGHIGKLMNOPQRSTUVWXYZabcdefghigklmnopqrstuvwxyz0123456789='
        length = len(base_str) - 1
        for _ in range(randomlength):
            random_str += base_str[random.randint(0, length)]
        return random_str
