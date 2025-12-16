#!/bin/bash

# ================= 配置区域 =================
# Git 源码目录 (请修改为您服务器上的实际路径)
SRC_DIR="/data/git/Domain_expiry_monitor"

# 部署运行目录 (请修改为您服务器上的实际路径)
DEST_DIR="/data/bin/domain_monitor"

# 虚拟环境目录 (默认在部署目录下)
VENV_DIR="$DEST_DIR/.venv"

# 主程序文件名
MAIN_SCRIPT="domain_expiry_monitor.py"
# ===========================================

echo "🚀 开始部署流程..."

# 1. 更新代码
echo "📂 切换到源码目录: $SRC_DIR"
if [ -d "$SRC_DIR" ]; then
    cd "$SRC_DIR" || { echo "❌ 无法进入目录 $SRC_DIR"; exit 1; }
    echo "🔄 执行 git pull..."
    git pull
else
    echo "❌ 源码目录不存在: $SRC_DIR"
    exit 1
fi

# 2. 同步文件
# 将必要的文件同步到运行目录，排除 git 目录和缓存文件
echo "📤 同步文件到运行目录: $DEST_DIR"
mkdir -p "$DEST_DIR"
rsync -av \
  --include='*/' \
  --include='*.py' \
  --include='*.ini' \
  --include='*.txt' \
  --include='*.md' \
  --exclude='.*' \
  --exclude='__pycache__' \
  --exclude='venv' \
  --delete \
  "$SRC_DIR/" "$DEST_DIR/"

# 3. 环境配置与依赖安装
echo "🔧 检查 Python 虚拟环境..."
cd "$DEST_DIR" || exit

if [ ! -d "$VENV_DIR" ]; then
    echo "creation 正在创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

echo "🔌 激活虚拟环境并更新依赖..."
source "$VENV_DIR/bin/activate"
pip install -r requirements.txt

# 4. Systemd 服务配置与重启
SERVICE_NAME="domain-monitor.service"
SYSTEMD_PATH="/etc/systemd/system/$SERVICE_NAME"

echo "� 检查 Systemd 服务配置..."

# 检查是否已有服务文件
if [ ! -f "$SYSTEMD_PATH" ]; then
    echo "⚠️ 服务文件不存在，正在生成配置..."
    
    # 获取当前用户 (如果使用 sudo 执行，可能是 root，建议指定运行用户)
    # 这里默认使用当前执行脚本的用户，但在 sudo 下往往需要小心
    # 我们假设用户以非 root 身份运行 sudo ./deploy.sh 或者拥有 sudo 权限
    
    RUN_USER=$SUDO_USER
    if [ -z "$RUN_USER" ]; then
        RUN_USER=$(whoami)
    fi

    echo "� 运行用户: $RUN_USER"
    echo "🐍 Python 路径: $VENV_DIR/bin/python"

    # 生成临时 service 文件
    cat > temporary_service.service <<EOF
[Unit]
Description=Domain Expiry Monitor Bot
After=network.target

[Service]
ExecStart=$VENV_DIR/bin/python $DEST_DIR/$MAIN_SCRIPT
WorkingDirectory=$DEST_DIR
User=$RUN_USER
Restart=always
RestartSec=5
StandardOutput=append:$DEST_DIR/log.log
StandardError=append:$DEST_DIR/error.log

[Install]
WantedBy=multi-user.target
EOF

    echo "📥 安装服务文件到 /etc/systemd/system/..."
    sudo mv temporary_service.service "$SYSTEMD_PATH"
    
    echo "🔄 重载 Systemd 守护进程..."
    sudo systemctl daemon-reload
    
    echo "✅ 设置开机自启..."
    sudo systemctl enable "$SERVICE_NAME"
    
    echo "▶️ 启动服务..."
    sudo systemctl start "$SERVICE_NAME"
else
    echo "🔄 服务已存在，正在重启..."
    sudo systemctl restart "$SERVICE_NAME"
fi

echo "✅ 部署完成！"
echo "你可以使用以下命令查看状态："
echo "  sudo systemctl status $SERVICE_NAME"
echo "  tail -f $DEST_DIR/log.log"
