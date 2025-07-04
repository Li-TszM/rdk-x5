# AES-256-CBC + PKCS7 + base64 加密/解密工具 - 增强版(多种加密协议)
# 依赖: pip install pycryptodome
import base64
import os
import random
import hashlib
import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

BLOCK_SIZE = 16  # AES block size

# 密钥长度32字节（256位）
def _fix_key(key: str) -> bytes:
    # 确保密钥是字符串类型
    if not isinstance(key, str):
        key = str(key)
    
    # 转换为字节并确保长度为32字节
    key_bytes = key.encode('utf-8')
    if len(key_bytes) < 32:
        # 使用PKCS7风格填充，重复密钥直到达到32字节
        repetitions = (32 // len(key_bytes)) + 1
        key_bytes = (key_bytes * repetitions)[:32]
    else:
        key_bytes = key_bytes[:32]
    return key_bytes

# 协议1: 基本的AES-256-CBC加密（兼容旧版本）
def encrypt_text_protocol1(plain_text: str, key: str) -> str:
    key_bytes = _fix_key(key)
    iv = os.urandom(BLOCK_SIZE)
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
    padded = pad(plain_text.encode('utf-8'), BLOCK_SIZE)
    encrypted = cipher.encrypt(padded)
    encrypted_data = iv + encrypted  # 前16字节为IV
    return base64.b64encode(encrypted_data).decode('utf-8')

def decrypt_text_protocol1(enc_text: str, key: str) -> str:
    key_bytes = _fix_key(key)
    enc_data = base64.b64decode(enc_text)
    iv = enc_data[:BLOCK_SIZE]
    encrypted = enc_data[BLOCK_SIZE:]
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
    padded = cipher.decrypt(encrypted)
    plain = unpad(padded, BLOCK_SIZE)
    return plain.decode('utf-8')

# 协议2: 带密钥派生的增强AES-256-CBC (PBKDF2)
def encrypt_text_protocol2(plain_text: str, key: str) -> str:
    # 创建盐值和强化密钥
    salt = os.urandom(16)
    key_hash = hashlib.pbkdf2_hmac('sha256', key.encode('utf-8'), salt, iterations=10000)
    
    # 加密
    iv = os.urandom(BLOCK_SIZE)
    cipher = AES.new(key_hash, AES.MODE_CBC, iv)
    padded = pad(plain_text.encode('utf-8'), BLOCK_SIZE)
    encrypted = cipher.encrypt(padded)
    
    # 组合数据
    metadata = {
        'protocol': 2,
        'salt': base64.b64encode(salt).decode('utf-8'),
        'iv': base64.b64encode(iv).decode('utf-8')
    }
    
    result = {
        'metadata': metadata,
        'data': base64.b64encode(encrypted).decode('utf-8')
    }
    
    return base64.b64encode(json.dumps(result).encode('utf-8')).decode('utf-8')

def decrypt_text_protocol2(enc_text: str, key: str) -> str:
    # 解析数据
    data = json.loads(base64.b64decode(enc_text).decode('utf-8'))
    metadata = data['metadata']
    encrypted = base64.b64decode(data['data'])
    
    # 恢复密钥和IV
    salt = base64.b64decode(metadata['salt'])
    iv = base64.b64decode(metadata['iv'])
    key_hash = hashlib.pbkdf2_hmac('sha256', key.encode('utf-8'), salt, iterations=10000)
    
    # 解密
    cipher = AES.new(key_hash, AES.MODE_CBC, iv)
    padded = cipher.decrypt(encrypted)
    plain = unpad(padded, BLOCK_SIZE)
    return plain.decode('utf-8')

# 协议3: 双重加密 (AES-256 + 密钥扰动)
def encrypt_text_protocol3(plain_text: str, key: str) -> str:
    # 创建盐值和派生密钥
    salt = os.urandom(16)
    key_hash1 = hashlib.pbkdf2_hmac('sha256', key.encode('utf-8'), salt, iterations=5000)
    key_hash2 = hashlib.pbkdf2_hmac('sha256', key.encode('utf-8') + salt, salt, iterations=7500)
    
    # 第一层加密
    iv1 = os.urandom(BLOCK_SIZE)
    cipher1 = AES.new(key_hash1, AES.MODE_CBC, iv1)
    padded1 = pad(plain_text.encode('utf-8'), BLOCK_SIZE)
    encrypted1 = cipher1.encrypt(padded1)
    
    # 第二层加密
    iv2 = os.urandom(BLOCK_SIZE)
    cipher2 = AES.new(key_hash2, AES.MODE_CBC, iv2)
    padded2 = pad(encrypted1, BLOCK_SIZE)
    encrypted2 = cipher2.encrypt(padded2)
    
    # 组合数据
    metadata = {
        'protocol': 3,
        'salt': base64.b64encode(salt).decode('utf-8'),
        'iv1': base64.b64encode(iv1).decode('utf-8'),
        'iv2': base64.b64encode(iv2).decode('utf-8')
    }
    
    result = {
        'metadata': metadata,
        'data': base64.b64encode(encrypted2).decode('utf-8')
    }
    
    return base64.b64encode(json.dumps(result).encode('utf-8')).decode('utf-8')

def decrypt_text_protocol3(enc_text: str, key: str) -> str:
    # 解析数据
    data = json.loads(base64.b64decode(enc_text).decode('utf-8'))
    metadata = data['metadata']
    encrypted2 = base64.b64decode(data['data'])
    
    # 恢复密钥和IV
    salt = base64.b64decode(metadata['salt'])
    iv1 = base64.b64decode(metadata['iv1'])
    iv2 = base64.b64decode(metadata['iv2'])
    key_hash1 = hashlib.pbkdf2_hmac('sha256', key.encode('utf-8'), salt, iterations=5000)
    key_hash2 = hashlib.pbkdf2_hmac('sha256', key.encode('utf-8') + salt, salt, iterations=7500)
    
    # 第二层解密
    cipher2 = AES.new(key_hash2, AES.MODE_CBC, iv2)
    padded1 = unpad(cipher2.decrypt(encrypted2), BLOCK_SIZE)
    
    # 第一层解密
    cipher1 = AES.new(key_hash1, AES.MODE_CBC, iv1)
    plain = unpad(cipher1.decrypt(padded1), BLOCK_SIZE)
    return plain.decode('utf-8')

# 集成函数 - 随机选择加密协议
def encrypt_text(plain_text: str, key: str) -> str:
    # 随机选择加密协议 (1, 2, 或 3)
    protocol = random.randint(1, 3)
    
    # 根据协议选择加密函数
    if protocol == 1:
        encrypted = encrypt_text_protocol1(plain_text, key)
        # 为协议1添加标识前缀
        return f"{{\"metadata\": {{\"protocol\": 1}}, \"data\": \"{encrypted}\"}}"
    elif protocol == 2:
        return encrypt_text_protocol2(plain_text, key)
    else:  # protocol == 3
        return encrypt_text_protocol3(plain_text, key)

# 解密函数 - 自动检测协议
def decrypt_text(enc_text: str, key: str) -> str:
    try:
        # 尝试解析为JSON
        data = json.loads(enc_text)
        protocol = data.get("metadata", {}).get("protocol", 1)
        
        if protocol == 1:
            # 协议1
            return decrypt_text_protocol1(data["data"], key)
        elif protocol == 2:
            # 协议2
            return decrypt_text_protocol2(enc_text, key)
        elif protocol == 3:
            # 协议3
            return decrypt_text_protocol3(enc_text, key)
        else:
            raise ValueError(f"未知的加密协议: {protocol}")
    except json.JSONDecodeError:
        # 如果不是JSON格式，假设是旧版的协议1
        return decrypt_text_protocol1(enc_text, key)

if __name__ == '__main__':
    # 简单测试
    key = 'test-key-1234567890'
    text = '中文English!@#￥%……&*（）——'
    
    # 测试所有协议
    for i in range(1, 4):
        print(f"\n测试协议 {i}:")
        if i == 1:
            enc = encrypt_text_protocol1(text, key)
            print(f'加密(协议1): {enc[:20]}...')
            dec = decrypt_text_protocol1(enc, key)
        elif i == 2:
            enc = encrypt_text_protocol2(text, key)
            print(f'加密(协议2): {enc[:20]}...')
            dec = decrypt_text_protocol2(enc, key)
        else:
            enc = encrypt_text_protocol3(text, key)
            print(f'加密(协议3): {enc[:20]}...')
            dec = decrypt_text_protocol3(enc, key)
        
        print(f'解密: {dec}')
        
    # 测试自动选择协议
    enc = encrypt_text(text, key)
    print("\n随机选择的协议:")
    print(f'加密: {enc[:50]}...')
    dec = decrypt_text(enc, key)
    print(f'解密: {dec}')
