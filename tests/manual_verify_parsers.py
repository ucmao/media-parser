"""人工执行的真实链接解析验证工具；不参与 unittest 自动发现。"""

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.parser_factory import ParserFactory
from utils.web_fetcher import UrlParser, WebFetcher


SAMPLES_PATH = Path(__file__).with_name("live_parser_samples.json")


def load_cases():
    return json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))["cases"]


def collect_media(parser):
    def call(method_name, default):
        try:
            return getattr(parser, method_name)()
        except NotImplementedError:
            return default
        except Exception:
            return default

    video_url = call("get_real_video_url", None)
    video_list = call("get_video_list", [])
    image_list = call("get_image_list", [])
    return {
        "video": bool(video_url or video_list),
        "audio": bool(call("get_audio_url", None)),
        "cover": bool(call("get_cover_photo_url", None)),
        "title": bool(call("get_title_content", "")),
        "author": bool(call("get_author_info", {})),
        "images": bool(image_list),
        "live_media": any(
            isinstance(item, dict) and item.get("live_photo_url") for item in image_list
        ),
    }


def verify_case(case):
    platform = case["platform"]
    pattern = case.get("pattern", "标准链接")
    url = case.get("url", "")
    if not url:
        return "MISSING", platform, pattern, "未配置真实链接", url
    try:
        real_url = WebFetcher.fetch_redirect_url(url)
        if not real_url:
            return "FAILED", platform, pattern, "无法获取或识别分享链接", url
        detected_platform = UrlParser.get_platform(real_url)
        if detected_platform != platform:
            return "FAILED", platform, pattern, f"识别为 {detected_platform or '未知平台'}", url
        parser = ParserFactory.create_parser(platform, real_url)
        found = collect_media(parser)
        expected = case.get("expected_fields", ["title"])
        missing = [field for field in expected if not found.get(field)]
        if missing:
            return "FAILED", platform, pattern, f"缺少字段：{', '.join(missing)}", url
        present = ", ".join(name for name, value in found.items() if value)
        return "PASSED", platform, pattern, f"已取得：{present}", url
    except Exception as exc:
        return "FAILED", platform, pattern, f"{type(exc).__name__}: {exc}", url


def main():
    parser = argparse.ArgumentParser(description="一键多形态验证 31 平台真实分享链接")
    parser.add_argument("--platform", action="append", help="仅验证指定平台；可重复传入")
    parser.add_argument("--list-missing", action="store_true", help="仅列出缺少链接的平台")
    parser.add_argument("--limit", type=int, default=0, help="限制每个平台运行的最大用例数 (默认全部)")
    args = parser.parse_args()

    cases = load_cases()
    if args.platform:
        requested = set(args.platform)
        cases = [case for case in cases if case["platform"] in requested]
        unknown = requested - {case["platform"] for case in cases}
        if unknown:
            parser.error(f"样例清单中不存在平台：{', '.join(sorted(unknown))}")
    if args.list_missing:
        for case in cases:
            if not case.get("url"):
                print(f"MISSING  {case['platform']}: {case['note']}")
        return

    if args.limit > 0:
        limited_cases = []
        counts = {}
        for case in cases:
            p = case["platform"]
            counts[p] = counts.get(p, 0) + 1
            if counts[p] <= args.limit:
                limited_cases.append(case)
        cases = limited_cases

    print(f"🧪 开始执行 31 平台自动化多形态链接验证 (共 {len(cases)} 条用例)...\n")
    results = [verify_case(case) for case in cases]
    for status, platform, pattern, detail, url in results:
        status_tag = f"✅ {status}" if status == "PASSED" else (f"❌ {status}" if status == "FAILED" else f"⚪ {status}")
        print(f"{status_tag:<10} [{platform:<6}] ({pattern[:25]}): {detail}")

    summary = {status: sum(1 for result in results if result[0] == status) for status in ("PASSED", "FAILED", "MISSING")}
    print("\n" + "=" * 60)
    print("📊 验证汇总：" + ", ".join(f"{key}={value}" for key, value in summary.items()))
    total = len(results)
    if total > 0:
        pass_rate = (summary['PASSED'] / total) * 100
        print(f"🎯 整体通过率：{pass_rate:.1f}% ({summary['PASSED']}/{total})")
    print("=" * 60)


if __name__ == "__main__":
    main()

