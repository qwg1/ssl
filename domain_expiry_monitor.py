import whois
import ssl
import socket
import sys
import os
from datetime import datetime
import requests
import configparser
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
    # 优先环境变量，其次 config.ini（环境变量不写文件，重启服务器不丢）
    enabled = config.getboolean('BOT', 'telegram_report', fallback=True)
    if not enabled:
        logging.info("Telegram 推送已关闭 (telegram_report=false)，跳过发送")
        return
    bot_token = os.environ.get('BOT_TOKEN') or config['BOT']['BOT_TOKEN']
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


# 写报告到桌面 .txt (按日期倒序追加, 新条目在最上面)
def write_desktop_report(config, message):
    enabled = config.getboolean('BOT', 'desktop_report', fallback=True)
    if not enabled:
        return
    try:
        desktop_dir = os.path.expanduser('~/Desktop')
        os.makedirs(desktop_dir, exist_ok=True)
        date_str = datetime.now().strftime('%Y%m%d')
        out_path = os.path.join(desktop_dir, f'domain_expiry_report_{date_str}.txt')

        # 新条目: 完整内容,带时间戳头 + 分隔线
        new_entry = (
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{'=' * 50}\n"
            f"{message}\n"
        )

        if os.path.exists(out_path):
            # 已存在: 倒序追加(新条目写最前, 历史内容往后挪)
            with open(out_path, 'r', encoding='utf-8') as f:
                old_content = f.read()
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(new_entry)
                f.write("\n")  # 新旧之间多空一行
                f.write(old_content)
            logging.info(f"桌面报告已追加(倒序): {out_path}")
        else:
            # 不存在: 创建
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(new_entry)
            logging.info(f"桌面报告已创建: {out_path}")
    except Exception as e:
        logging.error(f"写桌面报告失败: {e}")



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
    write_desktop_report(config, full_report)

# 启动时验证 token 是否有效（防止拿到坏 token 还傻跑）
def verify_bot_token(config):
    bot_token = os.environ.get('BOT_TOKEN') or config['BOT']['BOT_TOKEN']
    try:
        r = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get('ok'):
                username = data['result'].get('username', 'unknown')
                logging.info(f"✅ Bot 验证通过: @{username}")
                return True
        logging.error(f"❌ Bot token 验证失败: HTTP {r.status_code} {r.text[:200]}")
        return False
    except Exception as e:
        logging.error(f"❌ Bot token 验证异常: {e}")
        return False

# 主函数 — 单次执行模式 (由 launchd StartCalendarInterval 每天触发一次)
# 替代之前的 schedule 常驻循环 + KeepAlive 方案:
# - 进程只在定时点启动, 跑完 scheduled_task 立刻 sys.exit(0)
# - 无 schedule / time.sleep 常驻, 无 KeepAlive 重启风暴
# - DNS / TG 临时不可达只会让当天报告失败, 不影响明天 + 桌面文件独立落地
def main():
    # 加载配置
    config = load_config()
    if config is None:
        sys.exit(1)

    # 验证 token 有效性（失败仅 warn，不退出）
    # 原因：DNS 偶发不通 / TG 临时不可达时, 如果 exit(1) + launchd KeepAlive 会形成死亡螺旋。
    #       当前方案用 StartCalendarInterval 不存在 KeepAlive, 但保持 warn 仍然安全:
    #       即使 token 失效, 桌面报告照常落地 (核心价值), TG 推送失败不影响。
    if not verify_bot_token(config):
        logging.warning("⚠️ token 验证失败, 但继续运行 (桌面报告不受影响, TG 推送会失败)")

    # 跑一次任务, 然后退出 (由 launchd 第二天再次触发)
    scheduled_task(config)
    logging.info("✅ 单次任务完成, 进程退出")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("程序已停止")