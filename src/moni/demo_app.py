#!/usr/bin/env python3
"""
Demo application showcasing Atlassian-style UI components for Moni system monitor.

This script demonstrates the usage of all implemented Atlassian design system components
including buttons, badges, lozenges, banners, flags, progress bars, and form controls.
"""

import sys
import psutil
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QFrame, QScrollArea, QGroupBox, QTabWidget
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont

# Import our custom components
from .ui.design_tokens import DesignTokens, DEFAULT_TOKENS
from .ui.components import (
    # Buttons
    create_button, create_primary_button, create_danger_button,
    create_link_button,

    # Status indicators
    create_badge, create_lozenge, create_status_badge, create_status_lozenge,

    # Messaging
    create_banner, create_flag, create_success_banner, create_error_banner,
    create_warning_flag,

    # Progress indicators
    create_progress_bar, create_cpu_progress_bar, create_memory_progress_bar,
    create_disk_progress_bar, create_loading_progress_bar,

    # Data tables
    create_data_table, create_process_table, create_network_table, create_disk_table,

    # Modals and dialogs
    create_modal, create_message_dialog, create_confirmation_dialog, create_error_dialog, create_success_dialog, create_settings_modal,

    # Component classes for direct instantiation
    AtlassianButton, AtlassianBadge, AtlassianLozenge,
    AtlassianBanner, AtlassianFlag, AtlassianProgressBar,
    AtlassianTextField, AtlassianSelect, AtlassianCheckbox,
    AtlassianDataTable, AtlassianModal, AtlassianMessageDialog
)


