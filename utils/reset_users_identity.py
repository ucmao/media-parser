import os
import sys
import random
from dotenv import load_dotenv

# 将项目根目录添加到系统路径，以便导入 src 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
from configs.general_constants import DATABASE_CONFIG, DOMAIN

def generate_random_nickname():
    """生成 3-5 个汉字的随机昵称"""
    chars = (
        "云深不知处月明风清晚秋初雪小桥流水暮色微光星辰大海青空漫步离人思语归途"
        "山川岁月人间烟火浮生若梦浅笑安然时光荏苒静谧清浅长风破浪锦瑟流年半夏微凉"
    )
    length = random.randint(3, 5)
    return "".join(random.choices(chars, k=length))

def reset_users():
    load_dotenv()
    
    # 检查域名是否已配置
    if not DOMAIN or DOMAIN == "your_domain_here":
        print("错误: 请先在 .env 文件中配置真实的 DOMAIN 域名！")
        return

    db = DBManager(**DATABASE_CONFIG)
    try:
        db.connect()
        cursor = db.conn.cursor(dictionary=True)
        
        # 1. 获取所有用户
        cursor.execute("SELECT user_id, open_id FROM users")
        users = cursor.fetchall()
        
        if not users:
            print("数据库中暂无用户记录。")
            return

        print(f"开始重置 {len(users)} 名用户的身份信息...")
        
        count = 0
        for user in users:
            new_nickname = generate_random_nickname()
            # 使用 .env 中最新的 DOMAIN，处理可能自带协议的情况
            base_domain = DOMAIN.replace('https://', '').replace('http://', '')
            default_avatar = f"https://{base_domain}/static/images/default-avatar.png"
            
            cursor.execute(
                "UPDATE users SET nickname = %s, avatar_url = %s WHERE user_id = %s",
                (new_nickname, default_avatar, user['user_id'])
            )
            count += 1
            if count % 10 == 0:
                print(f"已处理 {count} 名用户...")
        
        db.conn.commit()
        print(f"\n✅ 成功！已为 {count} 名用户重置了随机昵称和最新的头像地址。")
        print(f"当前使用的域名: {DOMAIN}")

    except Exception as e:
        print(f"发生错误: {str(e)}")
    finally:
        db.disconnect()

if __name__ == "__main__":
    reset_users()

