#!/usr/bin/env python3
"""
国際化システム拡張機能テストスクリプト
"""

import sys
import os

# パスを設定
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    # まずモジュールの構文チェック
    import ast

    # 国際化モジュールのパス
    i18n_file = os.path.join(os.path.dirname(__file__), 'src', 'moni', 'internationalization.py')

    # ファイルが存在するかチェック
    if not os.path.exists(i18n_file):
        print(f"❌ 国際化ファイルが見つかりません: {i18n_file}")
        sys.exit(1)

    # ファイルサイズチェック
    file_size = os.path.getsize(i18n_file)
    print(f"📁 国際化ファイルサイズ: {file_size} bytes")

    # ファイルの最後の部分を確認
    with open(i18n_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f"📝 総行数: {len(lines)}")

        # 最後の20行を表示
        print("\n📋 ファイルの最後の部分:")
        for i, line in enumerate(lines[-20:], len(lines)-19):
            print(f"{i"4d"}: {line.rstrip()}")

    print("\n🎉 ファイル構造確認完了！")

except Exception as e:
    print(f"❌ エラー: {e}")
    import traceback
    traceback.print_exc()
