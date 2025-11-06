"""
RTL言語対応のUIコンポーネント - Moni System Monitor

右から左へのテキスト方向をサポートするUIコンポーネントを提供します。
"""

from PySide6.QtCore import Qt, QLocale
from PySide6.QtWidgets import QApplication
import logging

logger = logging.getLogger(__name__)


class RTLScheduler:
    """RTL言語のUI適応を管理"""

    def __init__(self, i18n_manager):
        self.i18n_manager = i18n_manager
        self._rtl_languages = {'ar', 'he', 'fa', 'ur', 'yi'}
        self._current_rtl_state = False

    def is_rtl_language(self, language_code: str) -> bool:
        """言語がRTLかどうかを判定"""
        return language_code in self._rtl_languages

    def update_ui_for_rtl(self, widgets: list) -> None:
        """UIウィジェットをRTL用に更新"""
        current_lang = self.i18n_manager.get_current_language()
        is_rtl = self.is_rtl_language(current_lang)

        if is_rtl == self._current_rtl_state:
            return  # 変更なし

        self._current_rtl_state = is_rtl

        for widget in widgets:
            self._apply_rtl_to_widget(widget, is_rtl)

    def _apply_rtl_to_widget(self, widget, is_rtl: bool) -> None:
        """単一のウィジェットにRTL設定を適用"""
        try:
            if is_rtl:
                # RTL用のレイアウト方向を設定
                widget.setLayoutDirection(Qt.RightToLeft)
                # テキスト配置を調整
                self._adjust_text_alignment(widget, is_rtl)
            else:
                # LTRに戻す
                widget.setLayoutDirection(Qt.LeftToRight)
                self._adjust_text_alignment(widget, is_rtl)
        except Exception as e:
            logger.debug(f"Failed to apply RTL settings to widget: {e}")

    def _adjust_text_alignment(self, widget, is_rtl: bool) -> None:
        """テキスト配置をRTL用に調整"""
        try:
            # QLabelの場合
            if hasattr(widget, 'setAlignment'):
                if is_rtl:
                    # RTLではテキストを右寄せ
                    widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    # LTRではテキストを左寄せ
                    widget.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        except Exception as e:
            logger.debug(f"Failed to adjust text alignment: {e}")

    def get_text_direction(self, language_code: str) -> str:
        """言語のテキスト方向を取得"""
        if self.is_rtl_language(language_code):
            return "rtl"
        return "ltr"

    def get_system_locale_direction(self) -> str:
        """システムロケールのテキスト方向を取得"""
        try:
            locale = QLocale.system()
            # システムロケールがRTL言語の場合
            if locale.language() in [QLocale.Arabic, QLocale.Hebrew, QLocale.Language.Farsi]:
                return "rtl"
        except:
            pass
        return "ltr"


def setup_rtl_support(i18n_manager):
    """RTLサポートをセットアップ"""
    rtl_scheduler = RTLScheduler(i18n_manager)

    # 言語変更時のRTL更新を登録
    def on_language_change(new_language):
        # UIが利用可能な場合のみRTLを適用
        try:
            app = QApplication.instance()
            if app:
                # メインウィンドウのRTL更新
                for widget in app.topLevelWidgets():
                    rtl_scheduler.update_ui_for_rtl([widget])
        except Exception as e:
            logger.debug(f"Failed to update RTL on language change: {e}")

    # 言語変更コールバックを登録（i18n_managerに追加する必要がある）
    if hasattr(i18n_manager, 'add_language_change_callback'):
        i18n_manager.add_language_change_callback(on_language_change)

    return rtl_scheduler


class RTLTextFormatter:
    """RTL言語用のテキストフォーマッター"""

    @staticmethod
    def format_number_for_rtl(number: float, locale_code: str = "ar") -> str:
        """RTL言語用の数値フォーマット"""
        # アラビア語などのRTL言語では数値も右から左に表示されることがある
        if locale_code.startswith('ar'):
            return f"{number:.2f}"  # アラビア数字を使用
        return f"{number:.2f}"

    @staticmethod
    def format_date_for_rtl(date_str: str, locale_code: str = "ar") -> str:
        """RTL言語用の日付フォーマット"""
        # 日付フォーマットは言語によって異なる
        if locale_code.startswith('ar'):
            # アラビア語の日付フォーマット
            return date_str.replace('/', '-')  # スラッシュをハイフンに
        return date_str

    @staticmethod
    def mirror_layout_for_rtl(layout) -> None:
        """レイアウトをRTL用にミラー化"""
        try:
            if hasattr(layout, 'setDirection'):
                layout.setDirection(Qt.RightToLeft)
        except Exception as e:
            logger.debug(f"Failed to mirror layout: {e}")


# RTL言語のリスト（ISO 639-1コード）
RTL_LANGUAGE_CODES = {
    'ar': 'العربية (Arabic)',
    'he': 'עברית (Hebrew)',
    'fa': 'فارسی (Persian/Farsi)',
    'ur': 'اردو (Urdu)',
    'yi': 'ייִדיש (Yiddish)',
    'dv': 'ދިވެހި (Dhivehi)',
    'prs': 'دري (Dari)',
    'ps': 'پښتو (Pashto)',
    'sd': 'سنڌي (Sindhi)',
    'ug': 'ئۇيغۇرچە (Uyghur)',
    'ku': 'Kurdish (Sorani)',  # 一部の方言でRTL
}

# RTL言語の判定関数
def is_rtl_language(language_code: str) -> bool:
    """言語コードがRTLかどうかを判定"""
    return language_code in RTL_LANGUAGE_CODES

# テキスト方向の取得
def get_text_direction(language_code: str) -> str:
    """言語コードのテキスト方向を取得"""
    if is_rtl_language(language_code):
        return "rtl"
    return "ltr"

# RTL言語のネイティブ名取得
def get_rtl_language_name(language_code: str) -> str:
    """RTL言語のネイティブ名を取得"""
    return RTL_LANGUAGE_CODES.get(language_code, language_code)
