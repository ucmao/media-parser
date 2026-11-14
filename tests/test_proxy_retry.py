"""代理窗口、跨进程协调、失败重试与请求预算的确定性回归。"""

import json
import multiprocessing
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

import requests

from app import create_app
from src.api.parse import _execute_parse
from src.utils.parser_transport import (
    Attempt, ParseFailure, ParserSession, ProxyAccessFailure, attempt_context, current_attempt,
)
from src.utils.proxy_manager import ProxyAddress, ProxyManager


def activate_worker(database):
    manager = ProxyManager(database, 'http://provider.invalid')
    manager.activate('快手')


def replenish_worker(database, api_url, event):
    manager = ProxyManager(database, api_url)
    event.wait(10)
    manager.replenish(time.monotonic() + 5)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def payload(ip='114.106.134.52', remain=49):
    return {'code': 200, 'data': {'count': 1, 'surplus_quantity': 0, 'proxy_list': [
        {'ip': ip, 'port': 35152, 'ip_remain': remain, 'city_code': '341700', 'city_name': '安徽|池州'}
    ]}}


class ManagerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = os.path.join(self.temp.name, 'proxy.db')
        self.manager = ProxyManager(self.database, 'http://provider.invalid')
        self.clock = Clock()
        self.patches = [patch('time.time', self.clock.time), patch('time.monotonic', self.clock.time)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def supply(self, ip='114.106.134.52', remain=49):
        session = Mock()
        session.get.return_value.json.return_value = payload(ip, remain)
        with patch('src.utils.proxy_manager.requests.Session') as factory:
            factory.return_value.__enter__.return_value = session
            called = self.manager.replenish(self.clock.now + 5)
        return called, session

    def test_json2_remaining_and_zero_surplus(self):
        proxy = self.manager.decode(payload(), 998)
        self.assertEqual(proxy.address, '114.106.134.52:35152')
        self.assertEqual(proxy.expires_at, 1047)
        self.assertEqual(proxy.url, 'http://114.106.134.52:35152')
        for remain in (None, 0, 9, 'bad', float('nan'), float('inf')):
            with self.subTest(remain=remain), self.assertRaises((ValueError, TypeError)):
                self.manager.decode(payload(remain=remain), 1000)

    def test_window_does_not_extend_and_other_platform_is_direct(self):
        self.manager.activate('快手')
        self.clock.now = 1100
        self.manager.activate('快手')
        with self.manager.connection() as db:
            self.assertEqual(db.execute('SELECT until_at FROM proxy_platform_windows').fetchone()[0], 1900)
        self.assertTrue(self.manager.active('快手'))
        self.assertFalse(self.manager.active('抖音'))
        self.clock.now = 1900
        self.assertFalse(self.manager.active('快手'))
        self.manager.activate('快手')
        self.assertTrue(self.manager.active('快手'))

    def test_prefetch_retirement_and_inflight_validity(self):
        self.manager.activate('快手')
        called, session = self.supply()
        self.assertTrue(called)
        self.assertFalse(session.trust_env)
        first = self.manager.available()
        self.clock.now += 1
        self.supply('114.106.134.53')
        self.assertFalse(self.supply('114.106.134.54')[0])
        self.clock.now = 1030
        self.assertTrue(self.supply('114.106.134.54')[0])
        self.assertNotEqual(self.manager.available().address, first.address)
        self.assertTrue(self.manager.valid(first))
        self.clock.now = 1049
        self.assertFalse(self.manager.valid(first))

    def test_invalid_address_shared_and_duplicate_does_not_revive(self):
        self.supply()
        proxy = self.manager.available()
        other = ProxyManager(self.database, self.manager.api_url)
        other.invalidate(proxy, '访问失败')
        self.assertFalse(self.manager.valid(proxy))
        self.assertIsNone(self.manager.available())
        self.clock.now += 1
        self.supply()
        self.assertIsNone(self.manager.available())

    def test_maintenance_idle_and_inflight_use(self):
        with patch.object(self.manager, 'replenish') as replenish:
            self.manager.maintain_once()
            replenish.assert_not_called()
            self.manager.activate('快手')
            self.manager.maintain_once()
            self.assertEqual(replenish.call_count, 1)
            self.clock.now = 1899
            token = self.manager.begin_use(90)
            self.clock.now = 1901
            self.manager.maintain_once()
            self.assertEqual(replenish.call_count, 2)
            self.manager.end_use(token)
            self.manager.maintain_once()
            self.assertEqual(replenish.call_count, 2)

    def test_lease_takeover_and_extraction_frequency(self):
        with self.manager.connection(write=True) as db:
            db.execute("UPDATE proxy_coordination SET owner='dead', lease_until=1008, next_fetch=1001")
        self.assertFalse(self.supply()[0])
        self.clock.now = 1008
        self.assertTrue(self.supply()[0])
        self.assertFalse(self.supply('114.106.134.53')[0])
        self.clock.now += 1
        self.assertTrue(self.supply('114.106.134.53')[0])

    def test_supplier_failure_backoff(self):
        session = Mock()
        session.get.side_effect = requests.Timeout()
        with patch('src.utils.proxy_manager.requests.Session') as factory:
            factory.return_value.__enter__.return_value = session
            for delay in (1, 2, 4, 8, 15, 15):
                self.assertTrue(self.manager.replenish(self.clock.now + 5))
                with self.manager.connection() as db:
                    next_fetch = db.execute('SELECT next_fetch FROM proxy_coordination').fetchone()[0]
                self.assertEqual(next_fetch, self.clock.now + delay)
                self.assertFalse(self.manager.replenish(self.clock.now + 5))
                self.clock.now = next_fetch


class ProcessCoordinationTest(unittest.TestCase):
    def test_two_processes_share_window(self):
        with tempfile.TemporaryDirectory() as temp:
            database = os.path.join(temp, 'shared.db')
            manager = ProxyManager(database, 'http://provider.invalid')
            context = multiprocessing.get_context('spawn')
            processes = [context.Process(target=activate_worker, args=(database,)) for _ in range(2)]
            for process in processes:
                process.start()
            for process in processes:
                process.join(15)
                self.assertEqual(process.exitcode, 0)
            self.assertTrue(manager.active('快手'))
            with manager.connection() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM proxy_platform_windows').fetchone()[0], 1)

    def test_two_processes_only_extract_once(self):
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append(time.monotonic())
                time.sleep(0.2)
                data = json.dumps(payload()).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with tempfile.TemporaryDirectory() as temp:
                    database = os.path.join(temp, 'shared.db')
                    api_url = f'http://127.0.0.1:{server.server_port}'
                    ProxyManager(database, api_url)
                    context = multiprocessing.get_context('spawn')
                    event = context.Event()
                    processes = [context.Process(target=replenish_worker, args=(database, api_url, event)) for _ in range(2)]
                    for process in processes:
                        process.start()
                    event.set()
                    for process in processes:
                        process.join(15)
                        self.assertEqual(process.exitcode, 0)
                    self.assertEqual(len(calls), 1)
            finally:
                server.shutdown()
                thread.join()


def fake_parser(kind='success'):
    parser = Mock()
    parser.terminal_error = None
    parser.no_media_in_content = False
    parser.cookie_required = kind == 'cookie'
    parser.get_title_content.return_value = '测试标题'
    parser.get_description.return_value = None
    parser.get_real_video_url.return_value = 'https://cdn.example/video.mp4' if kind == 'success' else None
    parser.get_video_list.return_value = []
    parser.get_image_list.return_value = []
    parser.get_cover_photo_url.return_value = None
    parser.get_author_info.return_value = None
    parser.get_audio_url.return_value = None
    parser.get_subtitles.return_value = None
    if kind == 'cookie':
        parser.terminal_error = {'error_code': 'KUAISHOU_COOKIE_REQUIRED', 'detail_msg': '需要 Cookie'}
    if kind == 'deleted':
        parser.terminal_error = {'detail_msg': '内容已删除'}
    if kind == 'text':
        parser.no_media_in_content = True
    return parser


class RetryIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({'TESTING': True, 'API_ONLY': True, 'SECRET_KEY': 'test',
                               'DATABASE': os.path.join(self.temp.name, 'test.db'),
                               'DYNAMIC_PROXY_API_URL': 'http://provider.invalid'})
        self.manager = self.app.extensions['proxy_manager']
        self.client = self.app.test_client()
        self.url = 'https://v.kuaishou.com/test'
        self.clock = Clock()
        for target, value in [('time.time', self.clock.time), ('time.monotonic', self.clock.time),
                              ('src.api.parse.time.sleep', self.clock.sleep)]:
            item = patch(target, value)
            item.start()
            self.addCleanup(item.stop)
        item = patch('src.api.parse.WebFetcher.fetch_redirect_url', return_value=self.url)
        self.redirect = item.start()
        self.addCleanup(item.stop)
        self.sessions = []

    def supply(self):
        session = Mock()
        index = len(self.sessions) + 1
        session.get.return_value.json.return_value = payload(f'114.106.134.{index}', 300)
        self.sessions.append(session)
        return session

    def parse(self, parsers):
        with patch('src.api.parse.ParserFactory.create_parser', side_effect=parsers) as factory:
            with patch('src.utils.proxy_manager.requests.Session') as sessions:
                sessions.return_value.__enter__.side_effect = self.supply
                response = self.client.get('/api/v1/parse', query_string={'url': self.url})
        return response, factory

    def test_direct_success_does_not_fetch_proxy(self):
        response, factory = self.parse([fake_parser()])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.sessions), 0)
        self.assertFalse(self.manager.active('快手'))
        self.assertEqual(factory.call_count, 1)

    def test_cookie_retry_recreates_parser_and_redirect(self):
        seen = []

        def build(*args):
            seen.append(current_attempt().proxy)
            return fake_parser('cookie' if len(seen) == 1 else 'success')

        with patch('src.api.parse.platform_access', return_value=None) as access:
            response, factory = self.parse(build)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(seen[0])
        self.assertIsNotNone(seen[1])
        self.assertTrue(self.manager.active('快手'))
        self.assertEqual(self.redirect.call_count, 2)
        self.assertEqual(factory.call_count, 2)
        access.assert_called_once_with('快手')

    def test_three_cookie_failures_keep_cookie_error(self):
        response, factory = self.parse([fake_parser('cookie') for _ in range(4)])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error_code'], 'KUAISHOU_COOKIE_REQUIRED')
        self.assertEqual(factory.call_count, 4)
        self.assertEqual(len(self.sessions), 3)
        self.assertIsNone(self.manager.available())

    def test_three_network_failures_exhaust(self):
        self.manager.activate('快手')

        def fail(*args):
            current_attempt().fail_proxy('网络异常')

        response, factory = self.parse(fail)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json['error_code'], 'PROXY_RETRY_EXHAUSTED')
        self.assertEqual(factory.call_count, 3)

    def test_swallowed_network_failure_still_rotates(self):
        self.manager.activate('快手')

        def build(*args):
            if len(self.sessions) == 1:
                try:
                    current_attempt().fail_proxy('网络异常')
                except requests.RequestException:
                    pass
                return fake_parser('empty')
            return fake_parser()

        response, _ = self.parse(build)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.sessions), 2)

    def test_content_and_plain_empty_do_not_discard_proxy(self):
        self.manager.activate('快手')
        for kind in ('deleted', 'text', 'empty'):
            with self.subTest(kind=kind):
                response, _ = self.parse([fake_parser(kind)])
                self.assertEqual(response.status_code, 400)
                self.assertIsNotNone(self.manager.available())
        self.assertEqual(len(self.sessions), 1)

    def test_expired_window_restores_direct(self):
        self.manager.activate('快手')
        self.clock.now += 900
        response, _ = self.parse([fake_parser()])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.sessions), 0)

    def test_supplier_failure_has_three_call_limit(self):
        self.manager.activate('快手')
        with patch('src.utils.proxy_manager.requests.Session') as sessions:
            sessions.return_value.__enter__.return_value.get.side_effect = requests.Timeout()
            response = self.client.get('/api/v1/parse', query_string={'url': self.url})
            self.assertEqual(sessions.return_value.__enter__.return_value.get.call_count, 3)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['error_code'], 'PROXY_UNAVAILABLE')
        self.assertTrue(self.manager.active('快手'))

    def test_budget_stops_even_if_parser_returns_success(self):
        def build(*args):
            self.clock.now += 91
            return fake_parser()

        response, _ = self.parse(build)
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json['error_code'], 'PARSE_TIMEOUT')

    def test_credit_and_request_log_happen_once(self):
        with self.app.test_request_context('/api/v1/parse'):
            with patch('src.api.parse.reserve_user_credit', return_value=True) as reserve, \
                    patch('src.api.parse.refund_user_credit') as refund, \
                    patch('src.api.parse.record_request') as record, \
                    patch('src.api.parse.ParserFactory.create_parser', side_effect=[fake_parser('cookie'), fake_parser()]), \
                    patch('src.utils.proxy_manager.requests.Session') as sessions:
                sessions.return_value.__enter__.side_effect = self.supply
                _, status = _execute_parse(self.url, {'user_id': 123})
        self.assertEqual(status, 200)
        reserve.assert_called_once_with(123)
        refund.assert_not_called()
        record.assert_called_once()

    def test_failure_refunds_credit_and_logs_only_once(self):
        with self.app.test_request_context('/api/v1/parse'):
            with patch('src.api.parse.reserve_user_credit', return_value=True) as reserve, \
                    patch('src.api.parse.refund_user_credit') as refund, \
                    patch('src.api.parse.record_request') as record, \
                    patch('src.api.parse.ParserFactory.create_parser', side_effect=[fake_parser('cookie') for _ in range(4)]), \
                    patch('src.utils.proxy_manager.requests.Session') as sessions:
                sessions.return_value.__enter__.side_effect = self.supply
                _, status = _execute_parse(self.url, {'user_id': 123})
        self.assertEqual(status, 400)
        reserve.assert_called_once_with(123)
        refund.assert_called_once_with(123)
        record.assert_called_once()

    def test_second_request_uses_proxy_from_first_network_step(self):
        self.manager.activate('快手')
        seen = []

        def redirect(url):
            seen.append(current_attempt().proxy)
            return url

        self.redirect.side_effect = redirect
        for _ in range(2):
            response, _ = self.parse([fake_parser()])
            self.assertEqual(response.status_code, 200)
        self.assertTrue(all(seen))
        self.assertEqual(seen[0].address, seen[1].address)
        self.assertEqual(len(self.sessions), 1)

    def test_other_platform_stays_direct(self):
        self.manager.activate('快手')
        self.url = 'https://www.douyin.com/video/123'
        self.redirect.return_value = self.url
        response, _ = self.parse([fake_parser()])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.sessions), 0)

    def test_xhs_cookie_detail_keeps_cookie_code(self):
        self.url = 'https://www.xiaohongshu.com/explore/123'
        self.redirect.return_value = self.url
        parsers = []
        for _ in range(4):
            parser = fake_parser('empty')
            parser.terminal_error = {'detail_msg': '小红书 Cookie 凭据可能已失效或访问受限，请在后台更新'}
            parsers.append(parser)
        response, _ = self.parse(parsers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error_code'], 'XIAOHONGSHU_COOKIE_REQUIRED')
        self.assertEqual(len(self.sessions), 3)

    def test_cookie_challenge_in_constructor_rotates_immediately(self):
        from src.utils.parser_transport import report_cookie_required
        self.manager.activate('快手')

        def build(*args):
            report_cookie_required()
            self.fail('代理 Cookie 拦截后不应继续解析')

        response, factory = self.parse(build)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error_code'], 'KUAISHOU_COOKIE_REQUIRED')
        self.assertEqual(factory.call_count, 3)

    def test_universal_decoders(self):
        start = time.time()
        # 1. 巨量 IP (Juliang)
        p1 = ProxyManager.decode({'code': 200, 'data': {'proxy_list': [{'ip': '1.2.3.4', 'port': 8080, 'ip_remain': 120}]}}, start)
        self.assertEqual(p1.address, '1.2.3.4:8080')
        self.assertAlmostEqual(p1.expires_at - start, 120, delta=1)

        # 2. 芝麻代理 (Zhima)
        p2 = ProxyManager.decode({'code': 0, 'data': [{'ip': '5.6.7.8', 'port': 9090, 'expire_time': '2026-09-30 20:00:00'}]}, start)
        self.assertEqual(p2.address, '5.6.7.8:9090')

        # 3. 青果网络 (Qingguo)
        p3 = ProxyManager.decode({'code': 'SUCCESS', 'data': [{'ip': '9.10.11.12', 'port': 7070, 'ttl': 300}]}, start)
        self.assertEqual(p3.address, '9.10.11.12:7070')

        # 4. Data5U / 无忧代理
        p4 = ProxyManager.decode({'success': True, 'data': [{'ip': '13.14.15.16', 'port': 6060}]}, start)
        self.assertEqual(p4.address, '13.14.15.16:6060')

        # 5. 纯文本 TXT
        p5 = ProxyManager.decode("17.18.19.20:5050\n1.1.1.1:80", start)
        self.assertEqual(p5.address, '17.18.19.20:5050')



class ProxyModeAndPoolTest(unittest.TestCase):
    """始终走代理模式、IP 池大小、提取频率与轮换分配。"""

    def setUp(self):
        ManagerTest.setUp(self)

    supply = ManagerTest.supply

    def make(self, **kwargs):
        self.manager = ProxyManager(self.database, 'http://provider.invalid', **kwargs)
        return self.manager

    def save_setting(self, key, value):
        with self.manager.connection(write=True) as db:
            db.execute('CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value TEXT)')
            db.execute('INSERT OR REPLACE INTO system_settings(key, value) VALUES(?, ?)', (key, value))

    def fill(self, count):
        for index in range(count):
            self.assertTrue(self.supply(f'114.106.134.{index + 1}', 300)[0])
            self.clock.now += 1

    def test_defaults_keep_original_behaviour(self):
        self.assertEqual(self.manager.mode, 'auto')
        self.assertEqual(self.manager.pool_size, 2)
        self.assertEqual(self.manager.fetch_interval, 1)
        self.assertFalse(self.manager.active(None))
        self.assertFalse(self.manager.active('快手'))

    def test_disabled_without_api_url_even_in_always_mode(self):
        manager = ProxyManager(self.database, '', mode='always')
        self.assertFalse(manager.always)
        self.assertFalse(manager.active('快手'))

    def test_always_mode_proxies_every_platform_without_windows(self):
        self.make(mode='always')
        self.assertTrue(self.manager.active('抖音'))
        self.assertTrue(self.manager.active(None))
        self.manager.activate('快手')
        with self.manager.connection() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM proxy_platform_windows').fetchone())
        with patch.object(self.manager, 'replenish') as replenish:
            self.manager.maintain_once()
            replenish.assert_called_once()

    def test_admin_setting_overrides_constructor(self):
        self.make(mode='auto', pool_size='3')
        self.save_setting('proxy_mode', 'always')
        self.save_setting('proxy_pool_size', '5')
        self.assertEqual(self.manager.mode, 'always')
        self.assertEqual(self.manager.pool_size, 5)
        self.save_setting('proxy_mode', 'bogus')
        self.assertEqual(self.manager.mode, 'auto')

    def test_pool_size_limits_inventory(self):
        self.make(pool_size=4)
        self.fill(4)
        self.assertFalse(self.supply('114.106.134.9', 300)[0])

    def test_fetch_rate_shortens_interval(self):
        self.make(fetch_per_second=4)
        self.assertTrue(self.supply('114.106.134.1', 300)[0])
        self.assertFalse(self.supply('114.106.134.2', 300)[0])
        self.clock.now += 0.25
        self.assertTrue(self.supply('114.106.134.2', 300)[0])

    def test_rotation_spreads_parses_across_pool(self):
        self.make(pool_size=3)
        self.fill(3)
        picked = []
        for _ in range(6):
            picked.append(self.manager.available().address)
            self.clock.now += 0.1
        self.assertEqual(picked[:3], ['114.106.134.1:35152', '114.106.134.2:35152', '114.106.134.3:35152'])
        self.assertEqual(picked[3:], picked[:3])

    def test_rotation_respects_excluded_addresses(self):
        self.make(pool_size=3)
        self.fill(3)
        first = self.manager.available()
        retry = self.manager.available({first.address})
        self.assertNotEqual(retry.address, first.address)

    def test_old_database_gets_last_used_column(self):
        legacy = os.path.join(self.temp.name, 'legacy.db')
        db = sqlite3.connect(legacy)  # 模拟升级前的库结构
        db.execute('CREATE TABLE proxy_addresses (address TEXT PRIMARY KEY, expires_at REAL NOT NULL, '
                   'created_at REAL NOT NULL, invalid INTEGER NOT NULL DEFAULT 0, retired INTEGER NOT NULL DEFAULT 0)')
        db.execute("INSERT INTO proxy_addresses(address, expires_at, created_at) VALUES('1.2.3.4:80', 5000, 900)")
        db.commit()
        db.close()
        manager = ProxyManager(legacy, 'http://provider.invalid')
        self.assertEqual(manager.available().address, '1.2.3.4:80')


class AlwaysModeIntegrationTest(unittest.TestCase):
    def setUp(self):
        RetryIntegrationTest.setUp(self)
        with self.manager.connection(write=True) as db:
            db.execute("INSERT OR REPLACE INTO system_settings(key, value) VALUES('proxy_mode', 'always')")
            db.execute("INSERT OR REPLACE INTO system_settings(key, value) VALUES('proxy_pool_size', '3')")

    supply = RetryIntegrationTest.supply
    parse = RetryIntegrationTest.parse

    def test_first_network_step_uses_proxy_and_parses_rotate(self):
        seen = []

        def redirect(url):
            seen.append(current_attempt().proxy)
            return url

        self.redirect.side_effect = redirect
        with patch('src.utils.proxy_manager.requests.Session') as sessions:
            sessions.return_value.__enter__.side_effect = self.supply
            for _ in range(3):
                self.manager.replenish(self.clock.now + 5)
                self.clock.now += 1
        self.assertEqual(len(self.sessions), 3)
        for _ in range(3):
            response, _ = self.parse([fake_parser()])
            self.assertEqual(response.status_code, 200)
            self.clock.now += 0.1
        self.assertTrue(all(seen))
        self.assertEqual(len({proxy.address for proxy in seen}), 3)
        self.assertTrue(self.manager.active('快手'))
        with self.manager.connection() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM proxy_platform_windows').fetchone())

    def test_cookie_failure_in_always_mode_rotates_without_window(self):
        seen = []

        def build(*args):
            seen.append(current_attempt().proxy)
            return fake_parser('cookie' if len(seen) == 1 else 'success')

        response, _ = self.parse(build)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(seen))
        self.assertNotEqual(seen[0].address, seen[1].address)


class ProxySettingsAdminTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test',
                               'DATABASE': os.path.join(self.temp.name, 'test.db'),
                               'DYNAMIC_PROXY_API_URL': 'http://provider.invalid'})
        self.client = self.app.test_client()
        for path, extra in (('/auth/setup', {'confirm_password': 'password123'}), ('/auth/login', {})):
            self.client.post(path, data={'csrf_token': self.csrf(), 'username': 'admin',
                                         'password': 'password123', **extra})

    def csrf(self):
        with self.client.session_transaction() as session:
            session['csrf_token'] = 'test-csrf'
        return 'test-csrf'

    def test_page_shows_defaults_and_saves_proxy_options(self):
        page = self.client.get('/admin/settings').get_data(as_text=True)
        self.assertRegex(page, r'value="auto"[^>]*\s+checked')
        self.assertRegex(page, r'id="proxy_pool_size"[^>]*value="2"')
        self.assertRegex(page, r'id="proxy-toggle"[^>]*checked')
        response = self.client.post('/admin/settings', headers={'Accept': 'application/json'}, data={
            'csrf_token': self.csrf(), 'proxy_enabled_field': '1', 'proxy_enabled': 'on',
            'proxy_mode': 'always', 'proxy_pool_size': '500', 'proxy_fetch_per_second': 'abc',
        })
        self.assertEqual(response.status_code, 200)
        manager = self.app.extensions['proxy_manager']
        self.assertEqual(manager.mode, 'always')
        self.assertEqual(manager.pool_size, 100)
        self.assertEqual(manager.fetch_interval, 1)
        page = self.client.get('/admin/settings').get_data(as_text=True)
        self.assertRegex(page, r'value="always"[^>]*\s+checked')

    def test_master_switch_disables_proxy_and_greys_fields(self):
        manager = self.app.extensions['proxy_manager']
        self.assertTrue(manager.enabled)
        self.client.post('/admin/settings', headers={'Accept': 'application/json'}, data={
            'csrf_token': self.csrf(), 'proxy_enabled_field': '1', 'proxy_mode': 'always',
        })
        self.assertFalse(manager.switch_on)
        self.assertFalse(manager.enabled)
        self.assertFalse(manager.active('快手'))
        page = self.client.get('/admin/settings').get_data(as_text=True)
        self.assertRegex(page, r'<fieldset id="proxy-fields"[^>]*disabled')
        self.assertIn('已关闭 · 全部直连', page)

    def test_unrelated_settings_post_keeps_proxy_switch(self):
        self.client.post('/admin/settings', headers={'Accept': 'application/json'},
                         data={'csrf_token': self.csrf(), 'global_api_enabled': '1'})
        self.assertTrue(self.app.extensions['proxy_manager'].enabled)

    def test_fresh_install_without_url_is_off(self):
        manager = ProxyManager(os.path.join(self.temp.name, 'fresh.db'), '')
        self.assertFalse(manager.switch_on)
        self.assertFalse(manager.enabled)
