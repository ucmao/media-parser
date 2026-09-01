import os
from configs.logging_config import get_logger
from py_mini_racer._mini_racer import MiniRacer

logger = get_logger(__name__)


class AntiSigner:
    """拼多多 anti-content JS 签名与 Token 生成器。"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AntiSigner, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return

        self.user_agent = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/14.1.1 Mobile/15E148 Safari/604.1"
        )
        js_path = os.path.dirname(os.path.abspath(__file__))
        self.anti_content_js_path = os.path.join(js_path, 'anti_content.js')

        try:
            with open(self.anti_content_js_path, 'r', encoding='utf-8') as f:
                anti_code = f.read()

            setup_code = """
            var window = this;
            var self = this;
            var setTimeout = function(fn) {};
            var clearTimeout = function() {};
            var history = { back: function(){}, forward: function(){}, go: function(){}, length: 1 };
            function Element() {}
            function HTMLElement() {}
            function HTMLCanvasElement() {}
            function HTMLImageElement() {}
            var document = {
              referrer: 'https://mobile.yangkeduo.com/',
              documentElement: { clientWidth: 375, clientHeight: 667 },
              body: { clientWidth: 375, clientHeight: 667 },
              createElement: function() { return { getContext: function() { return null; } }; },
              getElementsByTagName: function() { return []; },
              addEventListener: function() {},
              removeEventListener: function() {}
            };
            var location = {
              href: 'https://mobile.yangkeduo.com/fyxmkief.html',
              origin: 'https://mobile.yangkeduo.com',
              protocol: 'https:',
              host: 'mobile.yangkeduo.com',
              hostname: 'mobile.yangkeduo.com',
              pathname: '/fyxmkief.html',
              search: '',
              hash: ''
            };
            var navigator = {
              userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
              appVersion: '5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
              platform: 'iPhone',
              language: 'zh-CN',
              languages: ['zh-CN', 'zh'],
              cookie: ''
            };
            var screen = { width: 375, height: 667, availWidth: 375, availHeight: 667, colorDepth: 24 };

            var exportFn;
            var __LOADABLE_LOADED_CHUNKS__ = {
              push: function(arr) {
                var mods = arr[1];
                if (mods && mods[53636]) {
                  var moduleObj = { exports: {} };
                  mods[53636](moduleObj);
                  exportFn = moduleObj.exports;
                }
              }
            };
            """

            self.ctx = MiniRacer()
            self.ctx.eval(setup_code)
            self.ctx.eval(anti_code)
            self.ctx.eval("""
            var crawler = new exportFn({ serverTime: Date.now(), _2827c887a48a351a: false });
            if (crawler && crawler.init) crawler.init();
            function getAntiContent() {
                if (!crawler || typeof crawler.messagePack !== 'function') return '';
                return crawler.messagePack();
            }
            """)
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize AntiSigner: {e}")
            self.ctx = None
            self._initialized = False

    def get_anti_content(self) -> str:
        """获取拼多多请求所需的 anti-content 签名 Token。"""
        if not self.ctx:
            return ""
        try:
            token = self.ctx.call('getAntiContent')
            return token or ""
        except Exception as e:
            logger.error(f"AntiSigner generate error: {e}")
            return ""
