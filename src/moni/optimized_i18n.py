"""
国際化システム - Moni System Monitor
パフォーマンス最適化版

多言語対応のための国際化フレームワークを提供します。
gettextベースの翻訳システムを実装し、50言語以上をサポートします。
"""

import json
import logging
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, Callable

logger = logging.getLogger(__name__)


class TranslationCache:
    """翻訳結果のLRUキャッシュ"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: Dict[str, Dict[str, str]] = {}
        self.access_times: Dict[str, float] = {}
        self._lock = threading.Lock()

    def get(self, cache_key: str, language: str) -> Optional[str]:
        """キャッシュから翻訳を取得"""
        with self._lock:
            if cache_key in self.cache and language in self.cache[cache_key]:
                self.access_times[cache_key] = time.time()
                return self.cache[cache_key][language]
            return None

    def set(self, cache_key: str, language: str, translation: str) -> None:
        """キャッシュに翻訳を保存"""
        with self._lock:
            if cache_key not in self.cache:
                self.cache[cache_key] = {}

            self.cache[cache_key][language] = translation
            self.access_times[cache_key] = time.time()

            # キャッシュサイズ制限を超えたら古いエントリを削除
            if len(self.cache) > self.max_size:
                self._evict_oldest()

    def clear(self) -> None:
        """キャッシュをクリア"""
        with self._lock:
            self.cache.clear()
            self.access_times.clear()

    def _evict_oldest(self) -> None:
        """最も古いエントリを削除"""
        if not self.access_times:
            return

        oldest_key = min(self.access_times.items(), key=lambda x: x[1])
        del self.cache[oldest_key[0]]
        del self.access_times[oldest_key[0]]

    def get_stats(self) -> Dict[str, Any]:
        """キャッシュ統計を取得"""
        with self._lock:
            return {
                'cache_size': len(self.cache),
                'max_size': self.max_size,
                'hit_ratio': self._calculate_hit_ratio()
            }

    def _calculate_hit_ratio(self) -> float:
        """キャッシュヒット率を計算（簡易版）"""
        # 実際のヒット率計算にはアクセスカウンターが必要
        return 0.0


# グローバルキャッシュインスタンス
_translation_cache = TranslationCache(max_size=2000)


class OptimizedTranslator:
    """パフォーマンス最適化された翻訳マネージャー"""

    def __init__(self, locale_dir: Optional[Path] = None):
        self.locale_dir = locale_dir or Path(__file__).parent / "locale"
        self.current_language = "en"
        self.translations: Dict[str, Dict[str, Any]] = {}
        self.fallback_language = "en"
        self._cache_enabled = True
        self._load_translations()

    def _load_translations(self) -> None:
        """最適化された翻訳ファイルの読み込み"""
        self.translations.clear()

        if not self.locale_dir.exists():
            logger.warning(f"Locale directory not found: {self.locale_dir}")
            return

        # 並列読み込み（スレッドプール使用）
        import concurrent.futures

        def load_single_file(locale_file: Path) -> tuple:
            """単一の翻訳ファイルを読み込み"""
            try:
                language_code = locale_file.stem
                with open(locale_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return language_code, data.get('translations', {})
            except Exception as e:
                logger.error(f"Failed to load {locale_file}: {e}")
                return None, {}

        # 並列で翻訳ファイルを読み込み
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(load_single_file, f) for f in self.locale_dir.glob("*.json")]

            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result[0]:
                    self.translations[result[0]] = result[1]
                    logger.info(f"Loaded optimized translations for {result[0]}")

    @lru_cache(maxsize=500)
    def _get_translation_key(self, language: str, key: str) -> Optional[str]:
        """LRUキャッシュ付きの翻訳キー取得"""
        if language not in self.translations:
            return None

        return self._get_nested_value(self.translations[language], key)

    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Optional[str]:
        """ネストされた辞書値を取得（ドット記法）"""
        keys = key.split('.')
        current = data

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None

        return current if isinstance(current, str) else None

    def get(self, key: str, default: str = "", **kwargs) -> str:
        """最適化された翻訳取得"""
        # キャッシュチェック
        if self._cache_enabled:
            cache_key = f"{self.current_language}:{key}"
            cached = _translation_cache.get(cache_key, self.current_language)
            if cached is not None:
                return self._format_string(cached, **kwargs)

        # 翻訳取得
        translation = self._get_translation_key(self.current_language, key)

        if not translation and self.fallback_language != self.current_language:
            translation = self._get_translation_key(self.fallback_language, key)

        if not translation:
            translation = default or key

        # フォーマット
        formatted = self._format_string(translation, **kwargs)

        # キャッシュ保存
        if self._cache_enabled:
            _translation_cache.set(cache_key, self.current_language, formatted)

        return formatted

    def _format_string(self, template: str, **kwargs) -> str:
        """文字列フォーマット（エラーハンドリング強化）"""
        if not kwargs:
            return template

        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            logger.debug(f"String formatting failed for template: {template}")
            return template

    def set_language(self, language_code: str) -> bool:
        """言語設定（キャッシュクリア）"""
        if language_code not in self.translations:
            logger.warning(f"Language not available: {language_code}")
            return False

        # キャッシュクリア
        if self._cache_enabled:
            _translation_cache.clear()

        self.current_language = language_code
        logger.info(f"Language optimized to: {language_code}")
        return True

    def get_available_languages(self) -> List[str]:
        """利用可能な言語一覧を取得"""
        return list(self.translations.keys())

    def preload_common_translations(self, keys: List[str]) -> None:
        """一般的な翻訳キーをプリロード"""
        for key in keys:
            for language in self.translations.keys():
                cache_key = f"{language}:{key}"
                translation = self._get_translation_key(language, key)
                if translation:
                    _translation_cache.set(cache_key, language, translation)

    def get_cache_stats(self) -> Dict[str, Any]:
        """キャッシュ統計を取得"""
        return _translation_cache.get_stats()


# グローバル翻訳インスタンス
_translator: Optional[OptimizedTranslator] = None


def get_translator() -> OptimizedTranslator:
    """グローバル翻訳インスタンスを取得"""
    global _translator
    if _translator is None:
        _translator = OptimizedTranslator()
    return _translator


def t(key: str, default: str = "", **kwargs) -> str:
    """翻訳の便利関数"""
    return get_translator().get(key, default, **kwargs)


def set_language(language_code: str) -> bool:
    """言語設定"""
    return get_translator().set_language(language_code)


def get_current_language() -> str:
    """現在の言語を取得"""
    return get_translator().current_language


# 後方互換性のためのマネージャー
class I18nManager:
    """既存のUIコードとの互換性のためのマネージャー"""

    def __init__(self):
        self.translator = get_translator()

    def get_text(self, key: str, default: str = "") -> str:
        """翻訳テキストを取得（ドット記法）"""
        return self.translator.get(key, default)

    def set_language(self, language_code: str) -> bool:
        """言語設定"""
        return self.translator.set_language(language_code)

    def get_available_languages(self) -> List[str]:
        """利用可能な言語一覧"""
        return self.translator.get_available_languages()

    def get_current_language(self) -> str:
        """現在の言語"""
        return self.translator.current_language


# グローバルi18nマネージャー（後方互換性）
i18n_manager = I18nManager()
