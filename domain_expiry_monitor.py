import whois
import ssl
import socket
from datetime import datetime
import requests
import configparser
import schedule
import time

# 读取配置文件
def load_config(config_file="./config/config.ini"):
    config = configparser.ConfigParser()
    try:
        config.read(config_file)
        return config
    except Exception as e:
        print(f"读取配置文件时出错: {e}")
        return None


# 获取 SSL 证书的到期时间
def get_certificate_expiry_date(domain):
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                expiry_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y GMT')
                return expiry_date
    except ssl.SSLError as e:
        print(f"SSL 错误：{e}")
    except socket.timeout as e:
        print(f"连接超时：{e}")
    except Exception as e:
        print(f"获取证书信息时出错: {e}")
    return None


# 获取域名的到期时间
def get_domain_expiry_date(domain):
    try:
        w = whois.whois(domain)
        expiry_date = min(w.expiration_date) if isinstance(w.expiration_date, list) else w.expiration_date
        return expiry_date
    except Exception as e:
        print(f"查询域名 {domain} 时出错: {e}")
        return None


# 发送 Telegram 消息
def send_telegram_message(config, message):
    bot_token = config['BOT']['BOT_TOKEN']
    admin_user_ids = config['admins']['admin_user_ids'].split(",")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    for user_id in admin_user_ids:
        params = {
            'chat_id': user_id.strip(),
            'text': message,
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            print(f"成功发送通知给用户 {user_id}: {message}")
        else:
            print(f"发送失败给用户 {user_id}，状态码: {response.status_code}")


# 发送到期提醒
def send_alert(domain, days, item_type, config):
    message = f"{item_type} {domain} 将在 {days} 天后过期！"
    print(f"发送 Telegram 通知：{message}")  # 调试输出
    send_telegram_message(config, message)


# 检查证书的过期时间
def check_certificate_expiry(domain, config, alert_days):
    expiry_date = get_certificate_expiry_date(domain)
    if expiry_date:
        days_left = (expiry_date - datetime.now()).days
        print(f"域名: {domain} 证书剩余天数：{days_left}")  # 输出域名和证书剩余天数
        if days_left <= alert_days:  # 如果证书在 alert_days 天内过期，发送提醒
            send_alert(domain, days_left, "SSL 证书", config)


# 检查域名的到期时间
def check_domain_expiry(domain, config, alert_days):
    expiry_date = get_domain_expiry_date(domain)
    if expiry_date:
        days_left = (expiry_date - datetime.now()).days
        print(f"域名: {domain} 域名剩余天数：{days_left}")  # 输出域名和剩余天数
        if days_left <= alert_days:  # 如果域名在 alert_days 天内过期，发送提醒
            send_alert(domain, days_left, "域名", config)


# 定时执行任务的函数
def scheduled_task(config, alert_days):
    # 获取域名列表
    domains = [config['domains'].get('domain1'), config['domains'].get('domain2')]
    if not domains:
        print("未找到有效的域名配置！")
        return

    # 检查每个域名的到期时间和证书到期时间
    for domain in domains:
        print(f"\n检查域名: {domain}")
        check_domain_expiry(domain, config, alert_days)
        check_certificate_expiry(domain, config, alert_days)


# 主函数
def main():
    # 加载配置
    config = load_config()
    if config is None:
        return

    # 获取提醒提前天数配置
    alert_days = config.getint('alerts', 'alert_days', fallback=7)  # 默认提前7天提醒

    # 设置定时任务
    schedule.every().day.at("13:00").do(scheduled_task, config=config, alert_days=alert_days)
    # print("域名和证书到期监控程序已启动，等待定时任务执行...")
    # schedule.every(2).minutes.do(scheduled_task, config=config, alert_days=alert_days)

    # 持续运行，定期执行任务
    while True:
        schedule.run_pending()
        time.sleep(1)  # 每秒检查是否有任务要执行


if __name__ == "__main__":
    main()
