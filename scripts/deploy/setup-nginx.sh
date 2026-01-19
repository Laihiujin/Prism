#!/bin/bash
# SynapseAutomation Nginx 配置检查脚本

set -e

NGINX_CONF="./nginx.conf"
DOMAIN="${1:-your-domain.com}"

echo "=========================================="
echo "Nginx 配置检查"
echo "=========================================="
echo ""

# 检查 Nginx 是否安装
if ! command -v nginx &> /dev/null; then
    echo "[✗] Nginx 未安装"
    echo "请安装 Nginx:"
    echo "  Ubuntu/Debian: sudo apt-get install nginx"
    echo "  CentOS/RHEL: sudo yum install nginx"
    exit 1
fi

echo "[✓] Nginx 已安装"
nginx -v

# 检查配置文件
if [ ! -f "$NGINX_CONF" ]; then
    echo "[✗] 找不到 $NGINX_CONF"
    exit 1
fi

echo "[✓] 配置文件存在"

# 测试 Nginx 配置
echo ""
echo "正在测试配置文件..."
if sudo nginx -t -c "$(pwd)/$NGINX_CONF"; then
    echo "[✓] 配置文件语法正确"
else
    echo "[✗] 配置文件有错误"
    exit 1
fi

# 替换域名
echo ""
echo "正在更新域名配置..."
if [ "$DOMAIN" != "your-domain.com" ]; then
    sudo sed -i "s/your-domain\.com/$DOMAIN/g" "$NGINX_CONF"
    echo "[✓] 域名已更新为: $DOMAIN"
fi

# 配置 Let's Encrypt (可选)
echo ""
echo "是否需要配置 SSL 证书? (y/n)"
read -r response

if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
    if ! command -v certbot &> /dev/null; then
        echo "[!] 需要安装 certbot"
        echo "Ubuntu/Debian: sudo apt-get install certbot python3-certbot-nginx"
        echo "CentOS/RHEL: sudo yum install certbot python3-certbot-nginx"
        exit 1
    fi
    
    echo ""
    echo "正在配置 Let's Encrypt 证书..."
    sudo certbot certonly --nginx -d "$DOMAIN" -d "www.$DOMAIN"
    echo "[✓] 证书配置完成"
fi

# 重启 Nginx
echo ""
echo "是否重启 Nginx? (y/n)"
read -r response

if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
    sudo systemctl restart nginx
    echo "[✓] Nginx 已重启"
    sudo systemctl status nginx
fi

echo ""
echo "=========================================="
echo "✓ Nginx 配置完成"
echo "=========================================="
echo ""
echo "访问地址:"
echo "  前端: https://$DOMAIN"
echo "  后端: https://$DOMAIN/api/"
echo ""
