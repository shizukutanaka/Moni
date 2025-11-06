"""
翻訳品質管理システム - Moni System Monitor

多言語対応の翻訳品質を確保・改善するためのツール群
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TranslationQualityIssue:
    """翻訳品質の問題"""
    language: str
    key: str
    issue_type: str  # 'missing', 'inconsistent', 'formatting', 'context'
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    suggestion: str


class TranslationQualityManager:
    """翻訳品質管理マネージャー"""

    def __init__(self, locale_dir: Optional[Path] = None):
        self.locale_dir = locale_dir or Path(__file__).parent / "locale"
        self.baseline_language = "en"  # 基準言語
        self.issues: List[TranslationQualityIssue] = []

    def analyze_translation_quality(self) -> Dict[str, Any]:
        """翻訳品質を包括的に分析"""
        if not self.locale_dir.exists():
            return {"error": "Locale directory not found"}

        # 全言語ファイルを取得
        lang_files = list(self.locale_dir.glob("*.json"))
        if not lang_files:
            return {"error": "No language files found"}

        analysis_result = {
            "total_languages": len(lang_files),
            "baseline_language": self.baseline_language,
            "quality_score": 0.0,
            "issues": [],
            "coverage": {},
            "consistency": {},
            "recommendations": []
        }

        # 各言語の分析
        for lang_file in lang_files:
            lang_code = lang_file.stem
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                quality = self._analyze_single_language(lang_code, data)
                analysis_result["coverage"][lang_code] = quality["coverage"]
                analysis_result["issues"].extend(quality["issues"])

            except Exception as e:
                logger.error(f"Failed to analyze {lang_code}: {e}")
                analysis_result["issues"].append({
                    "language": lang_code,
                    "error": str(e)
                })

        # 全体的な品質スコアを計算
        analysis_result["quality_score"] = self._calculate_overall_quality(analysis_result)
        analysis_result["recommendations"] = self._generate_recommendations(analysis_result)

        return analysis_result

    def _analyze_single_language(self, lang_code: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """単一言語の翻訳品質を分析"""
        translations = data.get("translations", {})
        metadata = data.get("metadata", {})

        # カバレッジ分析
        coverage = self._analyze_coverage(translations)

        # 一貫性分析
        consistency = self._analyze_consistency(translations)

        # フォーマット分析
        formatting = self._analyze_formatting(translations)

        # 文脈分析
        context = self._analyze_context(translations)

        issues = []
        issues.extend(coverage["issues"])
        issues.extend(consistency["issues"])
        issues.extend(formatting["issues"])
        issues.extend(context["issues"])

        return {
            "coverage": coverage["score"],
            "consistency": consistency["score"],
            "formatting": formatting["score"],
            "context": context["score"],
            "issues": issues,
            "metadata_valid": self._validate_metadata(metadata)
        }

    def _analyze_coverage(self, translations: Dict[str, Any]) -> Dict[str, Any]:
        """翻訳カバレッジを分析"""
        # 基準言語の翻訳キーを取得
        baseline_file = self.locale_dir / f"{self.baseline_language}.json"
        if not baseline_file.exists():
            return {"score": 0.0, "issues": []}

        with open(baseline_file, 'r', encoding='utf-8') as f:
            baseline_data = json.load(f)
            baseline_translations = baseline_data.get("translations", {})

        # 全てのキーを抽出（再帰的に）
        def extract_all_keys(data: Dict[str, Any]) -> set:
            keys = set()
            for key, value in data.items():
                if isinstance(value, dict):
                    nested_keys = extract_all_keys(value)
                    keys.update({f"{key}.{k}" for k in nested_keys})
                else:
                    keys.add(key)
            return keys

        baseline_keys = extract_all_keys(baseline_translations)
        current_keys = extract_all_keys(translations)

        # 不足しているキー
        missing_keys = baseline_keys - current_keys
        extra_keys = current_keys - baseline_keys

        coverage_score = len(current_keys) / len(baseline_keys) if baseline_keys else 0.0

        issues = []
        for key in missing_keys:
            issues.append(TranslationQualityIssue(
                language="", key=key, issue_type="missing",
                severity="high", description=f"Missing translation for key: {key}",
                suggestion=f"Add translation for '{key}'"
            ))

        for key in extra_keys:
            issues.append(TranslationQualityIssue(
                language="", key=key, issue_type="extra",
                severity="low", description=f"Extra translation key: {key}",
                suggestion=f"Consider removing or checking if this key should be in baseline"
            ))

        return {"score": coverage_score, "issues": issues}

    def _analyze_consistency(self, translations: Dict[str, Any]) -> Dict[str, Any]:
        """翻訳の一貫性を分析"""
        issues = []
        consistency_score = 1.0

        # 用語の一貫性チェック
        term_usage = self._check_term_consistency(translations)

        # フォーマットの一貫性チェック
        format_usage = self._check_format_consistency(translations)

        # テキスト長の一貫性チェック
        length_consistency = self._check_length_consistency(translations)

        # 問題がある場合、スコアを下げる
        if term_usage["issues"]:
            consistency_score -= 0.2
        if format_usage["issues"]:
            consistency_score -= 0.1
        if length_consistency["issues"]:
            consistency_score -= 0.1

        issues.extend(term_usage["issues"])
        issues.extend(format_usage["issues"])
        issues.extend(length_consistency["issues"])

        return {"score": max(0.0, consistency_score), "issues": issues}

    def _check_term_consistency(self, translations: Dict[str, Any]) -> Dict[str, Any]:
        """用語の一貫性チェック"""
        issues = []

        # 重要な用語の使用パターンをチェック
        key_terms = ["CPU", "Memory", "System", "Monitor", "Settings", "Configuration"]

        for term in key_terms:
            self._check_term_usage_consistency(translations, term, issues)

        return {"issues": issues}

    def _check_term_usage_consistency(self, translations: Dict[str, Any], term: str, issues: List) -> None:
        """特定用語の使用一貫性をチェック"""
        def find_term_usage(data: Dict[str, Any], path: str = "") -> List[str]:
            usages = []
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, dict):
                    usages.extend(find_term_usage(value, current_path))
                elif isinstance(value, str) and term.lower() in value.lower():
                    usages.append(f"{current_path}: {value}")
            return usages

        usages = find_term_usage(translations)
        if len(usages) > 1:
            # 複数の異なる翻訳があるかチェック
            translations_found = [usage.split(": ", 1)[1] for usage in usages]
            if len(set(translations_found)) > 1:
                issues.append(TranslationQualityIssue(
                    language="", key="", issue_type="inconsistent_terms",
                    severity="medium",
                    description=f"Inconsistent translation for term '{term}': {translations_found}",
                    suggestion=f"Standardize translation for '{term}'"
                ))

    def _check_format_consistency(self, translations: Dict[str, Any]) -> Dict[str, Any]:
        """フォーマットの一貫性チェック"""
        issues = []

        # フォーマット文字列の使用パターンをチェック
        def check_format_strings(data: Dict[str, Any]) -> List[str]:
            format_strings = []
            for key, value in data.items():
                if isinstance(value, dict):
                    format_strings.extend(check_format_strings(value))
                elif isinstance(value, str):
                    # フォーマットプレースホルダーをチェック
                    if re.search(r'\{[^}]+\}', value):
                        format_strings.append(value)
            return format_strings

        format_strings = check_format_strings(translations)

        # フォーマットパターンの一貫性をチェック
        if format_strings:
            patterns = [re.findall(r'\{([^}]+)\}', s) for s in format_strings]
            if patterns:
                first_pattern = set(patterns[0])
                for i, pattern in enumerate(patterns[1:], 1):
                    if set(pattern) != first_pattern:
                        issues.append(TranslationQualityIssue(
                            language="", key="", issue_type="inconsistent_formatting",
                            severity="high",
                            description=f"Inconsistent format pattern in string: {format_strings[i]}",
                            suggestion="Ensure consistent placeholder usage"
                        ))

        return {"issues": issues}

    def _check_length_consistency(self, translations: Dict[str, Any]) -> Dict[str, Any]:
        """テキスト長の一貫性チェック"""
        issues = []

        # 基準言語と比較して大幅に異なる場合を検出
        baseline_file = self.locale_dir / f"{self.baseline_language}.json"
        if baseline_file.exists():
            with open(baseline_file, 'r', encoding='utf-8') as f:
                baseline_data = json.load(f)
                baseline_translations = baseline_data.get("translations", {})

            def check_lengths(data: Dict[str, Any], baseline: Dict[str, Any], path: str = ""):
                for key, value in data.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, dict) and key in baseline and isinstance(baseline[key], dict):
                        check_lengths(value, baseline[key], current_path)
                    elif isinstance(value, str) and key in baseline and isinstance(baseline[key], str):
                        if len(value) > len(baseline[key]) * 2 or len(value) < len(baseline[key]) * 0.3:
                            issues.append(TranslationQualityIssue(
                                language="", key=current_path, issue_type="length_inconsistency",
                                severity="low",
                                description=f"Significant length difference: baseline={len(baseline[key])}, current={len(value)}",
                                suggestion="Check if translation length is appropriate"
                            ))

            check_lengths(translations, baseline_translations)

        return {"issues": issues}

    def _analyze_formatting(self, translations: Dict[str, Any]) -> Dict[str, Any]:
        """フォーマットの分析"""
        issues = []
        score = 1.0

        # プレースホルダーの整合性チェック
        def check_placeholder_consistency(data: Dict[str, Any]) -> None:
            for key, value in data.items():
                if isinstance(value, dict):
                    check_placeholder_consistency(value)
                elif isinstance(value, str):
                    # フォーマットプレースホルダーの数をチェック
                    placeholders = re.findall(r'\{[^}]+\}', value)
                    if placeholders:
                        # 各プレースホルダーが適切に閉じられているかチェック
                        for placeholder in placeholders:
                            if not placeholder.startswith('{') or not placeholder.endswith('}'):
                                issues.append(TranslationQualityIssue(
                                    language="", key=key, issue_type="formatting_error",
                                    severity="high",
                                    description=f"Malformed placeholder: {placeholder}",
                                    suggestion="Fix placeholder formatting"
                                ))

        check_placeholder_consistency(translations)

        if issues:
            score = 0.5

        return {"score": score, "issues": issues}

    def _analyze_context(self, translations: Dict[str, Any]) -> Dict[str, Any]:
        """文脈の分析"""
        issues = []
        score = 1.0

        # 特定の文脈での翻訳の適切性をチェック
        context_checks = [
            (r'error|Error|ERROR', 'エラーメッセージ'),
            (r'warning|Warning|WARNING', '警告メッセージ'),
            (r'success|Success|SUCCESS', '成功メッセージ'),
            (r'loading|Loading|LOADING', '読み込みメッセージ'),
            (r'settings|Settings|SETTINGS', '設定関連'),
            (r'configure|Configure|CONFIGURE', '設定関連'),
        ]

        for pattern, context in context_checks:
            self._check_context_consistency(translations, pattern, context, issues)

        if issues:
            score = 0.8

        return {"score": score, "issues": issues}

    def _check_context_consistency(self, translations: Dict[str, Any], pattern: str, context: str, issues: List) -> None:
        """文脈の一貫性チェック"""
        def find_matching_strings(data: Dict[str, Any], path: str = "") -> List[Tuple[str, str]]:
            matches = []
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, dict):
                    matches.extend(find_matching_strings(value, current_path))
                elif isinstance(value, str) and re.search(pattern, value, re.IGNORECASE):
                    matches.append((current_path, value))
            return matches

        matches = find_matching_strings(translations)
        if matches:
            # 文脈に適した翻訳になっているかチェック
            for path, text in matches:
                if self._is_inappropriate_context(text, context):
                    issues.append(TranslationQualityIssue(
                        language="", key=path, issue_type="context_inappropriate",
                        severity="medium",
                        description=f"Potentially inappropriate context for {context}: {text}",
                        suggestion=f"Review translation for {context} context"
                    ))

    def _is_inappropriate_context(self, text: str, expected_context: str) -> bool:
        """文脈が不適切かどうかを判定"""
        # 簡易的なチェック
        inappropriate_patterns = {
            'エラーメッセージ': [r'成功|success|ok', r'完了|complete|done'],
            '警告メッセージ': [r'成功|success|ok', r'完了|complete|done'],
            '成功メッセージ': [r'失敗|fail|error', r'エラー|error|問題'],
        }

        for context, patterns in inappropriate_patterns.items():
            if expected_context in context:
                for pattern in patterns:
                    if re.search(pattern, text, re.IGNORECASE):
                        return True

        return False

    def _validate_metadata(self, metadata: Dict[str, Any]) -> bool:
        """メタデータの有効性を検証"""
        required_fields = ['language', 'language_code', 'locale', 'encoding', 'rtl', 'text_direction']

        for field in required_fields:
            if field not in metadata:
                return False

        # RTL設定の整合性チェック
        rtl = metadata.get('rtl', False)
        direction = metadata.get('text_direction', 'ltr')
        if rtl and direction != 'rtl':
            return False
        if not rtl and direction != 'ltr':
            return False

        return True

    def _calculate_overall_quality(self, analysis: Dict[str, Any]) -> float:
        """全体的な品質スコアを計算"""
        if not analysis["coverage"]:
            return 0.0

        # カバレッジスコアの平均
        coverage_scores = [data for data in analysis["coverage"].values() if isinstance(data, (int, float))]
        if not coverage_scores:
            return 0.0

        avg_coverage = sum(coverage_scores) / len(coverage_scores)

        # 問題の深刻度による減点
        critical_issues = len([issue for issue in analysis["issues"] if getattr(issue, 'severity', '') == 'critical'])
        high_issues = len([issue for issue in analysis["issues"] if getattr(issue, 'severity', '') == 'high'])
        medium_issues = len([issue for issue in analysis["issues"] if getattr(issue, 'severity', '') == 'medium'])

        penalty = (critical_issues * 0.3 + high_issues * 0.2 + medium_issues * 0.1) / max(1, len(analysis["issues"]))

        return max(0.0, avg_coverage - penalty)

    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """改善提案を生成"""
        recommendations = []

        # カバレッジに基づく提案
        low_coverage_langs = [lang for lang, score in analysis["coverage"].items()
                             if isinstance(score, (int, float)) and score < 0.8]
        if low_coverage_langs:
            recommendations.append(f"Complete translations for: {', '.join(low_coverage_langs)}")

        # 問題数に基づく提案
        if len(analysis["issues"]) > 10:
            recommendations.append("Review and fix translation issues")

        # RTL言語の提案
        rtl_languages = [lang for lang in analysis["coverage"].keys()
                        if self.locale_dir.joinpath(f"{lang}.json").exists()]
        with open(self.locale_dir / f"{rtl_languages[0]}.json", 'r', encoding='utf-8') as f:
            rtl_data = json.load(f)
            if rtl_data.get("metadata", {}).get("rtl", False):
                recommendations.append("Test RTL language support thoroughly")

        return recommendations

    def generate_quality_report(self) -> str:
        """品質レポートを生成"""
        analysis = self.analyze_translation_quality()

        if "error" in analysis:
            return f"Error: {analysis['error']}"

        report = []
        report.append("=== 翻訳品質レポート ===")
        report.append(f"全体品質スコア: {analysis['quality_score']:.2f}/1.0".2f"        report.append(f"サポート言語数: {analysis['total_languages']}")
        report.append(f"基準言語: {analysis['baseline_language']}")
        report.append("")

        # 言語別カバレッジ
        report.append("言語別カバレッジ:")
        for lang, score in analysis["coverage"].items():
            if isinstance(score, (int, float)):
                status = "✅" if score > 0.9 else "⚠️" if score > 0.7 else "❌"
                report.append(f"  {status} {lang}: {score:.1%}")
".1%"
        # 問題の要約
        if analysis["issues"]:
            report.append(f"\\n検出された問題: {len(analysis['issues'])}件")

            # 深刻度別
            severity_count = {}
            for issue in analysis["issues"]:
                severity = getattr(issue, 'severity', 'unknown')
                severity_count[severity] = severity_count.get(severity, 0) + 1

            for severity, count in sorted(severity_count.items()):
                report.append(f"  {severity}: {count}件")

        # 提案
        if analysis["recommendations"]:
            report.append("\\n改善提案:")
            for rec in analysis["recommendations"]:
                report.append(f"  • {rec}")

        return "\\n".join(report)

    def export_issues_to_json(self, output_file: str) -> None:
        """問題をJSONファイルにエクスポート"""
        analysis = self.analyze_translation_quality()

        export_data = {
            "quality_score": analysis["quality_score"],
            "total_languages": analysis["total_languages"],
            "issues": [
                {
                    "language": issue.language,
                    "key": issue.key,
                    "issue_type": issue.issue_type,
                    "severity": issue.severity,
                    "description": issue.description,
                    "suggestion": issue.suggestion
                }
                for issue in analysis["issues"]
                if hasattr(issue, 'severity')
            ],
            "recommendations": analysis["recommendations"],
            "timestamp": self._get_timestamp()
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

    def _get_timestamp(self) -> str:
        """タイムスタンプを取得"""
        from datetime import datetime
        return datetime.now().isoformat()


# 品質管理ツールの実行関数
def run_translation_quality_check(locale_dir: Optional[Path] = None) -> str:
    """翻訳品質チェックを実行"""
    manager = TranslationQualityManager(locale_dir)
    return manager.generate_quality_report()


def main():
    """メイン実行関数"""
    import sys

    if len(sys.argv) > 1:
        locale_dir = Path(sys.argv[1])
    else:
        locale_dir = Path(__file__).parent / "locale"

    manager = TranslationQualityManager(locale_dir)

    print("翻訳品質分析を実行中...")
    report = manager.generate_quality_report()
    print(report)

    # JSONエクスポート
    output_file = locale_dir / "translation_quality_report.json"
    manager.export_issues_to_json(str(output_file))
    print(f"\\n詳細レポートをエクスポート: {output_file}")


if __name__ == "__main__":
    main()
