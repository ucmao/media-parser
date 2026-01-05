import os
import json
from dotenv import load_dotenv

# 加载环境变量与基础配置
load_dotenv()
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 微信配置
WECHAT_APP_ID = os.getenv("WECHAT_APP_ID")
WECHAT_APP_SECRET = os.getenv("WECHAT_APP_SECRET")
DOMAIN = os.getenv("DOMAIN")

# 数据库配置
DATABASE_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

# 如果 host 是 localhost，移除 port 配置
if DATABASE_CONFIG["host"] == "localhost":
    DATABASE_CONFIG.pop("port", None)


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

# 业务常量
DOMAIN_TO_NAME = business_config["DOMAIN_TO_NAME"]
PLATFORM_MAP = business_config["PLATFORM_MAP"]
MINI_PROGRAM_LEGAL_DOMAIN = business_config["MINI_PROGRAM_LEGAL_DOMAIN"]
USER_AGENT_PC = business_config["USER_AGENT_PC"]
USER_AGENT_M = business_config["USER_AGENT_M"]


def check_essential_dirs():
    """检查并创建必要目录"""
    for dir_path in [SAVE_VIDEO_PATH, SAVE_IMAGE_PATH, SAVE_AVATAR_PATH]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            print(f"已创建目录：{dir_path}")


check_essential_dirs()  # 启动检查
