import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

# 业务常量
DOMAIN_TO_NAME = business_config["DOMAIN_TO_NAME"]
USER_AGENT_PC = business_config["USER_AGENT_PC"]
USER_AGENT_M = business_config["USER_AGENT_M"]
