import mysql.connector
from configs.general_constants import DATABASE_CONFIG
import json
from configs.logging_config import logger


class UserInfoQuery:
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
        # 检查每个字段的值是否是数字且大于0
        for key in keys:
            value = limits[key]
            if not isinstance(value, (int)) or value <= 0:
                return False

        return True

    def update_user_info(self, open_id, user_info):
        try:
            update_query = """
            UPDATE users
            SET nickname = %s, avatar_url = %s, gender = %s, country = %s, province = %s, city = %s
            WHERE open_id = %s
            """
            self.cursor.execute(update_query, (
                user_info.get('nickName', ''),
                user_info.get('avatarUrl', ''),
                'male' if user_info.get('gender', 0) == 1 else 'female' if user_info.get('gender', 0) == 2 else 'unknown',
                user_info.get('country', ''),
                user_info.get('province', ''),
                user_info.get('city', ''),
                open_id
            ))

            self.conn.commit()
            return True, "User updated successfully"

        except Exception as e:
            return False, str(e)

    def get_user_permissions(self, open_id):
        try:
            select_query = """
            SELECT permissions
            FROM users
            WHERE open_id = %s
            """
            self.cursor.execute(select_query, (open_id,))
            result = self.cursor.fetchone()
            logger.debug(f'result: {result}')

            if result:
                permissions = result['permissions']
                if permissions is None:
                    return True, {}
                else:
                    data_dict = json.loads(permissions)
                    if UserInfoQuery.validate_limits(data_dict):
                        return True, data_dict
                    return False, "Incorrect format"
            else:
                return False, "User not found"

        except Exception as e:
            return False, str(e)

    def upload_user_permissions(self, open_id, permissions):
        try:
            if not UserInfoQuery.validate_limits(permissions):
                return False, "Incorrect format"

            # 将权限字典转换为 JSON 字符串
            permissions_json = json.dumps(permissions)

            # 更新用户权限
            update_query = """
            UPDATE users
            SET permissions = %s
            WHERE open_id = %s
            """
            self.cursor.execute(update_query, (permissions_json, open_id))
            self.conn.commit()

            return True, "Permissions updated successfully"

        except Exception as e:
            return False, str(e)

    def compare_and_update_permissions(self, open_id, client_permissions):
        try:
            # 读取服务器的 permissions
            success, server_permissions = self.get_user_permissions(open_id)
            if not success:
                return False, server_permissions

            logger.debug(f'server_permissions {server_permissions}')
            # 保留指定的字段
            allowed_fields = {
                'watermarkLimit',
                'singleDownloadLimit',
                'bulkDownloadLimit',
                'searchLimit',
                'storageLimit'
            }
            server_permissions = {key: server_permissions[key] for key in server_permissions if key in allowed_fields}
            client_permissions = {key: client_permissions[key] for key in client_permissions if key in allowed_fields}

            if server_permissions == client_permissions:
                return False, server_permissions

            if server_permissions == {}:
                updated_permissions = client_permissions
            elif client_permissions == {}:
                updated_permissions = server_permissions
            else:
                # 比较并更新 permissions
                updated_permissions = {}
                for key in client_permissions:
                    if key in server_permissions:
                        updated_permissions[key] = max(server_permissions[key], client_permissions[key])
                    else:
                        updated_permissions[key] = client_permissions[key]

            logger.debug(f'updated_permissions {updated_permissions}')
            # 上传更新后的 permissions
            success, message = self.upload_user_permissions(open_id, updated_permissions)
            if success:
                return True, updated_permissions
            else:
                return False, message

        except Exception as e:
            return False, str(e)
