#!/bin/bash
# ============================================
# UniAPI Python 版自动部署脚本
# 适用服务器: api.ccbot.chat (OpenCloudOS 9)
# 用法: bash deploy.sh
# 前提: 已配置 SSH 免密登录
# ============================================
set -e

SSH_HOST="api.ccbot.chat"
SSH_USER="root"
REMOTE_DIR="/www/wwwroot/api.ccbot.chat"
OLD_GO_SERVICE="uniapi.service"  # 旧版 Go 的 systemd 服务名
PY_SERVICE="uniapi-py.service"   # Python 版 systemd 服务名

echo "========================================="
echo " UniAPI Python 版自动部署"
echo " 目标: $SSH_HOST:$REMOTE_DIR"
echo "========================================="

# ── 1. 构建前端 ──
echo ""
echo "[1/7] 构建前端..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/web"
yarn build
echo "  ✓ 前端构建完成"

# ── 生成版本文件（从 Git tag）──
VERSION=$(git describe --tags --dirty 2>/dev/null | sed 's/^v//')
echo "VERSION = \"${VERSION}\"" > "$SCRIPT_DIR/app/version.py"
echo "  ✓ 版本号: ${VERSION}"

# ── 2. 停止服务（防止 rsync --delete 误删 SQLite WAL/SHM）──
echo ""
echo "[2/7] 停止服务..."
ssh "$SSH_USER@$SSH_HOST" "systemctl stop $PY_SERVICE 2>/dev/null; sleep 1"
echo "  ✓ 服务已停止"

# ── 3. 同步文件到服务器 ──
echo ""
echo "[3/7] 同步代码到服务器..."
cd "$SCRIPT_DIR"

rsync -avz --delete --ignore-errors \
  --exclude '.venv' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude 'uniapi.db' \
  --exclude 'web/node_modules' \
  --exclude 'web/.yarn/cache' \
  --exclude 'web/src' \
  --exclude 'web/test-results' \
  --exclude 'web/playwright-report' \
  --exclude '.codegraph' \
  --exclude 'DeepSeek-Reasonix' \
  --exclude 'logs' \
  --exclude 'backups' \
  --exclude 'deploy.sh' \
  --exclude '.user.ini' \
  ./ "$SSH_USER@$SSH_HOST:$REMOTE_DIR/"
echo "  ✓ 代码同步完成"

# ── 4. 服务器环境初始化 ──
echo ""
echo "[4/7] 配置服务器环境..."

# 创建 logs 和 backups 目录
ssh "$SSH_USER@$SSH_HOST" "mkdir -p $REMOTE_DIR/logs $REMOTE_DIR/backups"

# 生成 version.py（服务器无 git tag，从 pyproject.toml 读取版本号）
VERSION=$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$SCRIPT_DIR/pyproject.toml" | head -1 || echo "0.0.0")
ssh "$SSH_USER@$SSH_HOST" "echo 'VERSION = \"${VERSION}\"' > $REMOTE_DIR/app/version.py"
echo "  ✓ version.py 已生成: ${VERSION}"

# 创建 .env（不覆盖已有配置）
# 首先生成本地随机 SECRET，再写入服务器
LOCAL_SECRET=$(openssl rand -hex 32)
ssh "$SSH_USER@$SSH_HOST" "test -f $REMOTE_DIR/.env || cat > $REMOTE_DIR/.env << ENVEOF
# Server
SERVER_PORT=3000
DEBUG=false

# Database ── 绝对路径防错
SQLITE_PATH=$REMOTE_DIR/uniapi.db
SQL_DSN=

# Session（首次部署自动生成，不修改已有配置）
SESSION_SECRET=$LOCAL_SECRET
COOKIE_MAX_AGE_HOURS=168

# Token
TOKEN_KEY_PREFIX=sk-

# Rate limits
API_RATE_LIMIT=480
RELAY_RATE_LIMIT=480

# Provider API keys ── 渠道必须单独设置 Key
DEEPSEEK_API_KEY=
GLM_API_KEY=
QWEN_API_KEY=
KIMI_API_KEY=
MINIMAX_API_KEY=

# Budget (disabled)
BUDGET_REDIS_URL=
BUDGET_ENABLED=false
DEFAULT_MONTHLY_BUDGET=800.0
ENVEOF
"
echo "  ✓ .env 已就绪"

# 创建 Python 虚拟环境
ssh "$SSH_USER@$SSH_HOST" "test -d $REMOTE_DIR/.venv || python3 -m venv $REMOTE_DIR/.venv"
ssh "$SSH_USER@$SSH_HOST" "cd $REMOTE_DIR && source .venv/bin/activate && pip install -e . -q"
echo "  ✓ Python 依赖安装完成"

