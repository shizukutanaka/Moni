#!/usr/bin/env python3
"""
Simple test to verify Atlassian UI components are working.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from moni.ui.design_tokens import DesignTokens, DEFAULT_TOKENS
    print("✓ Design tokens imported successfully")

    from moni.ui.components import (
        create_button, create_primary_button, create_danger_button,
        create_link_button, create_badge, create_lozenge,
        create_banner, create_flag, create_progress_bar,
        create_text_field, create_select, create_checkbox
    )
    print("✓ Components imported successfully")

    # Test creating a button
    button = create_button("Test Button")
    print("✓ Button created successfully")

    # Test creating other components
    badge = create_badge("Test")
    progress = create_progress_bar(value=50)
    text_field = create_text_field(placeholder="Test")
    print("✓ All basic components created successfully")

    print("\n🎉 All imports and basic component creation tests passed!")

except ImportError as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
