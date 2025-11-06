#!/usr/bin/env python3
"""
Internationalization Analysis Tool for Moni System
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Set

def analyze_internationalization_file(file_path: str) -> Dict:
    """Analyze the internationalization.py file structure and content."""

    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    result = {
        "file_info": {},
        "classes": [],
        "functions": [],
        "language_definitions": [],
        "translation_dictionaries": [],
        "supported_languages": [],
        "issues": [],
        "recommendations": []
    }

    # File basic info
    size = os.path.getsize(file_path)
    result["file_info"] = {
        "size_bytes": size,
        "size_kb": size / 1024,
        "path": file_path
    }

    # Read file content
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')

        result["file_info"]["line_count"] = len(lines)

        # Analyze classes
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('class '):
                # Look for docstring
                docstring = ""
                for j in range(1, 4):
                    if i + j < len(lines):
                        next_line = lines[i + j - 1].strip()
                        if next_line.startswith('"""') or next_line.startswith("'''"):
                            # Find end of docstring
                            for k in range(i + j, len(lines)):
                                if '"""' in lines[k] or "'''" in lines[k]:
                                    docstring = " ".join(lines[i + j - 1:k + 1])
                                    break
                            break
                        elif next_line and not next_line.startswith('#') and not next_line.startswith('class'):
                            docstring = next_line
                            break

                result["classes"].append({
                    "line": i,
                    "name": stripped,
                    "docstring": docstring
                })

        # Analyze functions
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('def '):
                result["functions"].append({
                    "line": i,
                    "name": stripped
                })

        # Find language definitions
        for i, line in enumerate(lines, 1):
            if any(keyword in line.upper() for keyword in ['LANGUAGES', 'SUPPORTED', 'LANGUAGE']):
                result["language_definitions"].append({
                    "line": i,
                    "content": line.strip()
                })

        # Find translation dictionaries
        in_dict = False
        current_dict = None
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if '{' in stripped and any(lang in stripped.upper() for lang in ['EN', 'JA', 'ZH', 'ES', 'FR', 'DE', 'KO', 'PT', 'RU']):
                in_dict = True
                current_dict = {"start_line": i, "content": []}
            elif in_dict:
                current_dict["content"].append(stripped)
                if stripped.startswith('}'):
                    in_dict = False
                    result["translation_dictionaries"].append(current_dict)
                    current_dict = None

        # Extract supported languages
        lang_codes = set()
        for line in lines:
            # Find language codes like 'en', 'ja', 'zh', etc.
            matches = re.findall(r'["\']([a-z]{2,3})["\']', line)
            for match in matches:
                if len(match) == 2 or match in ['zh-CN', 'zh-TW', 'pt-BR', 'en-US']:
                    lang_codes.add(match)

        result["supported_languages"] = sorted(list(lang_codes))

        # Identify issues
        if not result["classes"]:
            result["issues"].append("No class definitions found")

        if not result["supported_languages"]:
            result["issues"].append("No language codes found in the file")

        if len(lines) > 1000 and not result["classes"]:
            result["issues"].append("Large file without clear structure")

        # Recommendations
        if len(result["issues"]) > 2:
            result["recommendations"].append("File structure needs refactoring")

        if not result["supported_languages"]:
            result["recommendations"].append("Add language support definitions")

        if size > 250 * 1024:  # 250KB
            result["recommendations"].append("Consider splitting large file into modules")

    except Exception as e:
        result["error"] = str(e)

    return result

