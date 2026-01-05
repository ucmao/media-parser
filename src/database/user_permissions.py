import mysql.connector
import json


class UserPermissions:
    def __init__(self):
        self.conn = mysql.connector.connect(**DATABASE_CONFIG)
        self.cursor = self.conn.cursor(dictionary=True)

    def close(self):
        self.cursor.close()
        self.conn.close()

    @staticmethod
    def validate_limits(limits):
        allowed_fields = {
            'watermarkLimit',
            'singleDownloadLimit',
            'bulkDownloadLimit',
            'searchLimit',
            'storageLimit'
        }
        # 检查传入字典的键是否仅包含允许的字段
        keys = set(limits.keys())
        if keys != allowed_fields:
            return False
        # 检查每个字段的值是否是整数且大于0
        for key in keys:
            value = limits[key]
            if not isinstance(value, int) or value <= 0:
                return False

        return True

    def get_user_by_open_id(self, open_id):
        try:
            select_query = """
            SELECT *
            FROM users
            WHERE open_id = %s
            """
            self.cursor.execute(select_query, (open_id,))
            result = self.cursor.fetchone()

            if result:
                return True, result
            else:
                return False, "User not found"

        except Exception as e:
            return False, str(e)

    def set_user_permissions(self, open_id, permissions):
        if not UserPermissions.validate_limits(permissions):
            return False, "Invalid permissions format"

        try:
            update_query = """
            UPDATE users
            SET permissions = %s
            WHERE open_id = %s
            """
            self.cursor.execute(update_query, (json.dumps(permissions), open_id))
            self.conn.commit()
            return True, "Permissions updated successfully"

        except Exception as e:
            return False, str(e)


def generate_vip_permissions(multiplier=None, custom_value=None):
    default_values = {
        'watermarkLimit': 50,
        'singleDownloadLimit': 10,
        'bulkDownloadLimit': 5,
        'searchLimit': 5,
        'storageLimit': 100
    }

    if custom_value is not None and isinstance(custom_value, int) and custom_value > 0:
        return {key: custom_value for key in default_values}

    if multiplier is not None and isinstance(multiplier, int) and multiplier > 0:
        return {key: value * multiplier for key, value in default_values.items()}

    return default_values


def query_and_set_permissions():
    manager = UserPermissions()

    while True:
        command = input("请输入要查询的 open_id 或输入 'exit' 退出: ")
        if command.lower() == 'exit':
            break

        open_id = command
        success, result = manager.get_user_by_open_id(open_id)
        if success:
            user = result

            print("用户数据:")
            for key, value in user.items():
                print(f"{key}: {value}")

            set_permission = input("是否要对权限进行设置？(y/n): ")
            if set_permission.lower() == 'y':
                while True:
                    choice = input("请选择设置方式 (1: 倍数设置, 2: 自定义值设置): ")
                    if choice == '1':
                        while True:
                            try:
                                multiplier = int(input("请输入倍数（参考10/20/30）: "))
                                if multiplier > 0:
                                    permissions = generate_vip_permissions(multiplier=multiplier)
                                    break
                                else:
                                    print("倍数必须是大于0的整数，请重新输入。")
                            except ValueError:
                                print("输入无效，请输入一个整数。")
                        break
                    elif choice == '2':
                        while True:
                            try:
                                custom_value = int(input("请输入自定义值: "))
                                if custom_value > 0:
                                    permissions = generate_vip_permissions(custom_value=custom_value)
                                    break
                                else:
                                    print("自定义值必须是大于0的整数，请重新输入。")
                            except ValueError:
                                print("输入无效，请输入一个整数。")
                        break
                    else:
                        print("无效的选择，请重新输入。")

                success, message = manager.set_user_permissions(user['open_id'], permissions)
                if success:
                    print("权限设置成功")
                else:
                    print("权限设置失败:", message)
            else:
                print("跳过权限设置。")
        else:
            print("查询失败:", result)

    manager.close()


if __name__ == "__main__":
    DATABASE_CONFIG = {
    'host': 'localhost',  # 数据库主机地址
    'user': 'root',  # 数据库用户名
    'password': 'yuandian123',  # 数据库密码
    'database': 'parse_ucmao'  # 数据库名称
    }
    query_and_set_permissions()

