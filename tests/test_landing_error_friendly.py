import unittest
from app import app


class LandingErrorFriendlyTest(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()

    def test_landing_page_has_friendly_error_elements(self):
        """验证首页渲染包含结构化的友好错误卡片及操作组件"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        # 检查错误卡片核心 DOM 结构
        self.assertIn('id="errorState"', html)
        self.assertIn('id="errorTitle"', html)
        self.assertIn('id="errorMsg"', html)
        self.assertIn('id="errorHintBox"', html)
        self.assertIn('id="errorHint"', html)
        self.assertIn('id="errorTag"', html)

        # 检查快捷操作与示例填充按钮
        self.assertIn("fillSampleUrl()", html)
        self.assertIn("填入示例链接试一试", html)
        self.assertIn("清空重试", html)

    def test_landing_page_script_contains_error_formatting_and_masking(self):
        """验证首页脚本包含错误码友好转译与 Cookie 等运维黑话脱敏逻辑"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        # 检查转译函数与敏感信息脱敏逻辑
        self.assertIn("function formatUserErrorMessage(payload)", html)
        self.assertIn("function displayError(info)", html)
        self.assertIn("function fillSampleUrl()", html)
        self.assertIn("_COOKIE_REQUIRED", html)
        self.assertIn("目标平台在线体验受限", html)
        self.assertIn("未检测到有效链接", html)
        self.assertIn("建议尝试解析抖音、B站、快手等平台公开作品体验。", html)


if __name__ == "__main__":
    unittest.main()
