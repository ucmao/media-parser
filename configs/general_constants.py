import os
import json
from dotenv import load_dotenv

# 加载环境变量与基础配置
load_dotenv()
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 核心域名
DOMAIN = os.getenv("DOMAIN")


def load_business_json(json_path):
    """加载并验证业务配置JSON"""
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"业务配置文件不存在：{json_path}\n请检查configs目录")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON格式错误：{json_path}\n{str(e)}")


# 加载业务配置
business_config = load_business_json(os.path.join(PROJECT_ROOT, "configs", "business_config.json"))

# 文件路径配置
static_dir = os.path.join(PROJECT_ROOT, "static")
SAVE_VIDEO_PATH = os.path.join(static_dir, "videos")
SAVE_IMAGE_PATH = os.path.join(static_dir, "images")
SAVE_AVATAR_PATH = os.path.join(static_dir, "avatars")

# 缓存/下载相关配置
# 仅缓存小文件：默认 15MB，可通过环境变量 MAX_CACHE_SIZE_MB 调整
MAX_CACHE_SIZE_MB = int(os.getenv("MAX_CACHE_SIZE_MB", "15"))
MAX_CACHE_SIZE_BYTES = MAX_CACHE_SIZE_MB * 1024 * 1024

# 业务常量
DOMAIN_TO_NAME = business_config["DOMAIN_TO_NAME"]
USER_AGENT_PC = business_config["USER_AGENT_PC"]
USER_AGENT_M = business_config["USER_AGENT_M"]


def check_essential_dirs():
    """检查并创建必要目录"""
    for dir_path in [SAVE_VIDEO_PATH, SAVE_IMAGE_PATH, SAVE_AVATAR_PATH]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            print(f"已创建目录：{dir_path}")


check_essential_dirs()  # 启动检查
