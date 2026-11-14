import os
import secrets
import fcntl
from datetime import timedelta
from flask import Flask
from flask_cors import CORS
from src.api.parse import bp as api_bp
from src.web.views import bp as web_bp
from src.auth import bp as auth_bp, register_template_helpers
from src.web.portal import bp as portal_bp
from src.web.admin import bp as admin_bp
from src.db import init_app as init_database
from src.utils.proxy_manager import ProxyManager
from configs.logging_config import get_logger

logger = get_logger(__name__)


def _load_or_create_secret(data_dir):
    """为零配置部署生成可持久化的随机会话密钥。"""
    secret_path = os.path.join(data_dir, ".secret_key")
    try:
        descriptor = os.open(secret_path, os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, "r+", encoding="utf-8") as secret_file:
            fcntl.flock(secret_file.fileno(), fcntl.LOCK_EX)
            saved = secret_file.read().strip()
            if saved:
                return saved
            generated = secrets.token_hex(32)
            secret_file.seek(0)
            secret_file.write(generated)
            secret_file.flush()
            os.fsync(secret_file.fileno())
            return generated
    except (PermissionError, OSError) as e:
        logger.warning(f"无法读写密钥文件 {secret_path}，使用临时随机会话密钥: {e}")
        return secrets.token_hex(32)


def create_app(config=None):
    """应用工厂函数"""
    data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')
    app = Flask(__name__, instance_path=data_dir, template_folder='templates', static_folder='static')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or None
    app.config['DATABASE'] = os.getenv(
        'DATABASE_PATH', os.path.join(app.instance_path, 'media_parser.db')
    )
    proxy_url = (os.getenv('DYNAMIC_PROXY_API_URL') or os.getenv('JULIANG_PROXY_API_URL') or '').strip()
    app.config['DYNAMIC_PROXY_API_URL'] = proxy_url
    app.config['JULIANG_PROXY_API_URL'] = proxy_url
    app.config['PROXY_MODE'] = (os.getenv('PROXY_MODE') or '').strip().lower()
    app.config['PROXY_POOL_SIZE'] = (os.getenv('PROXY_POOL_SIZE') or '').strip()
    app.config['PROXY_FETCH_PER_SECOND'] = (os.getenv('PROXY_FETCH_PER_SECOND') or '').strip()
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    app.config['JSON_SORT_KEYS'] = False
    app.config['TRUST_PROXY_HEADERS'] = os.getenv(
        'TRUST_PROXY_HEADERS', ''
    ).strip().lower() in {'1', 'true', 'yes', 'on'}
    app.config['API_ONLY'] = os.getenv(
        'API_ONLY', ''
    ).strip().lower() in {'1', 'true', 'yes', 'on'}
    if hasattr(app, 'json'):
        app.json.sort_keys = False
    if config:
        app.config.update(config)

    database_dir = os.path.dirname(app.config['DATABASE'])
    if database_dir:
        os.makedirs(database_dir, exist_ok=True)
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = _load_or_create_secret(database_dir or app.instance_path)
    init_database(app)
    manager = ProxyManager(
        app.config["DATABASE"], app.config["DYNAMIC_PROXY_API_URL"],
        mode=app.config.get("PROXY_MODE"), pool_size=app.config.get("PROXY_POOL_SIZE"),
        fetch_per_second=app.config.get("PROXY_FETCH_PER_SECOND"),
    )
    app.extensions["proxy_manager"] = manager
    if not app.testing:
        manager.start()
        from src.utils.cookie_registry import start_auto_inspector
        start_auto_inspector()

    # 跨域配置（仅对 /api/* 接口开放，默认允许所有来源，支持通过环境变量 CORS_ORIGINS 自定义）
    cors_origins_raw = (os.getenv('CORS_ORIGINS') or '*').strip()
    cors_origins = '*' if cors_origins_raw == '*' else [
        origin.strip() for origin in cors_origins_raw.split(',') if origin.strip()
    ]
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})

    # 注册蓝图
    app.register_blueprint(api_bp, url_prefix='/api')
    if not app.config.get('API_ONLY'):
        register_template_helpers(app)
        app.register_blueprint(web_bp)
        app.register_blueprint(auth_bp)
        app.register_blueprint(portal_bp)
        app.register_blueprint(admin_bp)

    if app.config.get('TRUST_PROXY_HEADERS'):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('WEB_PORT', '8051')))