class MoniDemoWindow(QMainWindow):
    """Main demo window showcasing all Atlassian UI components."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Moni - Atlassian UI Components Demo")
        self.setMinimumSize(1200, 800)

        # Initialize design tokens
        self.design_tokens = DEFAULT_TOKENS

        # Setup UI
        self._setup_ui()

        # Start system monitoring updates
        self._start_monitoring()

    def _setup_ui(self):
        """Setup the main UI layout."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)

        # Create tab widget for organizing components
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # Add component demo tabs
        tab_widget.addTab(self._create_buttons_tab(), "Buttons")
        tab_widget.addTab(self._create_status_tab(), "Status Indicators")
        tab_widget.addTab(self._create_messaging_tab(), "Messaging")
        tab_widget.addTab(self._create_progress_tab(), "Progress Bars")
        tab_widget.addTab(self._create_data_tables_tab(), "Data Tables")
        tab_widget.addTab(self._create_modals_tab(), "Modals & Dialogs")
        tab_widget.addTab(self._create_forms_tab(), "Form Controls")
        tab_widget.addTab(self._create_system_monitor_tab(), "System Monitor")

        # Apply theme to the entire application
        self._apply_theme()

    def _create_buttons_tab(self):
        """Create the buttons demonstration tab."""
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(20)

        # Button variants section
        button_group = QGroupBox("Button Variants")
        button_layout = QGridLayout(button_group)

        # Default buttons
        button_layout.addWidget(QLabel("Default:"), 0, 0)
        button_row = QHBoxLayout()
        button_row.addWidget(create_button("Default Button", parent=button_group))
        button_row.addWidget(create_button("Disabled", parent=button_group, is_disabled=True))
        button_layout.addLayout(button_row, 0, 1)

        # Primary buttons
        button_layout.addWidget(QLabel("Primary:"), 1, 0)
        button_row = QHBoxLayout()
        button_row.addWidget(create_primary_button("Primary Button", parent=button_group))
        button_row.addWidget(create_primary_button("Disabled", parent=button_group, is_disabled=True))
        button_layout.addLayout(button_row, 1, 1)

        # Danger buttons
        button_layout.addWidget(QLabel("Danger:"), 2, 0)
        button_row = QHBoxLayout()
        button_row.addWidget(create_danger_button("Danger Button", parent=button_group))
        button_row.addWidget(create_danger_button("Disabled", parent=button_group, is_disabled=True))
        button_layout.addLayout(button_row, 2, 1)

        # Link buttons
        button_layout.addWidget(QLabel("Link:"), 3, 0)
        button_row = QHBoxLayout()
        button_row.addWidget(create_link_button("Link Button", parent=button_group))
        button_row.addWidget(create_link_button("Disabled", parent=button_group, is_disabled=True))
        button_layout.addLayout(button_row, 3, 1)

    # Subtle buttons
        button_layout.addWidget(QLabel("Subtle:"), 4, 0)
        button_row = QHBoxLayout()
        button_row.addWidget(create_button("Subtle Button", appearance="subtle", parent=button_group))
        button_row.addWidget(create_button("Disabled", appearance="subtle", parent=button_group, is_disabled=True))
        button_layout.addLayout(button_row, 4, 1)

        layout.addWidget(button_group)

        # Button sizes section
        size_group = QGroupBox("Button Sizes")
        size_layout = QVBoxLayout(size_group)

        size_layout.addWidget(create_button("Small Button", size="small", parent=size_group))
        size_layout.addWidget(create_button("Medium Button", size="medium", parent=size_group))
        size_layout.addWidget(create_button("Large Button", size="large", parent=size_group))

        layout.addWidget(size_group)

        return scroll_area

    def _create_status_tab(self):
        """Create the status indicators demonstration tab."""
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(20)

        # Badges section
        badge_group = QGroupBox("Badges")
        badge_layout = QVBoxLayout(badge_group)

        # Status badges
        status_layout = QHBoxLayout()
        status_layout.addWidget(create_status_badge("Success", parent=badge_group))
        status_layout.addWidget(create_status_badge("Warning", parent=badge_group))
        status_layout.addWidget(create_status_badge("Error", parent=badge_group))
        status_layout.addWidget(create_status_badge("Info", parent=badge_group))
        badge_layout.addLayout(status_layout)

        # Appearance badges
        appearance_layout = QHBoxLayout()
        appearance_layout.addWidget(create_badge("Neutral", appearance="neutral", parent=badge_group))
        appearance_layout.addWidget(create_badge("Success", appearance="success", parent=badge_group))
        appearance_layout.addWidget(create_badge("Warning", appearance="warning", parent=badge_group))
        appearance_layout.addWidget(create_badge("Error", appearance="error", parent=badge_group))
        appearance_layout.addWidget(create_badge("Information", appearance="information", parent=badge_group))
        appearance_layout.addWidget(create_badge("Discovery", appearance="discovery", parent=badge_group))
        badge_layout.addLayout(appearance_layout)

        layout.addWidget(badge_group)

        # Lozenges section
        lozenge_group = QGroupBox("Lozenges")
        lozenge_layout = QVBoxLayout(lozenge_group)

        # Status lozenges
        status_lozenge_layout = QHBoxLayout()
        status_lozenge_layout.addWidget(create_status_lozenge("Active", parent=lozenge_group))
        status_lozenge_layout.addWidget(create_status_lozenge("Inactive", parent=lozenge_group))
        status_lozenge_layout.addWidget(create_status_lozenge("Error", parent=lozenge_group))
        status_lozenge_layout.addWidget(create_lozenge("New", appearance="new", parent=lozenge_group))
        lozenge_layout.addLayout(status_lozenge_layout)

        # Appearance lozenges
        appearance_lozenge_layout = QHBoxLayout()
        appearance_lozenge_layout.addWidget(create_lozenge("Default", appearance="default", parent=lozenge_group))
        appearance_lozenge_layout.addWidget(create_lozenge("Success", appearance="success", parent=lozenge_group))
        appearance_lozenge_layout.addWidget(create_lozenge("Warning", appearance="warning", parent=lozenge_group))
        appearance_lozenge_layout.addWidget(create_lozenge("Error", appearance="error", parent=lozenge_group))
        appearance_lozenge_layout.addWidget(create_lozenge("Information", appearance="information", parent=lozenge_group))
        appearance_lozenge_layout.addWidget(create_lozenge("Discovery", appearance="discovery", parent=lozenge_group))
        lozenge_layout.addLayout(appearance_lozenge_layout)

        layout.addWidget(lozenge_group)

        return scroll_area

    def _create_messaging_tab(self):
        """Create the messaging demonstration tab."""
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(20)

        # Banners section
        banner_group = QGroupBox("Banners")
        banner_layout = QVBoxLayout(banner_group)

        banner_layout.addWidget(create_success_banner(
            "Operation completed successfully",
            "The system update has been applied without any issues.",
            parent=banner_group
        ))

        banner_layout.addWidget(create_banner(
            "Information",
            "This is an informational message that provides context to the user.",
            appearance="information",
            parent=banner_group
        ))

        banner_layout.addWidget(create_banner(
            "Warning",
            "Please review your settings before proceeding with this action.",
            appearance="warning",
            parent=banner_group
        ))

        banner_layout.addWidget(create_error_banner(
            "Error occurred",
            "Unable to save configuration. Please check your permissions and try again.",
            parent=banner_group
        ))

        layout.addWidget(banner_group)

        # Flags section
        flag_group = QGroupBox("Flags")
        flag_layout = QVBoxLayout(flag_group)

        flag_layout.addWidget(create_flag(
            "Success",
            "Your changes have been saved successfully.",
            appearance="success",
            parent=flag_group
        ))

        flag_layout.addWidget(create_warning_flag(
            "Warning",
            "This action cannot be undone. Please confirm before proceeding.",
            parent=flag_group
        ))

        flag_layout.addWidget(create_flag(
            "Information",
            "New updates are available for download.",
            appearance="information",
            parent=flag_group
        ))

        layout.addWidget(flag_group)

        return scroll_area

    def _create_progress_tab(self):
        """Create the progress bars demonstration tab."""
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(20)

        # Progress bar variants
        progress_group = QGroupBox("Progress Bar Variants")
        progress_layout = QVBoxLayout(progress_group)

        progress_layout.addWidget(create_progress_bar(
            value=75,
            label="Standard Progress",
            parent=progress_group
        ))

        progress_layout.addWidget(create_progress_bar(
            value=100,
            appearance="success",
            label="Completed Task",
            parent=progress_group
        ))

        progress_layout.addWidget(create_progress_bar(
            value=45,
            appearance="warning",
            label="Warning State",
            parent=progress_group
        ))

        progress_layout.addWidget(create_progress_bar(
            value=25,
            appearance="error",
            label="Error State",
            parent=progress_group
        ))

        progress_layout.addWidget(create_loading_progress_bar(
            label="Loading data...",
            parent=progress_group
        ))

        layout.addWidget(progress_group)

        # System monitoring simulation
        system_group = QGroupBox("System Monitoring (Demo)")
        system_layout = QVBoxLayout(system_group)

        self.demo_cpu_bar = create_cpu_progress_bar(value=45, parent=system_group)
        self.demo_memory_bar = create_memory_progress_bar(value=67, parent=system_group)
        self.demo_disk_bar = create_disk_progress_bar(value=82, parent=system_group)

        system_layout.addWidget(self.demo_cpu_bar)
        system_layout.addWidget(self.demo_memory_bar)
        system_layout.addWidget(self.demo_disk_bar)

        layout.addWidget(system_group)

        return scroll_area

    def _create_data_tables_tab(self):
        """Create the data tables demonstration tab."""
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(20)

        # Process Table section
        process_group = QGroupBox("Process Table")
        process_layout = QVBoxLayout(process_group)

        # Create sample process data
        sample_processes = [
            ["System", 4, 2.1, 15.2, "Running", "SYSTEM"],
            ["chrome.exe", 1234, 8.5, 245.3, "Running", "user"],
            ["python.exe", 5678, 1.2, 45.6, "Running", "user"],
            ["explorer.exe", 9101, 0.8, 78.9, "Running", "user"],
            ["svchost.exe", 1121, 0.3, 12.4, "Running", "SYSTEM"],
            ["notepad.exe", 3141, 0.1, 8.7, "Running", "user"],
        ]

        process_table = create_process_table(parent=process_group)
        process_table.set_data(sample_processes)

        # Add progress bars to CPU and Memory columns
        for row_idx, process in enumerate(sample_processes):
            cpu_bar = create_progress_bar(value=int(process[2]), show_percentage=False, parent=process_table)
            cpu_bar.setFixedHeight(20)
            process_table._table.setCellWidget(row_idx, 2, cpu_bar)

            mem_bar = create_progress_bar(value=int(process[3] / 10), show_percentage=False, parent=process_table)
            mem_bar.setFixedHeight(20)
            process_table._table.setCellWidget(row_idx, 3, mem_bar)

            # Add status badge
            status_badge = create_status_badge(process[4], parent=process_table)
            process_table._table.setCellWidget(row_idx, 4, status_badge)

        process_layout.addWidget(process_table)
        layout.addWidget(process_group)

        # Network Table section
        network_group = QGroupBox("Network Connections Table")
        network_layout = QVBoxLayout(network_group)

        # Create sample network data
        sample_network = [
            ["TCP", "127.0.0.1:54321", "127.0.0.1:54322", "ESTABLISHED", 1234, "chrome.exe"],
            ["TCP", "192.168.1.100:443", "104.18.32.1:443", "ESTABLISHED", 5678, "python.exe"],
            ["UDP", "0.0.0.0:68", "192.168.1.1:67", "ESTABLISHED", 9101, "dhcp"],
            ["TCP", "127.0.0.1:3306", "127.0.0.1:3307", "LISTEN", 1121, "mysqld.exe"],
        ]

        network_table = create_network_table(parent=network_group)
        network_table.set_data(sample_network)

        # Add status badges
        for row_idx, connection in enumerate(sample_network):
            status_badge = create_status_badge(connection[3], parent=network_table)
            network_table._table.setCellWidget(row_idx, 3, status_badge)

        network_layout.addWidget(network_table)
        layout.addWidget(network_group)

        # Disk Table section
        disk_group = QGroupBox("Disk Usage Table")
        disk_layout = QVBoxLayout(disk_group)

        # Create sample disk data
        sample_disks = [
            ["/", "ext4", "50.0 GB", "25.0 GB", "25.0 GB", 50, "Normal"],
            ["/home", "ext4", "100.0 GB", "75.0 GB", "25.0 GB", 75, "Warning"],
            ["C:", "NTFS", "500.0 GB", "450.0 GB", "50.0 GB", 90, "Critical"],
        ]

        disk_table = create_disk_table(parent=disk_group)
        disk_table.set_data(sample_disks)

        # Add progress bars and status badges
        for row_idx, disk in enumerate(sample_disks):
            usage_bar = create_progress_bar(value=disk[5], show_percentage=False, parent=disk_table)
            usage_bar.setFixedHeight(20)
            disk_table._table.setCellWidget(row_idx, 5, usage_bar)

            # Determine status based on usage
            usage = disk[5]
            if usage >= 90:
                status_badge = create_status_badge("Critical", parent=disk_table)
            elif usage >= 80:
                status_badge = create_status_badge("Warning", parent=disk_table)
            else:
                status_badge = create_status_badge("Normal", parent=disk_table)

            disk_table._table.setCellWidget(row_idx, 6, status_badge)

        disk_layout.addWidget(disk_table)
        layout.addWidget(disk_group)

        return scroll_area

    def _create_modals_tab(self):
        """Create the modals and dialogs demonstration tab."""
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(20)

        # Message Dialogs section
        dialogs_group = QGroupBox("Message Dialogs")
        dialogs_layout = QVBoxLayout(dialogs_group)

        # Create buttons to trigger different dialogs
        info_button = create_button("Show Info Dialog", parent=dialogs_group)
        info_button.clicked.connect(lambda: self._show_info_dialog())

        warning_button = create_button("Show Warning Dialog", parent=dialogs_group)
        warning_button.clicked.connect(lambda: self._show_warning_dialog())

        error_button = create_danger_button("Show Error Dialog", parent=dialogs_group)
        error_button.clicked.connect(lambda: self._show_error_dialog())

        success_button = create_primary_button("Show Success Dialog", parent=dialogs_group)
        success_button.clicked.connect(lambda: self._show_success_dialog())

        confirm_button = create_button("Show Confirmation Dialog", parent=dialogs_group)
        confirm_button.clicked.connect(lambda: self._show_confirmation_dialog())

        dialogs_layout.addWidget(info_button)
        dialogs_layout.addWidget(warning_button)
        dialogs_layout.addWidget(error_button)
        dialogs_layout.addWidget(success_button)
        dialogs_layout.addWidget(confirm_button)

        layout.addWidget(dialogs_group)

        # Modal Sizes section
        sizes_group = QGroupBox("Modal Sizes")
        sizes_layout = QVBoxLayout(sizes_group)

        small_modal_button = create_button("Small Modal", parent=sizes_group)
        small_modal_button.clicked.connect(lambda: self._show_modal("small"))

        medium_modal_button = create_button("Medium Modal", parent=sizes_group)
        medium_modal_button.clicked.connect(lambda: self._show_modal("medium"))

        large_modal_button = create_button("Large Modal", parent=sizes_group)
        large_modal_button.clicked.connect(lambda: self._show_modal("large"))

        sizes_layout.addWidget(small_modal_button)
        sizes_layout.addWidget(medium_modal_button)
        sizes_layout.addWidget(large_modal_button)

        layout.addWidget(sizes_group)

        # Custom Modal section
        custom_group = QGroupBox("Custom Modal")
        custom_layout = QVBoxLayout(custom_group)

        custom_modal_button = create_primary_button("Show Custom Settings Modal", parent=custom_group)
        custom_modal_button.clicked.connect(lambda: self._show_custom_modal())

        custom_layout.addWidget(custom_modal_button)
        layout.addWidget(custom_group)

        return scroll_area

    def _show_info_dialog(self):
        """Show an info message dialog."""
        dialog = create_message_dialog(
            title="Information",
            message="This is an informational message to provide context to the user. It can contain multiple lines of text and will wrap appropriately.",
            dialog_type="info",
            parent=self
        )
        dialog.exec()

    def _show_warning_dialog(self):
        """Show a warning message dialog."""
        dialog = create_message_dialog(
            title="Warning",
            message="This action may have unintended consequences. Please review your settings before proceeding.",
            dialog_type="warning",
            buttons=["Cancel", "Continue"],
            parent=self
        )
        result = dialog.exec()
        if result == dialog.Accepted:
            print("User chose to continue despite warning")

    def _show_error_dialog(self):
        """Show an error message dialog."""
        dialog = create_error_dialog(
            title="Connection Failed",
            message="Unable to connect to the system monitoring service. Please check your network connection and try again.",
            parent=self
        )
        dialog.exec()

    def _show_success_dialog(self):
        """Show a success message dialog."""
        dialog = create_success_dialog(
            title="Settings Saved",
            message="Your system monitoring preferences have been saved successfully. Changes will take effect immediately.",
            parent=self
        )
        dialog.exec()

    def _show_confirmation_dialog(self):
        """Show a confirmation dialog."""
        dialog = create_confirmation_dialog(
            title="Delete Process",
            message="Are you sure you want to terminate the selected process? This action cannot be undone.",
            parent=self
        )
        result = dialog.exec()
        if result == dialog.Accepted:
            print("User confirmed process termination")
        else:
            print("User cancelled process termination")

    def _show_modal(self, size: str):
        """Show a modal of the specified size."""
        modal = create_modal(
            title=f"{size.title()} Modal Dialog",
            size=size,
            parent=self
        )

        # Add some content
        from PySide6.QtWidgets import QLabel
        content_label = QLabel(f"This is a {size} modal dialog. It demonstrates the different size options available.")
        content_label.setWordWrap(True)
        modal.set_content_widget(content_label)

        # Add buttons
        modal.add_action_button("Close", "secondary")
        modal.add_action_button("OK", "primary")

        modal.exec()

    def _show_custom_modal(self):
        """Show a custom settings modal."""
        modal = create_settings_modal(parent=self)

        # Create settings content
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QGroupBox

        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)

        # Monitoring settings
        monitor_group = QGroupBox("Monitoring Settings")
        monitor_layout = QVBoxLayout(monitor_group)

        # Add some sample settings
        cpu_checkbox = create_checkbox("Monitor CPU usage", is_checked=True, parent=monitor_group)
        memory_checkbox = create_checkbox("Monitor memory usage", is_checked=True, parent=monitor_group)
        disk_checkbox = create_checkbox("Monitor disk usage", is_checked=True, parent=monitor_group)
        network_checkbox = create_checkbox("Monitor network activity", is_checked=False, parent=monitor_group)

        monitor_layout.addWidget(cpu_checkbox)
        monitor_layout.addWidget(memory_checkbox)
        monitor_layout.addWidget(disk_checkbox)
        monitor_layout.addWidget(network_checkbox)

        settings_layout.addWidget(monitor_group)

        # Update interval setting
        interval_group = QGroupBox("Update Settings")
        interval_layout = QVBoxLayout(interval_group)

        update_interval = create_select(
            items=["1 second", "2 seconds", "5 seconds", "10 seconds"],
            current_index=1,
            helper_text="How often to refresh system data",
            parent=interval_group
        )

        interval_layout.addWidget(update_interval)
        settings_layout.addWidget(interval_group)

        modal.set_content_widget(settings_widget)

        # Connect save button
        def on_save():
            print("Settings saved!")
            print(f"CPU monitoring: {cpu_checkbox.is_checked}")
            print(f"Memory monitoring: {memory_checkbox.is_checked}")
            print(f"Disk monitoring: {disk_checkbox.is_checked}")
            print(f"Network monitoring: {network_checkbox.is_checked}")
            print(f"Update interval: {update_interval.current_text}")

        # The modal already has Save/Cancel buttons from create_settings_modal
        # We need to connect to the accept signal
        modal.accepted.connect(on_save)

        modal.exec()

    def _create_forms_tab(self):
        """Create the form controls demonstration tab."""
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(20)

        # Text fields section
        text_group = QGroupBox("Text Fields")
        text_layout = QVBoxLayout(text_group)

        text_layout.addWidget(create_text_field(
            placeholder="Enter your name",
            helper_text="This field is required for identification.",
            parent=text_group
        ))

        text_layout.addWidget(create_text_field(
            placeholder="Enter your email",
            helper_text="We'll use this to send you updates.",
            parent=text_group
        ))

        text_layout.addWidget(create_text_field(
            text="Error example",
            validation_state="error",
            helper_text="This email address is not valid.",
            parent=text_group
        ))

        text_layout.addWidget(create_text_field(
            text="Warning example",
            validation_state="warning",
            helper_text="Please review this field before submitting.",
            parent=text_group
        ))

        layout.addWidget(text_group)

        # Select dropdowns section
        select_group = QGroupBox("Select Dropdowns")
        select_layout = QVBoxLayout(select_group)

        select_layout.addWidget(create_select(
            items=["Option 1", "Option 2", "Option 3", "Option 4"],
            placeholder="Choose an option",
            helper_text="Select one option from the list.",
            parent=select_group
        ))

        select_layout.addWidget(create_select(
            items=["Light Theme", "Dark Theme", "High Contrast"],
            current_index=0,
            helper_text="Choose your preferred theme.",
            parent=select_group
        ))

        layout.addWidget(select_group)

        # Checkboxes section
        checkbox_group = QGroupBox("Checkboxes")
        checkbox_layout = QVBoxLayout(checkbox_group)

        checkbox_layout.addWidget(create_checkbox(
            "Enable notifications",
            helper_text="Receive alerts about system events.",
            parent=checkbox_group
        ))

        checkbox_layout.addWidget(create_checkbox(
            "Auto-start on boot",
            helper_text="Launch the application automatically when the system starts.",
            is_checked=True,
            parent=checkbox_group
        ))

        checkbox_layout.addWidget(create_checkbox(
            "Enable advanced features",
            helper_text="Access experimental features and settings.",
            parent=checkbox_group
        ))

        layout.addWidget(checkbox_group)

        return scroll_area

    def _create_system_monitor_tab(self):
        """Create the system monitor demonstration tab."""
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(20)

        # System status overview
        status_group = QGroupBox("System Status")
        status_layout = QHBoxLayout(status_group)

        # Status indicators
        status_layout.addWidget(create_status_badge("System Online", parent=status_group))
        status_layout.addWidget(create_status_lozenge("All Services OK", parent=status_group))
        status_layout.addWidget(create_lozenge("Uptime: 5d 12h", parent=status_group))

        layout.addWidget(status_group)

        # Resource monitoring
        resources_group = QGroupBox("Resource Monitoring")
        resources_layout = QVBoxLayout(resources_group)

        # Real-time progress bars (will be updated by timer)
        self.cpu_progress = create_cpu_progress_bar(parent=resources_group)
        self.memory_progress = create_memory_progress_bar(parent=resources_group)
        self.disk_progress = create_disk_progress_bar(parent=resources_group)

        resources_layout.addWidget(self.cpu_progress)
        resources_layout.addWidget(self.memory_progress)
        resources_layout.addWidget(self.disk_progress)

        layout.addWidget(resources_group)

        # Network status
        network_group = QGroupBox("Network Status")
        network_layout = QVBoxLayout(network_group)

        network_layout.addWidget(create_flag(
            "Network Connected",
            "Internet connection is active and stable.",
            appearance="success",
            parent=network_group
        ))

        network_layout.addWidget(create_select(
            items=["Ethernet", "Wi-Fi", "Bluetooth"],
            current_index=1,
            helper_text="Primary network interface",
            parent=network_group
        ))

        layout.addWidget(network_group)

        return scroll_area

    def _apply_theme(self):
        """Apply the design system theme to the application."""
        from .ux_accessibility import ux_manager

        # Apply UX enhancements including theme and accessibility
        ux_manager.apply_ux_enhancements(self)

    def _start_monitoring(self):
        """Start system monitoring updates."""
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._update_monitoring)
        self.monitor_timer.start(2000)  # Update every 2 seconds

        # Initial update
        self._update_monitoring()

    def _update_monitoring(self):
        """Update system monitoring data."""
        try:
            # Get real system data
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Update progress bars
            if hasattr(self, 'cpu_progress'):
                self.cpu_progress.set_value(int(cpu_percent))

            if hasattr(self, 'memory_progress'):
                self.memory_progress.set_value(int(memory.percent))

            if hasattr(self, 'disk_progress'):
                self.disk_progress.set_value(int(disk.percent))

            # Update demo bars too
            if hasattr(self, 'demo_cpu_bar'):
                self.demo_cpu_bar.set_value(int(cpu_percent))

            if hasattr(self, 'demo_memory_bar'):
                self.demo_memory_bar.set_value(int(memory.percent))

            if hasattr(self, 'demo_disk_bar'):
                self.demo_disk_bar.set_value(int(disk.percent))

        except Exception as e:
            print(f"Error updating monitoring data: {e}")


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("Moni")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Moni Team")

    # Create and show the main window
    window = MoniDemoWindow()
    window.show()

    # Start the event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
