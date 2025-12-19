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

# 5. systemd 服务名 (如: my-api.service, my-bot.service)
SERVICE_NAME="sslbot.service"

# 6. 其他配置目录/文件 (rsync 时需要同步的非 Python 文件, 用空格分隔)
CONFIG_FILES="requirements.txt config.ini .env"

# ============================ ⚡️ 核心执行区域 (无需修改) ============================

VENV_DIR="$DEST_DIR/.venv"

echo "🚀 开始通用 Python 部署流程 (User: $RUN_USER, Service: $SERVICE_NAME)..."

# --- 1. 前置检查与环境初始化 ---
# 检查运行用户是否存在
if ! id "$RUN_USER" &>/dev/null; then
    echo "❌ 错误: 运行用户 '$RUN_USER' 不存在。请先创建该用户: sudo useradd -r $RUN_USER"
    exit 1
fi

# 检查源码目录
if [ ! -d "$SRC_DIR" ]; then
    echo "❌ 错误: 源码目录不存在: $SRC_DIR"
    exit 1
fi

# 确保目标目录存在，并设置正确的权限
echo "📂 创建目标目录并修正权限..."
sudo mkdir -p "$DEST_DIR"
sudo chown -R "$RUN_USER":"$RUN_USER" "$DEST_DIR"


# --- 2. 代码拉取与同步 ---
echo "🔄 切换到源码目录并执行 git pull..."
cd "$SRC_DIR" || exit 1
git pull

echo "📤 同步核心文件到运行目录: $DEST_DIR"
# 使用非 root 身份执行 rsync，确保同步的文件权限正确
sudo -u "$RUN_USER" rsync -av \
  --include='*/' \
  --include='*.py' \
  $(for file in $CONFIG_FILES; do echo "--include='$file'"; done) \
  --exclude='*' \
  --delete \
  "$SRC_DIR/" "$DEST_DIR/"


# --- 3. 虚拟环境与依赖安装 (使用 RUN_USER 权限) ---
cd "$DEST_DIR" || exit 1

# 使用 HERE document 和 sudo -u 来确保所有操作都在 RUN_USER 权限下执行
sudo -u "$RUN_USER" /bin/bash << EOF
echo "🔌 正在进入 $RUN_USER 权限环境安装依赖..."

# 检查并创建虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "creation 正在创建虚拟环境..."
    /usr/bin/python3 -m venv "$VENV_DIR" || { echo "❌ 虚拟环境创建失败，请检查 python3 是否安装!"; exit 1; }
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 确保 pip 版本最新 (解决版本过旧问题)
echo "↑ 升级 pip..."
pip install --upgrade pip

# 安装依赖 (核心校验和错误处理)
if [ -f "requirements.txt" ]; then
    echo "✅ 正在安装 requirements.txt 中的依赖..."
    
    pip install -r requirements.txt
    INSTALL_STATUS=$?
    
    if [ $INSTALL_STATUS -ne 0 ]; then
        # 依赖安装失败，给出详细的故障排除提示
        echo "=========================================================="
        echo "❌ 严重错误: Python 依赖安装失败 (退出码 $INSTALL_STATUS)"
        echo "🚨 请根据以上错误日志检查以下常见问题:"
        echo "1. **版本兼容性**: 您的 Python 版本是 \$(python -V)，请检查 requirements.txt 中是否有版本（如 requests==2.28.1）与此版本不兼容。"
        echo "2. **网络连接**: 检查服务器能否访问 PyPI 或自定义镜像源。"
        echo "3. **系统依赖**: 某些库需要系统级别的 C 库或头文件 (如 gcc, python3-devel)。"
        echo "=========================================================="
        deactivate
        exit 1 # 立即退出整个部署脚本
    fi
    
    echo "🎉 依赖安装成功。"
else
    echo "⚠️ 警告: 未找到 requirements.txt 文件，跳过依赖安装。"
fi

deactivate
echo "🎉 依赖环境配置完成。"
EOF


# --- 4. Systemd 服务配置与重启 ---
SYSTEMD_PATH="/etc/systemd/system/$SERVICE_NAME"

echo "⚙️ 检查/生成 Systemd 服务配置..."

# 生成服务文件内容
cat > temporary_service.service <<EOF
[Unit]
Description=$SERVICE_NAME Daemon
After=network.target

[Service]
ExecStart=$VENV_DIR/bin/python $DEST_DIR/$MAIN_SCRIPT
WorkingDirectory=$DEST_DIR
User=$RUN_USER         
Group=$RUN_USER        
# 进程退出非零代码时重启
Restart=on-failure
RestartSec=5
# 限制在 60 秒内最多重启 5 次，防止崩溃死循环
StartLimitIntervalSec=60
StartLimitBurst=5
# 将日志导入 systemd 日志系统 (推荐)
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "📥 安装服务文件到 /etc/systemd/system/..."
sudo mv temporary_service.service "$SYSTEMD_PATH"
    
echo "🔄 重载 Systemd 守护进程..."
sudo systemctl daemon-reload
    
echo "✅ 设置开机自启..."
sudo systemctl enable "$SERVICE_NAME"
    
echo "▶️ 启动/重启服务..."
sudo systemctl restart "$SERVICE_NAME"

echo "✅ 部署完成！"
echo "--- 调试命令 ---"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo journalctl -xeu $SERVICE_NAME -f"
echo "你可以使用以下命令查看状态："
echo "  sudo systemctl status $SERVICE_NAME"
echo "  tail -f $DEST_DIR/log.log"
