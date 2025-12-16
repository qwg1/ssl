# Domain Expiry Monitor

一个用于监控域名和 SSL 证书过期时间的 Python 脚本。它会每天通过 Telegram Bot 发送包含所有监控域名剩余天数的日报。

## 功能

- **每日日报**: 每天定时（默认 09:00）发送所有域名的到期倒计时。
- **SSL 检查**: 自动检查 HTTPS 证书的有效期。
- **域名 Whois**: 自动查询域名的注册到期时间。
- **Telegram 通知**: 通过 Bot 发送格式化的报告。

## 环境要求

- Python 3.x
- 依赖库: `requirements.txt`

## 安装与配置

1.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```

2.  **配置 `config/config.ini`**
    
    修改配置文件以填入你的 Bot Token、管理员 ID 和需要监控的域名。

    ```ini
    [BOT]
    BOT_TOKEN = your_bot_token_here
    schedule_time = 09:00  # 每天发送报告的时间 (24小时制)

    [admins]
    admin_user_ids = 12345678, 87654321

    [domains]
    # 可以添加任意数量的域名，key 名字不重要，只要唯一即可
    domain1 = example.com
    domain2 = google.com
    my_blog = myblog.net
    ```

## 运行

直接运行脚本即可：

```bash
python domain_expiry_monitor.py
```

## Linux 一键部署 (推荐)

使用 `deploy.sh` 脚本可以在 Linux 服务器上自动完成代码拉取、环境配置、服务安装和启动。

1.  **修改脚本配置**:
    打开 `deploy.sh`，修改顶部的 `SRC_DIR` (源码目录) 和 `DEST_DIR` (安装目录)。

2.  **运行脚本**:
    ```bash
    chmod +x deploy.sh
    ./deploy.sh
    ```

    脚本会自动：
    - 拉取 Git 最新代码
    - 同步文件到运行目录
    - 创建/更新 Python 虚拟环境
    - **自动生成并安装 Systemd 服务** (`domain-monitor.service`)
    - 启动或重启服务

3.  **查看状态**:
    ```bash
    sudo systemctl status domain-monitor.service
    tail -f /path/to/install/dir/log.log
    ```
