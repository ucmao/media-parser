from flask import Flask, session, render_template
import os
from src.api import login, ranking, upload_userinfo, refresh_video, upload_record, download, upload_score
from src.api import records, parse, admin
from configs.logging_config import logger

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')

# 注册API蓝图
app.register_blueprint(login.bp, url_prefix='/api')
app.register_blueprint(parse.bp, url_prefix='/api')
app.register_blueprint(ranking.bp, url_prefix='/api')
app.register_blueprint(records.bp, url_prefix='/api')
app.register_blueprint(upload_score.bp, url_prefix='/api')
app.register_blueprint(upload_record.bp, url_prefix='/api')
app.register_blueprint(upload_userinfo.bp, url_prefix='/api')
app.register_blueprint(refresh_video.bp, url_prefix='/api')
app.register_blueprint(download.bp, url_prefix='/api')

# 注册现代管理后台蓝图
app.register_blueprint(admin.bp)

@app.route('/')
def index():
    """前台展示页面（Landing Page）"""
    return render_template('landing.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
