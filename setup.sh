#!/bin/bash
set -e

PROJ=/root/kabu-trader

echo "=== 株AI仮想取引ダッシュボード セットアップ ==="

# venv 作成
python3 -m venv "$PROJ/venv"
echo "[OK] venv 作成"

# パッケージインストール
"$PROJ/venv/bin/pip" install --upgrade pip -q
"$PROJ/venv/bin/pip" install -r "$PROJ/requirements.txt" -q
echo "[OK] パッケージインストール完了"

# データディレクトリ
mkdir -p "$PROJ/data"
echo "[OK] data ディレクトリ確認"

# .env ファイル
if [ ! -f "$PROJ/.env" ]; then
    cp "$PROJ/.env.example" "$PROJ/.env"
    echo "[INFO] .env.example を .env にコピーしました。APIキーを設定してください:"
    echo "       nano $PROJ/.env"
else
    echo "[OK] .env 既存"
fi

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "次のステップ:"
echo "  1. APIキーを設定: nano $PROJ/.env"
echo "  2. SSL証明書取得: bash $PROJ/ssl-setup-kabu.sh"
echo "  3. nginx 有効化: sudo ln -s /etc/nginx/sites-available/kabu-trader /etc/nginx/sites-enabled/"
echo "  4. nginx リロード: sudo nginx -t && sudo systemctl reload nginx"
echo "  5. サービス起動: sudo systemctl enable --now kabu-trader"
echo ""
echo "  手動起動テスト: $PROJ/venv/bin/streamlit run $PROJ/app.py"