# 权限设置：跳过宝塔面板的 .user.ini（带 immutable 属性）
ssh "$SSH_USER@$SSH_HOST" "
		find $REMOTE_DIR -not -name '.user.ini' -exec chown root:www {} + 2>/dev/null
		find $REMOTE_DIR -not -name '.user.ini' -exec chmod 750 {} + 2>/dev/null
		chmod -R 770 $REMOTE_DIR/logs $REMOTE_DIR/backups 2>/dev/null
	"
echo "  ✓ 权限设置完成"

# ── 5. Nginx SSE 性能优化（堡塔 extension 目录，面板不覆盖） ──
echo ""
echo "[5/7] 配置 Nginx SSE 参数..."
NGINX_SSE_CONF="/www/server/panel/vhost/nginx/extension/api.ccbot.chat/proxy_sse.conf"
ssh "$SSH_USER@$SSH_HOST" "test -f $NGINX_SSE_CONF || cat > $NGINX_SSE_CONF << 'NGINXEOF'
# UniAPI SSE streaming optimization
# 部署脚本自动生成，首次创建后不再覆盖，可手动修改此文件
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 300s;
proxy_send_timeout 60s;
client_max_body_size 16m;
NGINXEOF
"
# 如果文件是新创建的，重载 Nginx
ssh "$SSH_USER@$SSH_HOST" "test -f $NGINX_SSE_CONF && nginx -t && nginx -s reload" 2>/dev/null && echo "  ✓ Nginx 配置已就绪" || true
echo "  → 配置文件: $NGINX_SSE_CONF"
echo "  → 说明: 首次部署自动创建，后续部署不覆盖，可手动修改"

# ── 6. 配置 systemd 服务 ──
echo ""
echo "[6/7] 配置系统服务..."
ssh "$SSH_USER@$SSH_HOST" "cat > /etc/systemd/system/$PY_SERVICE << 'UNITEOF'
[Unit]
Description=UniAPI Python Backend
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$REMOTE_DIR
ExecStart=$REMOTE_DIR/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 3000
Restart=always
RestartSec=5
StandardOutput=append:$REMOTE_DIR/logs/access.log
StandardError=append:$REMOTE_DIR/logs/error.log
EnvironmentFile=$REMOTE_DIR/.env
ExecStopPost=/bin/sleep 1

[Install]
WantedBy=multi-user.target
UNITEOF
"
echo "  ✓ systemd 服务配置完成"

# ── 7. 启动服务 ──
echo ""
echo "[7/7] 启动服务..."

# 停止旧版 Go 服务（如果存在且与新版端口冲突）
OLD_RUNNING=$(ssh "$SSH_USER@$SSH_HOST" "systemctl is-active $OLD_GO_SERVICE 2>/dev/null || echo inactive")
if [ "$OLD_RUNNING" = "active" ]; then
    echo "  检测到旧版 Go 服务，停止中..."
    # 检查 Go 版是否在使用同样的端口
    OLD_PORT=$(ssh "$SSH_USER@$SSH_HOST" "cat /etc/systemd/system/$OLD_GO_SERVICE 2>/dev/null | grep -oP '(?<=--port )\d+' || echo 3000")
    if [ "$OLD_PORT" = "3000" ]; then
        ssh "$SSH_USER@$SSH_HOST" "systemctl stop $OLD_GO_SERVICE && systemctl disable $OLD_GO_SERVICE"
        echo "  ✓ 旧版 Go 服务已停止"
    fi
fi

# 启动新版 Python 服务
ssh "$SSH_USER@$SSH_HOST" "systemctl daemon-reload && systemctl enable $PY_SERVICE && systemctl restart $PY_SERVICE"
sleep 3

# ── 验证 ──
echo ""
echo "验证服务状态..."
HEALTH=$(ssh "$SSH_USER@$SSH_HOST" "curl -s http://127.0.0.1:3000/health" 2>/dev/null || echo "失败")
echo "  Health: $HEALTH"

PY_STATUS=$(ssh "$SSH_USER@$SSH_HOST" "systemctl is-active $PY_SERVICE" 2>/dev/null)
echo "  服务状态: $PY_STATUS"

echo ""
echo "========================================="
echo " 部署完成！"
echo " 前端: https://api.ccbot.chat"
echo " API:  https://api.ccbot.chat/v1"
echo " 日志: $REMOTE_DIR/logs/"
echo " Nginx SSE: 已自动配置（extension/proxy_sse.conf）"
echo "========================================="