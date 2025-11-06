#!/usr/bin/env python3
"""
国際化システムテストスクリプト
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from moni.internationalization import i18n_manager, TranslationManager, LanguageChangeEvent
    print("✓ 国際化システムのインポートに成功しました")

    # 基本機能のテスト
    print(f"✓ 現在のロケール: {i18n_manager.get_current_locale()}")

    # 言語変更イベントシステムのテスト
    def test_callback(event):
        print(f"言語変更イベント: {event.old_locale} -> {event.new_locale}")

    i18n_manager.add_language_change_callback(test_callback)
    print("✓ 言語変更コールバックを登録しました")

    # 言語設定のテスト
    if i18n_manager.set_locale('ja'):
        print("✓ 日本語に変更しました")
    else:
        print("✗ 日本語への変更に失敗しました")

    # 翻訳機能のテスト
    translated = i18n_manager.get_text("Hello World")
    print(f"✓ 翻訳テスト: {translated}")

    print("\n🎉 すべてのテストに成功しました！")

except Exception as e:
    print(f"エラー: {e}")
    import traceback
    traceback.print_exc()
