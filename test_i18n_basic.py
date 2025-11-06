#!/usr/bin/env python3
"""
国際化システム基本テストスクリプト
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

    # 構文チェック
    with open(i18n_file, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        ast.parse(content)
        print("✅ 構文チェックOK")
    except SyntaxError as e:
        print(f"❌ 構文エラー: {e}")
        print(f"   エラー位置: 行 {e.lineno}, 列 {e.offset}")
        sys.exit(1)

    # モジュールをインポートしてテスト
    from moni.internationalization import TranslationManager

    print("✅ TranslationManagerクラスをインポートしました")

    # インスタンス作成テスト
    manager = TranslationManager()
    print("✅ TranslationManagerインスタンスを作成しました")

    # 基本機能テスト
    languages = manager.get_supported_languages()
    print(f"✅ サポート言語数: {len(languages)}")

    current_locale = manager.get_current_locale()
    print(f"✅ 現在のロケール: {current_locale}")

    # 言語設定テスト
    if manager.set_locale('ja'):
        print("✅ 日本語に設定しました")
        print(f"✅ 翻訳テスト: {manager.get_text('Hello World')}")
    else:
        print("⚠️ 日本語設定に失敗しました")

    print("\n🎉 基本テストに成功しました！")

except Exception as e:
    print(f"❌ エラー: {e}")
    import traceback
    traceback.print_exc()
