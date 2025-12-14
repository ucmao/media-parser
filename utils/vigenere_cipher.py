import time
import random
import string


class VigenereCipher:
    def __init__(self, timestamp):
        self.key = self.timestamp_to_letters(timestamp)

    @staticmethod
    def timestamp_to_letters(timestamp):
        digits_to_letters = 'abcdefghijklmnopqrstuvwxyz'  # 字母表
        result = ''
        for char in timestamp:
            if char.isdigit():  # 检查是否是数字字符
                index = int(char)  # 将字符转换为数字
                if 0 <= index < len(digits_to_letters):
                    result += digits_to_letters[index]  # 映射到字母
                else:
                    # 处理超出范围的数字，如果需要的话
                    result += '?'  # 或者抛出错误
            else:
                # 处理非数字字符，如果需要的话
                result += '?'  # 或者抛出错误
        return result

    # Vigenère密码加密函数
    def vigenere_encrypt(self, text):
        encrypted = []
        key_index = 0
        for char in text:
            if char.isalpha():
                shift = 65 if char.isupper() else 97
                key_char = self.key[key_index % len(self.key)].lower()
                key_shift = ord(key_char) - 97
                encrypted_char = chr((ord(char) - shift + key_shift) % 26 + shift)
                encrypted.append(encrypted_char)
                key_index += 1
            else:
                encrypted.append(char)
        return ''.join(encrypted)

    # Vigenère密码解密函数
    def vigenere_decrypt(self, text):
        decrypted = []
        key_index = 0
        for char in text:
            if char.isalpha():
                shift = 65 if char.isupper() else 97
                key_char = self.key[key_index % len(self.key)].lower()
                key_shift = ord(key_char) - 97
                decrypted_char = chr((ord(char) - shift - key_shift + 26) % 26 + shift)
                decrypted.append(decrypted_char)
                key_index += 1
            else:
                decrypted.append(char)
        return ''.join(decrypted)

    def verify_decryption(self, encrypted_text, original_text):
        decrypted_text = self.vigenere_decrypt(encrypted_text)
        return decrypted_text == original_text


def generate_complex_text(length=32):
    # 生成包含大小写字母、数字和特殊字符的随机字符串
    # characters = string.ascii_letters + string.digits + string.punctuation
    characters = string.ascii_letters
    return ''.join(random.choice(characters) for _ in range(length))


# 示例
if __name__ == "__main__":
    # 生成复杂原文
    original_text = generate_complex_text()
    print("Original Text: " + original_text)

    # 获取当前时间戳
    timestamp = int(time.time() * 1000)  # 毫秒级时间戳

    # 创建VigenereCipher实例
    cipher = VigenereCipher(str(timestamp))
    print("Key: " + cipher.key)

    # 加密原文
    encrypted_text = cipher.vigenere_encrypt(original_text)
    print("Encrypted Text: " + encrypted_text)

    # 解密原文
    decrypted_text = cipher.vigenere_decrypt(encrypted_text)
    print("Decrypted Text: " + decrypted_text)

    # 验证解密
    is_verified = cipher.verify_decryption(encrypted_text, original_text)
    print("Decryption Verified: " + str(is_verified))
