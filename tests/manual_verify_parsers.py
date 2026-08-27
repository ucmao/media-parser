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
    if not case.get("url"):
        return "MISSING", platform, "未配置真实链接"
    try:
        real_url = WebFetcher.fetch_redirect_url(case["url"])
        if not real_url:
            return "FAILED", platform, "无法获取或识别分享链接"
        detected_platform = UrlParser.get_platform(real_url)
        if detected_platform != platform:
            return "FAILED", platform, f"识别为 {detected_platform or '未知平台'}"
        parser = ParserFactory.create_parser(platform, real_url)
        found = collect_media(parser)
        missing = [field for field in case["expected_fields"] if not found.get(field)]
        if missing:
            return "FAILED", platform, f"缺少字段：{', '.join(missing)}"
        present = ", ".join(name for name, value in found.items() if value)
        return "PASSED", platform, f"已取得：{present}"
    except Exception as exc:
        return "FAILED", platform, f"{type(exc).__name__}: {exc}"


def main():
    parser = argparse.ArgumentParser(description="人工验证 Parser 真实分享链接")
    parser.add_argument("--platform", action="append", help="仅验证指定平台；可重复传入")
    parser.add_argument("--list-missing", action="store_true", help="仅列出缺少链接的平台")
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

    results = [verify_case(case) for case in cases]
    for status, platform, detail in results:
        print(f"{status:<7} {platform}: {detail}")
    summary = {status: sum(1 for result in results if result[0] == status) for status in ("PASSED", "FAILED", "MISSING")}
    print("\n汇总：" + ", ".join(f"{key}={value}" for key, value in summary.items()))


if __name__ == "__main__":
    main()
