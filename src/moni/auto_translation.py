"""
自動翻訳システム - Moni System Monitor

Google Translate API、Azure Translator、DeepLなどの自動翻訳サービスを統合
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib

logger = logging.getLogger(__name__)


class AutoTranslationManager:
    """自動翻訳マネージャー"""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent / "locale"
        self.config_file = self.config_dir / "auto_translate_config.json"
        self.cache_file = self.config_dir / "translation_cache.json"

        # 翻訳キャッシュ
        self._translation_cache: Dict[str, str] = {}
        self._load_cache()

        # 設定
        self._config = self._load_config()

        # 利用可能な翻訳サービス
        self._services = {
            'google': self._translate_google,
            'azure': self._translate_azure,
            'deepl': self._translate_deepl,
        }

    def _load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込み"""
        default_config = {
            'enabled': False,
            'primary_service': 'google',
            'fallback_service': 'azure',
            'api_keys': {},
            'auto_translate_missing': True,
            'cache_translations': True,
            'max_cache_size': 10000,
            'request_delay': 0.1,  # APIレート制限対策
        }

        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")

        return default_config

    def _save_config(self) -> None:
        """設定ファイルを保存"""
        self.config_dir.mkdir(exist_ok=True)
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def _load_cache(self) -> None:
        """翻訳キャッシュを読み込み"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self._translation_cache = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load translation cache: {e}")
                self._translation_cache = {}

    def _save_cache(self) -> None:
        """翻訳キャッシュを保存"""
        if not self._config.get('cache_translations', True):
            return

        try:
            # キャッシュサイズ制限
            max_size = self._config.get('max_cache_size', 10000)
            if len(self._translation_cache) > max_size:
                # 古いエントリを削除（簡易的なLRU）
                oldest_keys = sorted(self._translation_cache.keys(),
                                   key=lambda x: self._translation_cache[x].get('timestamp', 0))[:1000]
                for key in oldest_keys:
                    del self._translation_cache[key]

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._translation_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save translation cache: {e}")

    def set_api_key(self, service: str, api_key: str) -> None:
        """APIキーを設定"""
        if service not in self._services:
            raise ValueError(f"Unsupported translation service: {service}")

        self._config['api_keys'][service] = api_key
        self._save_config()
        logger.info(f"API key set for {service}")

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """テキストを翻訳"""
        if not self._config.get('enabled', False):
            return None

        # キャッシュチェック
        cache_key = self._generate_cache_key(text, source_lang, target_lang)
        if cache_key in self._translation_cache:
            cached = self._translation_cache[cache_key]
            return cached.get('translation')

        # 翻訳実行
        translation = self._perform_translation(text, source_lang, target_lang)

        if translation and self._config.get('cache_translations', True):
            self._translation_cache[cache_key] = {
                'translation': translation,
                'source_lang': source_lang,
                'target_lang': target_lang,
                'timestamp': time.time()
            }
            self._save_cache()

        return translation

    def _generate_cache_key(self, text: str, source_lang: str, target_lang: str) -> str:
        """キャッシュキーを生成"""
        key_data = f"{text}|{source_lang}|{target_lang}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()

    def _perform_translation(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """翻訳を実行"""
        primary_service = self._config.get('primary_service', 'google')
        fallback_service = self._config.get('fallback_service')

        # プライマリサービスで翻訳
        if primary_service in self._services:
            translation = self._services[primary_service](text, source_lang, target_lang)
            if translation:
                return translation

        # フォールバックサービスで翻訳
        if fallback_service and fallback_service in self._services and fallback_service != primary_service:
            translation = self._services[fallback_service](text, source_lang, target_lang)
            if translation:
                return translation

        return None

    def _translate_google(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """Google Translate API"""
        api_key = self._config.get('api_keys', {}).get('google')
        if not api_key:
            return None

        try:
            import requests
            url = "https://translation.googleapis.com/language/translate/v2"
            params = {
                'q': text,
                'source': source_lang,
                'target': target_lang,
                'format': 'text',
                'key': api_key
            }

            response = requests.post(url, params=params, timeout=10)
            response.raise_for_status()

            result = response.json()
            return result['data']['translations'][0]['translatedText']

        except Exception as e:
            logger.error(f"Google Translate API error: {e}")
            return None

    def _translate_azure(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """Azure Translator API"""
        api_key = self._config.get('api_keys', {}).get('azure')
        if not api_key:
            return None

        try:
            import requests
            url = "https://api.cognitive.microsofttranslator.com/translate"
            headers = {
                'Ocp-Apim-Subscription-Key': api_key,
                'Content-Type': 'application/json'
            }
            params = {
                'api-version': '3.0',
                'from': source_lang,
                'to': target_lang
            }
            body = [{'text': text}]

            response = requests.post(url, headers=headers, params=params, json=body, timeout=10)
            response.raise_for_status()

            result = response.json()
            return result[0]['translations'][0]['text']

        except Exception as e:
            logger.error(f"Azure Translator API error: {e}")
            return None

    def _translate_deepl(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """DeepL API"""
        api_key = self._config.get('api_keys', {}).get('deepl')
        if not api_key:
            return None

        try:
            import requests
            url = "https://api-free.deepl.com/v2/translate"
            params = {
                'auth_key': api_key,
                'text': text,
                'source_lang': source_lang.upper(),
                'target_lang': target_lang.upper()
            }

            response = requests.post(url, data=params, timeout=10)
            response.raise_for_status()

            result = response.json()
            return result['translations'][0]['text']

        except Exception as e:
            logger.error(f"DeepL API error: {e}")
            return None

    def translate_missing_keys(self, source_lang: str = 'en') -> Dict[str, Dict[str, str]]:
        """未翻訳のキーを自動翻訳"""
        if not self._config.get('enabled', False):
            return {}

        translated_data = {}

        # 全ての言語ファイルの翻訳キーを収集
        all_keys = set()
        lang_keys = {}

        for lang_file in self.config_dir.glob("*.json"):
            if lang_file.name == 'en.json':
                continue

            lang_code = lang_file.stem
            with open(lang_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                translations = data.get('translations', {})
                keys = self._extract_all_keys(translations)
                lang_keys[lang_code] = keys
                all_keys.update(keys)

        # 英語ファイルから基準キーを取得
        en_file = self.config_dir / 'en.json'
        if en_file.exists():
            with open(en_file, 'r', encoding='utf-8') as f:
                en_data = json.load(f)
                en_translations = en_data.get('translations', {})
                en_keys = self._extract_all_keys(en_translations)

                # 不足しているキーを特定
                missing_keys = en_keys - all_keys

                for target_lang in lang_keys.keys():
                    translated_data[target_lang] = {}

                    for key in missing_keys:
                        if key in en_translations:
                            source_text = self._get_nested_value(en_translations, key)
                            if source_text:
                                translated = self.translate_text(source_text, source_lang, target_lang[:2])
                                if translated:
                                    translated_data[target_lang][key] = translated

        return translated_data

    def _extract_all_keys(self, translations: Dict[str, Any]) -> set:
        """翻訳データから全てのキーを抽出"""
        keys = set()

        def extract_keys(data: Dict[str, Any], prefix: str = ''):
            for key, value in data.items():
                if isinstance(value, dict):
                    extract_keys(value, f'{prefix}.{key}' if prefix else key)
                else:
                    keys.add(f'{prefix}.{key}' if prefix else key)

        extract_keys(translations)
        return keys

    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Optional[str]:
        """ネストされた値をキーから取得"""
        keys = key.split('.')
        current = data

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None

        return current if isinstance(current, str) else None

    def get_supported_services(self) -> List[str]:
        """サポートされている翻訳サービスを取得"""
        return list(self._services.keys())

    def get_config(self) -> Dict[str, Any]:
        """現在の設定を取得"""
        return self._config.copy()

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """設定を更新"""
        self._config.update(new_config)
        self._save_config()
