import ssl
import socket
from datetime import datetime
import requests
import certifi
from urllib3.util.ssl_ import create_urllib3_context


def get_certificate_expiry_date(domain):
    try:
        # 创建自定义SSL上下文，调整协议和验证选项
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2  # 设置最低TLS版本
        context.verify_mode = ssl.CERT_REQUIRED  # 强制验证证书
        context.check_hostname = True  # 验证主机名
        context.load_verify_locations(certifi.where())  # 使用certifi的证书库

        # 增加超时时间和重试机制
        sock = socket.create_connection((domain, 443), timeout=15)
        ssock = context.wrap_socket(sock, server_hostname=domain)

        try:
            cert = ssock.getpeercert()
            # 获取证书的到期时间
            expiry_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y GMT')
            return expiry_date
        finally:
            ssock.close()
            sock.close()

    except ssl.SSLError as e:
        print(f"SSL 错误：{e}")
        # 尝试调试信息
        debug_ssl_connection(domain)
    except socket.timeout as e:
        print(f"连接超时：{e}")
    except Exception as e:
        print(f"获取证书信息时出错: {e}")
    return None


def debug_ssl_connection(domain):
    """提供更多调试信息"""
    try:
        # 使用openssl命令行工具获取更多信息
        import subprocess
        result = subprocess.run(
            ['openssl', 's_client', '-connect', f'{domain}:443', '-showcerts'],
            capture_output=True,
            text=True,
            timeout=10
        )
        print(f"\nSSL连接调试信息({domain}):")
        print(result.stdout)
        print(result.stderr)
    except Exception as e:
        print(f"调试时出错: {e}")


# 示例输出，测试函数
if __name__ == "__main__":
    domains = ["doc.bishengusdt.com", "doc.bs123.org"]
    for domain in domains:
        print(f"\n检查域名: {domain}")
        expiry_date = get_certificate_expiry_date(domain)
        if expiry_date:
            print(f"{domain} 的证书到期时间: {expiry_date}")
        else:
            print(f"无法获取 {domain} 的证书信息。")