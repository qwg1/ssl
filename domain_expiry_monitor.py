import whois
import ssl
import socket
from datetime import datetime
import requests
import configparser
import schedule
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 默认日志级别
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("log.log", encoding="utf-8"),  # 日志保存到文件
        logging.StreamHandler()  # 同时输出到控制台
    ]
)

# 读取配置文件
def load_config(config_file="./config/config.ini"):
    config = configparser.ConfigParser()
    try:
        config.read(config_file)
        return config
    except Exception as e:
        logging.error(f"读取配置文件时出错: {e}")
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
        logging.error(f"SSL 错误：{e}")
    except socket.timeout as e:
        logging.error(f"连接超时：{e}")
    except Exception as e:
        logging.error(f"获取证书信息时出错: {e}")
    return None

# 获取域名的到期时间
def get_domain_expiry_date(domain):
    try:
        w = whois.whois(domain)
        expiry_date = min(w.expiration_date) if isinstance(w.expiration_date, list) else w.expiration_date
        return expiry_date
    except Exception as e:
        logging.error(f"查询域名 {domain} 时出错: {e}")
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
            logging.info(f"成功发送通知给用户 {user_id}: {message}")
        else:
            logging.error(f"发送失败给用户 {user_id}，状态码: {response.status_code}")



# 检查证书的过期时间 (返回剩余天数)
def check_certificate_expiry(domain):
    expiry_date = get_certificate_expiry_date(domain)
    if expiry_date:
        days_left = (expiry_date - datetime.now()).days
        logging.info(f"域名: {domain} 证书剩余天数：{days_left}")
        return days_left
    return None

# 检查域名的到期时间 (返回剩余天数)
def check_domain_expiry(domain):
    expiry_date = get_domain_expiry_date(domain)
    if expiry_date:
        days_left = (expiry_date - datetime.now()).days
        logging.info(f"域名: {domain} 域名剩余天数：{days_left}")
        return days_left
    return None

# 定时执行任务的函数
def scheduled_task(config):
    # 获取域名列表
    domains = []
    if 'domains' in config:
        for key in config['domains']:
            domains.append(config['domains'][key])
            
    if not domains:
        logging.error("未找到有效的域名配置！")
        return

    logging.info("开始执行每日定时检查...")
    report_lines = ["📅 **域名与SSL证书到期日报**"]
    
    # 检查每个域名的到期时间和证书到期时间
    for domain in domains:
        if not domain:
            continue
        logging.info(f"检查域名: {domain}")
        
        domain_days = check_domain_expiry(domain)
        ssl_days = check_certificate_expiry(domain)
        
        report_lines.append(f"\n🌐 **{domain}**")
        
        if domain_days is not None:
             report_lines.append(f"  • 域名: 剩余 {domain_days} 天")
        else:
             report_lines.append(f"  • 域名: 获取失败 ❌")
             
        if ssl_days is not None:
             report_lines.append(f"  • SSL: 剩余 {ssl_days} 天")
        else:
             report_lines.append(f"  • SSL: 获取失败 ❌")

    full_report = "\n".join(report_lines)
    send_telegram_message(config, full_report)

# 主函数
def main():
    # 加载配置
    config = load_config()
    if config is None:
        return

    # 获取定时发送时间
    schedule_time = config.get('BOT', 'schedule_time', fallback='09:00')

    # 设置定时任务
    schedule.every().day.at(schedule_time).do(scheduled_task, config=config)
    logging.info(f"域名和证书到期监控程序已启动，每日定时发送时间: {schedule_time}")
    
    # 启动时立即执行一次（可选，方便测试）
    # scheduled_task(config)

    # 持续运行，定期执行任务
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("程序已停止")
