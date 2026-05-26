#!/bin/bash
set -e

DOMAIN="kabu.1qaz.jp"
EMAIL="${LETSENCRYPT_EMAIL:?set LETSENCRYPT_EMAIL env var}"

echo "=== SSL証明書取得: $DOMAIN ==="

# nginx で HTTP-only 設定を一時的に使い、certbot で証明書取得
# nginx の設定は sites-available/kabu-trader を有効化してから実行する

# 事前チェック
if ! command -v certbot &>/dev/null; then
    echo "certbot をインストールしています..."
    apt-get install -y certbot python3-certbot-nginx
fi

# 証明書取得
certbot certonly \
    --webroot \
    --webroot-path /var/www/certbot \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive

echo ""
echo "=== 証明書取得完了 ==="
echo "証明書パス: /etc/letsencrypt/live/$DOMAIN/"
echo ""
echo "次のステップ:"
echo "  nginx -t && systemctl reload nginx"
