#!/usr/bin/env bash
# 安装 a-stock-data 到 data-sources
# 运行: bash e:/work/stock/data-sources/install_a_stock_data.sh
set -e
cd e:/work/stock/data-sources
rm -rf a-stock-data 2>/dev/null || true
echo "正在克隆 a-stock-data..."
git clone https://github.com/simonlin1212/a-stock-data.git
echo "安装依赖..."
pip install mootdx requests pandas stockstats
echo "✅ a-stock-data 安装完成"
ls -la a-stock-data/
