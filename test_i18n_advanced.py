#!/usr/bin/env python3
"""
国際化システム拡張機能テストスクリプト
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from moni.internationalization import i18n_manager

    print("✅ 国際化システムのインポートに成功しました")

    # 基本機能のテスト
    print(f"📍 現在のロケール: {i18n_manager.get_current_locale()}")

    # 言語変更テスト
    if i18n_manager.set_locale('ja'):
        print("✅ 日本語に変更しました")
        print(f"📝 翻訳テスト: {i18n_manager.get_text('Hello World')}")

        # 言語変更イベントテスト
        def test_callback(event):
            print(f"🔔 言語変更イベント: {event.old_locale} -> {event.new_locale}")

        i18n_manager.add_language_change_callback(test_callback)

        # 言語を英語に戻す
        i18n_manager.set_locale_with_notification('en')
        print(f"📝 英語翻訳テスト: {i18n_manager.get_text('Hello World')}")

    # 言語固有フォーマットテスト
    from datetime import datetime
    print(f"📅 日付フォーマット（日本語）: {i18n_manager.format_date(datetime.now(), 'ja')}")
    print(f"💰 通貨フォーマット（日本語）: {i18n_manager.format_currency(1234.56, 'USD', 'ja')}")
    print(f"🔢 数値フォーマット（日本語）: {i18n_manager.format_number(1234.56, 'ja')}")

    # キャッシュ統計テスト
    cache_stats = i18n_manager.get_cache_statistics()
    print(f"💾 キャッシュ統計: {cache_stats}")

    # 翻訳メモリテスト
    i18n_manager.add_translation_to_memory("テストテキスト", "テスト翻訳", "en", "ja")
    cached = i18n_manager.get_translation_from_memory("テストテキスト", "en", "ja")
    print(f"🧠 翻訳メモリテスト: {cached}")

    print("\n🎉 すべてのテストに成功しました！")

except Exception as e:
    print(f"❌ エラー: {e}")
    import traceback
    traceback.print_exc()
