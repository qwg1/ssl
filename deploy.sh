#!/bin/bash

# ============================ ⚙️ 配置区域 (请根据项目修改) =============================

# 1. Git 源码目录 (服务器上存放 Git clone 的路径)
SRC_DIR="/data/git/ssl_monitor/domain_expiry_monitor"

# 2. 部署运行目录 (服务实际运行代码的路径)
DEST_DIR="/data/bin/sslbot"

# 3. 服务的运行用户 (!!! 必须是非 root 系统用户，推荐: botuser, www-data)
RUN_USER="botuser"

# 4. 主程序文件名 (如: main.py, app.py)
MAIN_SCRIPT="domain_expiry_monitor.py"

# 5. systemd 服务名 (短命 oneshot, 每天触发一次)
SERVICE_NAME="sslbot.service"

# 6. systemd 定时器名 (驱动 service 每天定时跑)
TIMER_NAME="sslbot.timer"

# 7. 每天定时推送时间 (HH:MM, 24h 制)
SCHEDULE_TIME="12:00"

# 8. 部署时排除的文件/目录 (rsync --exclude, 用空格分隔)
# 默认排除: 文档/.git/虚拟环境/IDE/缓存/部署脚本本身
EXCLUDES=".venv .git .idea __pycache__ *.pyc log.log test.py deploy.sh LINUX_DEPLOY.md README.md .gitignore .DS_Store launchd.err launchd.log"

# ============================ ⚡️ 核心执行区域 (无需修改) ============================

VENV_DIR="$DEST_DIR/.venv"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"
TIMER_PATH="/etc/systemd/system/$TIMER_NAME"

echo "🚀 开始部署 SSL/Domain 过期监控推送 (User: $RUN_USER, Service: $SERVICE_NAME, Timer: $TIMER_NAME @ $SCHEDULE_TIME)..."

# --- 1. 前置检查与环境初始化 ---
if ! id "$RUN_USER" &>/dev/null; then
    echo "👤 运行用户 '$RUN_USER' 不存在, 自动创建..."
    sudo useradd -r -s /bin/bash -d "$DEST_DIR" -m "$RUN_USER"
fi

if [ ! -d "$SRC_DIR" ]; then
    echo "❌ 错误: 源码目录不存在: $SRC_DIR"
    exit 1
fi

# 确保目标目录存在
sudo mkdir -p "$DEST_DIR"
sudo chown -R "$RUN_USER":"$RUN_USER" "$DEST_DIR"


# --- 2. 代码拉取与同步 ---
echo "🔄 git pull..."
cd "$SRC_DIR" || exit 1
sudo -u "$RUN_USER" git pull 2>&1 | tail -3

echo "📤 rsync 到 $DEST_DIR (排除: $EXCLUDES)..."
# 简化规则: 只用 --exclude, 不玩 include/exclude 混合 (容易踩坑)
# 把 EXCLUDES 列表展开成多个 --exclude 参数
EXCLUDE_ARGS=""
for item in $EXCLUDES; do
    EXCLUDE_ARGS="$EXCLUDE_ARGS --exclude=$item"
done
sudo -u "$RUN_USER" rsync -av $EXCLUDE_ARGS "$SRC_DIR/" "$DEST_DIR/"


# --- 3. 虚拟环境与依赖安装 ---
cd "$DEST_DIR" || exit 1

sudo -u "$RUN_USER" /bin/bash << EOF
set -e
echo "🔌 进入 $RUN_USER 权限环境安装依赖..."

if [ ! -d "$VENV_DIR" ]; then
    echo "creation 正在创建虚拟环境..."
    /usr/bin/python3 -m venv "$VENV_DIR" || { echo "❌ 虚拟环境创建失败 (是否装了 python3-venv?)"; exit 1; }
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip >/dev/null

if [ -f "requirements.txt" ]; then
    echo "✅ 安装 requirements.txt ..."
    pip install -r requirements.txt
else
    echo "❌ 严重错误: requirements.txt 不在 $DEST_DIR (rsync 没同步上?)"
    exit 1
fi

deactivate
echo "🎉 依赖环境配置完成。"
EOF


# --- 4. Systemd Service (短命 oneshot, 跑完即退出) ---
echo "⚙️ 写入 $SERVICE_NAME (Type=oneshot, Restart=no)..."

# oneshot + Restart=no: 防止死亡螺旋 (脚本 main() 已是"单次执行 + sys.exit(0)" 模式)
# 每天由 $TIMER_NAME 触发一次, 跑完即退出, 不常驻不重启
cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=$SERVICE_NAME Daemon (daily one-shot SSL/Domain report)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$DEST_DIR
User=$RUN_USER
Group=$RUN_USER
ExecStart=$VENV_DIR/bin/python $DEST_DIR/$MAIN_SCRIPT
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal
Restart=no

[Install]
WantedBy=multi-user.target
EOF


# --- 5. Systemd Timer (每天 SCHEDULE_TIME 触发 service) ---
echo "⏰ 写入 $TIMER_NAME (OnCalendar=*-*-* $SCHEDULE_TIME:00)..."

cat > "$TIMER_PATH" <<EOF
[Unit]
Description=Daily $SCHEDULE_TIME SSL/Domain expiry report

[Timer]
# 服务器时区已是 Asia/Shanghai (CST), OnCalendar 用本地时间表达
OnCalendar=*-*-* $SCHEDULE_TIME:00
# Persistent=true 让睡眠/关机期间错过的 tick 在唤醒时补跑一次
Persistent=true
# 容忍 30s 漂移
AccuracySec=30s
Unit=$SERVICE_NAME

[Install]
WantedBy=timers.target
EOF


# --- 6. 重载并启用 Timer ---
echo "🔄 重载 systemd..."
sudo systemctl daemon-reload

echo "✅ 设置 $TIMER_NAME 开机自启..."
sudo systemctl enable "$TIMER_NAME"

echo "▶️ 启动 $TIMER_NAME..."
sudo systemctl restart "$TIMER_NAME"

echo ""
echo "✅ 部署完成！"
echo ""
echo "--- 当前 Timer 状态 ---"
sudo systemctl list-timers "$TIMER_NAME" --no-pager
echo ""
echo "--- 调试命令 ---"
echo "  sudo systemctl status $SERVICE_NAME $TIMER_NAME --no-pager"
echo "  sudo journalctl -u $SERVICE_NAME -n 80 --no-pager"
echo "  sudo journalctl -u $TIMER_NAME -n 20 --no-pager"
echo ""
echo "--- 手动立即触发一次 (不等到 $SCHEDULE_TIME) ---"
echo "  sudo systemctl start $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
