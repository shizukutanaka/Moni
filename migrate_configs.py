#!/usr/bin/env python3
"""
設定システム統合スクリプト
古い設定ファイルをバックアップし、新しい統合システムに移行します。
"""

import shutil
from pathlib import Path

def migrate_config_files():
    """設定ファイルの移行を実行"""
    base_path = Path(__file__).parent

    # config.py を config_legacy.py にバックアップ
    config_py = base_path / "src" / "moni" / "config.py"
    config_legacy = base_path / "src" / "moni" / "config_legacy.py"

    if config_py.exists() and not config_legacy.exists():
        print(f"Backing up {config_py} to {config_legacy}")
        shutil.copy2(config_py, config_legacy)

    # config_manager.py を config_manager_legacy.py にバックアップ
    config_manager_py = base_path / "src" / "moni" / "config_manager.py"
    config_manager_legacy = base_path / "src" / "moni" / "config_manager_legacy.py"

    if config_manager_py.exists() and not config_manager_legacy.exists():
        print(f"Backing up {config_manager_py} to {config_manager_legacy}")
        shutil.copy2(config_manager_py, config_manager_legacy)

    # secure_config.py を secure_config_legacy.py にバックアップ
    secure_config_py = base_path / "src" / "moni" / "secure_config.py"
    secure_config_legacy = base_path / "src" / "moni" / "secure_config_legacy.py"

    if secure_config_py.exists() and not secure_config_legacy.exists():
        print(f"Backing up {secure_config_py} to {secure_config_legacy}")
        shutil.copy2(secure_config_py, secure_config_legacy)

    print("Configuration file migration completed!")

if __name__ == "__main__":
    migrate_config_files()
