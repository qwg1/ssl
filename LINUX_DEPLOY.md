# Linux 部署指南

## 快速开始

### 1. 克隆项目

```bash
# 克隆项目到服务器
git clone https://github.com/qwg1/ssl.git
cd ssl
```

### 2. 配置文件

创建配置文件 `config/config.ini`：

```bash
mkdir -p config
nano config/config.ini
```

填入以下内容：

```ini
[BOT]
BOT_TOKEN = your_bot_token_here
schedule_time = 09:00

[admins]
admin_user_ids = 12345678

[domains]
domain1 = example.com
domain2 = google.com
```

### 3. 手动运行（测试）

```bash
# 安装 Python 3 和 pip
sudo apt update
sudo apt install python3 python3-pip python3-venv -y

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行程序
python domain_expiry_monitor.py
```

按 `Ctrl+C` 停止程序。

---

## 自动部署（推荐）

使用 `deploy.sh` 脚本自动部署为系统服务。

### 前置准备

1. **创建运行用户**（推荐使用非 root 用户）：

```bash
sudo useradd -r -s /bin/bash botuser
```

2. **修改 `deploy.sh` 配置**：

打开 `deploy.sh`，修改以下配置：

```bash
# Git 源码目录（你 clone 项目的位置）
SRC_DIR="/root/ssl"

# 部署运行目录（服务实际运行的位置）
DEST_DIR="/data/bin/sslbot"

# 运行用户
RUN_USER="botuser"
```

### 执行部署

```bash
# 给脚本执行权限
chmod +x deploy.sh

# 运行部署脚本
./deploy.sh
```

脚本会自动：
- ✅ 拉取最新代码
- ✅ 同步文件到运行目录
- ✅ 创建虚拟环境并安装依赖
- ✅ 生成并安装 systemd 服务
- ✅ 启动服务并设置开机自启

### 管理服务

```bash
# 查看服务状态
sudo systemctl status sslbot.service

# 查看实时日志
sudo journalctl -xeu sslbot.service -f

# 停止服务
sudo systemctl stop sslbot.service

# 启动服务
sudo systemctl start sslbot.service

# 重启服务
sudo systemctl restart sslbot.service

# 禁用开机自启
sudo systemctl disable sslbot.service
```

---

## 更新代码

当你更新了 GitHub 代码后，在服务器上运行：

```bash
cd /root/ssl  # 你的源码目录
./deploy.sh
```

脚本会自动拉取最新代码并重启服务。

---

## 故障排查

### 1. 服务无法启动

```bash
# 查看详细错误日志
sudo journalctl -xeu sslbot.service --no-pager

# 检查配置文件是否存在
ls -la /data/bin/sslbot/config/config.ini
```

### 2. 依赖安装失败

```bash
# 手动进入虚拟环境安装
cd /data/bin/sslbot
sudo -u botuser /bin/bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 权限问题

```bash
# 确保运行目录权限正确
sudo chown -R botuser:botuser /data/bin/sslbot
```

### 4. Python 版本问题

```bash
# 检查 Python 版本（需要 3.x）
python3 --version

# 如果版本过低，升级 Python
sudo apt install python3.9 -y
```

---

## 完整部署示例

```bash
# 1. 安装系统依赖
sudo apt update
sudo apt install git python3 python3-pip python3-venv -y

# 2. 创建运行用户
sudo useradd -r -s /bin/bash botuser

# 3. 克隆项目
cd /root
git clone https://github.com/qwg1/ssl.git
cd ssl

# 4. 配置 config.ini
mkdir -p config
nano config/config.ini
# （填入你的配置）

# 5. 修改 deploy.sh 配置
nano deploy.sh
# 修改 SRC_DIR="/root/ssl"

# 6. 执行部署
chmod +x deploy.sh
./deploy.sh

# 7. 查看状态
sudo systemctl status sslbot.service
sudo journalctl -xeu sslbot.service -f
```

---

## 注意事项

⚠️ **配置文件不会被同步**：`config/config.ini` 需要在运行目录手动创建：

```bash
sudo mkdir -p /data/bin/sslbot/config
sudo nano /data/bin/sslbot/config/config.ini
sudo chown -R botuser:botuser /data/bin/sslbot/config
```

⚠️ **防火墙**：确保服务器可以访问 Telegram API（可能需要代理）。

⚠️ **时区**：确保服务器时区正确，影响定时发送时间：

```bash
# 查看时区
timedatectl

# 设置时区（例如上海）
sudo timedatectl set-timezone Asia/Shanghai
```