def analyze_hardcoded_strings(ui_file: str) -> Dict:
    """Analyze UI files for hardcoded strings that need internationalization."""

    if not os.path.exists(ui_file):
        return {"error": f"File not found: {ui_file}"}

    result = {
        "file_info": {},
        "hardcoded_strings": [],
        "string_locations": [],
        "issues": [],
        "recommendations": []
    }

    try:
        with open(ui_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')

        result["file_info"] = {
            "line_count": len(lines),
            "path": ui_file
        }

        # Find hardcoded strings in UI labels, titles, etc.
        hardcoded_patterns = [
            r'".*Monitor.*"',  # Monitor-related strings
            r'".*Settings.*"',  # Settings-related strings
            r'".*Configure.*"',  # Configuration strings
            r'".*Alert.*"',  # Alert strings
            r'".*Profile.*"',  # Profile strings
            r'".*Theme.*"',  # Theme strings
            r'".*Log.*"',  # Log strings
            r'".*Export.*"',  # Export strings
            r'".*History.*"',  # History strings
            r'".*Initializing.*"',  # Status strings
            r'".*Loading.*"',  # Loading strings
            r'".*Error.*"',  # Error strings
            r'".*Warning.*"',  # Warning strings
            r'".*Success.*"',  # Success strings
        ]

        for i, line in enumerate(lines, 1):
            for pattern in hardcoded_patterns:
                matches = re.findall(pattern, line)
                for match in matches:
                    result["hardcoded_strings"].append({
                        "line": i,
                        "string": match,
                        "context": line.strip()
                    })

        # Find specific UI string patterns
        ui_strings = []
        for i, line in enumerate(lines, 1):
            # QLabel, QPushButton, etc. text assignments
            if any(ui_widget in line for ui_widget in ['setText', 'setTitle', 'setWindowTitle']):
                string_match = re.search(r'["\']([^"\']+)["\']', line)
                if string_match:
                    ui_strings.append({
                        "line": i,
                        "string": string_match.group(1),
                        "context": line.strip()
                    })

        result["string_locations"] = ui_strings

        # Issues
        if len(result["hardcoded_strings"]) > 10:
            result["issues"].append(f"Found {len(result["hardcoded_strings"])} hardcoded strings needing internationalization")

        if len(result["string_locations"]) > 20:
            result["issues"].append(f"Found {len(result["string_locations"])} UI strings needing translation keys")

        # Recommendations
        if result["issues"]:
            result["recommendations"].append("Implement internationalization for all UI strings")
            result["recommendations"].append("Create translation keys for all hardcoded strings")
            result["recommendations"].append("Integrate i18n system with UI components")

    except Exception as e:
        result["error"] = str(e)

    return result

def main():
    """Main analysis function."""

    # Analyze internationalization file
    i18n_path = r'c:\Users\irosa\Desktop\claude\Moni\src\moni\internationalization.py'
    i18n_analysis = analyze_internationalization_file(i18n_path)

    # Analyze UI files
    ui_path = r'c:\Users\irosa\Desktop\claude\Moni\src\moni\ui\overlay.py'
    ui_analysis = analyze_hardcoded_strings(ui_path)

    # Print results
    print("=== MONI INTERNATIONALIZATION ANALYSIS ===\n")

    print("1. INTERNATIONALIZATION SYSTEM:")
    if "error" in i18n_analysis:
        print(f"❌ Error: {i18n_analysis['error']}")
    else:
        print(f"📁 File size: {i18n_analysis['file_info']['size_kb']:.1f} KB")
        print(f"📝 Lines: {i18n_analysis['file_info']['line_count']}")
        print(f"🏗️  Classes: {len(i18n_analysis['classes'])}")
        print(f"⚙️  Functions: {len(i18n_analysis['functions'])}")
        print(f"🌍 Supported languages: {len(i18n_analysis['supported_languages'])}")
        if i18n_analysis['supported_languages']:
            print(f"   Languages: {', '.join(i18n_analysis['supported_languages'])}")

        if i18n_analysis['issues']:
            print(f"\n❌ Issues found:")
            for issue in i18n_analysis['issues']:
                print(f"   - {issue}")

        if i18n_analysis['recommendations']:
            print(f"\n💡 Recommendations:")
            for rec in i18n_analysis['recommendations']:
                print(f"   - {rec}")

    print("\n2. UI INTERNATIONALIZATION:")
    if "error" in ui_analysis:
        print(f"❌ Error: {ui_analysis['error']}")
    else:
        print(f"📁 Lines: {ui_analysis['file_info']['line_count']}")
        print(f"🏷️  UI strings: {len(ui_analysis['string_locations'])}")
        print(f"📝 Hardcoded strings: {len(ui_analysis['hardcoded_strings'])}")

        if ui_analysis['issues']:
            print(f"\n❌ Issues found:")
            for issue in ui_analysis['issues']:
                print(f"   - {issue}")

        if ui_analysis['recommendations']:
            print(f"\n💡 Recommendations:")
            for rec in ui_analysis['recommendations']:
                print(f"   - {rec}")

        # Show some examples
        if ui_analysis['string_locations']:
            print(f"\n📋 Sample UI strings needing translation:")
            for item in ui_analysis['string_locations'][:10]:
                print(f"   Line {item['line']}: '{item['string']}'")

    print("\n3. OVERALL ASSESSMENT:")
    total_issues = len(i18n_analysis.get('issues', [])) + len(ui_analysis.get('issues', []))
    print(f"🔍 Total issues: {total_issues}")

    if total_issues == 0:
        print("✅ Internationalization system appears to be well-implemented")
    elif total_issues < 5:
        print("⚠️  Some improvements needed")
    else:
        print("❌ Major internationalization issues require attention")

    # Save detailed results
    output_file = r'c:\Users\irosa\Desktop\claude\Moni\i18n_analysis.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "i18n_analysis": i18n_analysis,
            "ui_analysis": ui_analysis,
            "timestamp": str(os.times())
        }, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Detailed analysis saved to: {output_file}")

if __name__ == "__main__":
    main()
