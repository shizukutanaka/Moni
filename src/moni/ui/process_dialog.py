"""Process Manager Dialog for advanced process control."""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QLabel, QMessageBox,
    QHeaderView, QMenu, QSpinBox, QGroupBox, QTextEdit, QSplitter,
    QProgressBar, QTabWidget, QWidget, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PySide6.QtGui import QFont, QAction, QIcon

from ..process_manager import ProcessManager, ProcessSearchFilter, ProcessStatus, ProcessPriority, ProcessInfo
from .design_tokens import DesignTokens, DEFAULT_TOKENS


class ProcessUpdateWorker(QThread):
    """Worker thread for updating process information."""
    processes_updated = pyqtSignal(list)

    def __init__(self, process_manager: ProcessManager, filter_obj: ProcessSearchFilter):
        super().__init__()
        self.process_manager = process_manager
        self.filter_obj = filter_obj
        self.running = True

    def run(self):
        while self.running:
            try:
                processes = self.process_manager.get_process_list(self.filter_obj, force_refresh=True)
                self.processes_updated.emit(processes)
                self.msleep(2000)  # Update every 2 seconds
            except Exception:
                break

    def stop(self):
        self.running = False


class ProcessManagerDialog(QDialog):
    """Advanced process manager dialog with search, filtering, and control."""

    def __init__(self, parent: Optional[QWidget] = None, design_tokens: Optional[DesignTokens] = None):
        super().__init__(parent)
        self.design_tokens = design_tokens or DEFAULT_TOKENS
        self.setWindowTitle("Process Manager - Moni")
        self.setMinimumSize(1000, 600)
        self.resize(1200, 700)

        self.process_manager = ProcessManager()
        self.current_filter = ProcessSearchFilter()
        self.selected_processes: List[ProcessInfo] = []
        self.update_worker: Optional[ProcessUpdateWorker] = None

        self._setup_ui()
        self._setup_auto_refresh()
        self._refresh_processes()

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Create splitter for main content
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        # Top section: Filters and controls
        filter_widget = self._create_filter_widget()
        splitter.addWidget(filter_widget)

        # Middle section: Process table
        table_widget = self._create_table_widget()
        splitter.addWidget(table_widget)

        # Bottom section: Process details and actions
        details_widget = self._create_details_widget()
        splitter.addWidget(details_widget)

        # Set splitter proportions
        splitter.setSizes([150, 400, 200])

        # Button layout
        button_layout = QHBoxLayout()

        refresh_button = QPushButton("Refresh")
        refresh_button.setStyleSheet(self._get_button_style())
        refresh_button.clicked.connect(self._refresh_processes)
        button_layout.addWidget(refresh_button)

        self.auto_refresh_checkbox = QCheckBox("Auto Refresh")
        self.auto_refresh_checkbox.setChecked(True)
        self.auto_refresh_checkbox.setStyleSheet(self._get_checkbox_style())
        self.auto_refresh_checkbox.toggled.connect(self._toggle_auto_refresh)
        button_layout.addWidget(self.auto_refresh_checkbox)

        button_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.setStyleSheet(self._get_button_style())
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def _get_button_style(self) -> str:
        """Get stylesheet for buttons."""
        return f"""
            QPushButton {{
                background-color: {self.design_tokens.colors.surface};
                color: {self.design_tokens.colors.text};
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
                border-radius: {self.design_tokens.borders.border_radius}px;
                padding: {self.design_tokens.spacing.space_100}px {self.design_tokens.spacing.space_200}px;
                font-size: {self.design_tokens.typography.font_size_sm}px;
                font-weight: {self.design_tokens.typography.font_weight_medium};
            }}
            QPushButton:hover {{
                background-color: {self.design_tokens.colors.primary};
                color: white;
            }}
            QPushButton:pressed {{
                background-color: {self.design_tokens.colors.primary_pressed};
            }}
        """

    def _get_checkbox_style(self) -> str:
        """Get stylesheet for checkboxes."""
        return f"""
            QCheckBox {{
                color: {self.design_tokens.colors.text};
                font-size: {self.design_tokens.typography.font_size_sm}px;
                spacing: {self.design_tokens.spacing.space_100}px;
            }}
            QCheckBox::indicator {{
                width: {self.design_tokens.spacing.space_200}px;
                height: {self.design_tokens.spacing.space_200}px;
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
                border-radius: {self.design_tokens.borders.border_radius_small}px;
                background-color: {self.design_tokens.colors.surface};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.design_tokens.colors.primary};
                border-color: {self.design_tokens.colors.primary};
            }}
        """

    def _get_input_style(self) -> str:
        """Get stylesheet for input fields."""
        return f"""
            QLineEdit, QComboBox, QSpinBox {{
                background-color: {self.design_tokens.colors.surface};
                color: {self.design_tokens.colors.text};
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
                border-radius: {self.design_tokens.borders.border_radius}px;
                padding: {self.design_tokens.spacing.space_075}px {self.design_tokens.spacing.space_100}px;
                font-size: {self.design_tokens.typography.font_size_sm}px;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border-color: {self.design_tokens.colors.border_focused};
                outline: none;
            }}
        """

    def _get_label_style(self) -> str:
        """Get stylesheet for labels."""
        return f"""
            QLabel {{
                color: {self.design_tokens.colors.text};
                font-size: {self.design_tokens.typography.font_size_sm}px;
                font-weight: {self.design_tokens.typography.font_weight_medium};
            }}
        """

    def _get_group_box_style(self) -> str:
        """Get stylesheet for group boxes."""
        return f"""
            QGroupBox {{
                font-size: {self.design_tokens.typography.font_size_sm}px;
                font-weight: {self.design_tokens.typography.font_weight_medium};
                color: {self.design_tokens.colors.text};
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
                border-radius: {self.design_tokens.borders.border_radius}px;
                margin-top: {self.design_tokens.spacing.space_200}px;
                padding-top: {self.design_tokens.spacing.space_200}px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {self.design_tokens.spacing.space_100}px;
                padding: 0 {self.design_tokens.spacing.space_100}px 0 {self.design_tokens.spacing.space_100}px;
            }}
        """

    def _create_filter_widget(self) -> QWidget:
        """Create the filter controls widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Filter group
        filter_group = QGroupBox("Filters")
        filter_group.setStyleSheet(self._get_group_box_style())
        filter_layout = QHBoxLayout(filter_group)

        # Search field
        search_layout = QVBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet(self._get_label_style())
        search_layout.addWidget(search_label)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Process name or command...")
        self.search_input.setStyleSheet(self._get_input_style())
        self.search_input.textChanged.connect(self._update_filter)
        search_layout.addWidget(self.search_input)
        filter_layout.addLayout(search_layout)

        # Status filter
        status_layout = QVBoxLayout()
        status_label = QLabel("Status:")
        status_label.setStyleSheet(self._get_label_style())
        status_layout.addWidget(status_label)
        self.status_filter = QComboBox()
        self.status_filter.addItem("All", None)
        for status in ProcessStatus:
            self.status_filter.addItem(status.value.title(), status)
        self.status_filter.setStyleSheet(self._get_input_style())
        self.status_filter.currentTextChanged.connect(self._update_filter)
        status_layout.addWidget(self.status_filter)
        filter_layout.addLayout(status_layout)

        # CPU threshold
        cpu_layout = QVBoxLayout()
        cpu_label = QLabel("Min CPU %:")
        cpu_label.setStyleSheet(self._get_label_style())
        cpu_layout.addWidget(cpu_label)
        self.cpu_threshold = QSpinBox()
        self.cpu_threshold.setRange(0, 100)
        self.cpu_threshold.setValue(0)
        self.cpu_threshold.setStyleSheet(self._get_input_style())
        self.cpu_threshold.valueChanged.connect(self._update_filter)
        cpu_layout.addWidget(self.cpu_threshold)
        filter_layout.addLayout(cpu_layout)

        # Memory threshold
        memory_layout = QVBoxLayout()
        memory_label = QLabel("Min Memory %:")
        memory_label.setStyleSheet(self._get_label_style())
        memory_layout.addWidget(memory_label)
        self.memory_threshold = QSpinBox()
        self.memory_threshold.setRange(0, 100)
        self.memory_threshold.setValue(0)
        self.memory_threshold.setStyleSheet(self._get_input_style())
        self.memory_threshold.valueChanged.connect(self._update_filter)
        memory_layout.addWidget(self.memory_threshold)
        filter_layout.addLayout(memory_layout)

        # System processes checkbox
        self.show_system_processes = QCheckBox("Show System Processes")
        self.show_system_processes.setChecked(True)
        self.show_system_processes.setStyleSheet(self._get_checkbox_style())
        self.show_system_processes.toggled.connect(self._update_filter)
        filter_layout.addWidget(self.show_system_processes)

        # Search in command line checkbox
        self.search_cmdline = QCheckBox("Search in Command Line")
        self.search_cmdline.setStyleSheet(self._get_checkbox_style())
        self.search_cmdline.toggled.connect(self._update_filter)
        filter_layout.addWidget(self.search_cmdline)

        layout.addWidget(filter_group)

        # Statistics
        self.stats_label = QLabel("Processes: 0 | CPU: 0% | Memory: 0%")
        self.stats_label.setStyleSheet(self._get_label_style() + "font-weight: bold; padding: 5px;")
        layout.addWidget(self.stats_label)

        return widget

    def _create_table_widget(self) -> QWidget:
        """Create the process table widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Process table
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(9)
        self.process_table.setHorizontalHeaderLabels([
            "PID", "Name", "Status", "CPU %", "Memory %", "Memory (MB)",
            "Threads", "User", "Uptime"
        ])
        self.process_table.setStyleSheet(self._get_table_style())

        # Configure table
        header = self.process_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # PID
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Name
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # CPU %
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Memory %
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Memory MB
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Threads
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # User
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # Uptime

        self.process_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.process_table.setAlternatingRowColors(True)
        self.process_table.setSortingEnabled(True)
        self.process_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.process_table.customContextMenuRequested.connect(self._show_context_menu)
        self.process_table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.process_table)
        return widget

    def _get_table_style(self) -> str:
        """Get stylesheet for table widgets."""
        return f"""
            QTableWidget {{
                background-color: {self.design_tokens.colors.surface};
                color: {self.design_tokens.colors.text};
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
                border-radius: {self.design_tokens.borders.border_radius}px;
                gridline-color: {self.design_tokens.colors.border};
                selection-background-color: {self.design_tokens.colors.primary};
                selection-color: white;
            }}
            QTableWidget::item {{
                padding: {self.design_tokens.spacing.space_075}px;
                border-bottom: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
            }}
            QTableWidget::item:selected {{
                background-color: {self.design_tokens.colors.primary};
                color: white;
            }}
            QTableWidget::item:alternate {{
                background-color: {self.design_tokens.colors.background};
            }}
            QHeaderView::section {{
                background-color: {self.design_tokens.colors.surface};
                color: {self.design_tokens.colors.text};
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
                padding: {self.design_tokens.spacing.space_100}px;
                font-size: {self.design_tokens.typography.font_size_sm}px;
                font-weight: {self.design_tokens.typography.font_weight_medium};
            }}
        """

    def _create_details_widget(self) -> QWidget:
        """Create the process details widget."""
        widget = QTabWidget()
        widget.setStyleSheet(self._get_tab_widget_style())

        # Process details tab
        details_tab = QWidget()
        details_layout = QVBoxLayout(details_tab)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setStyleSheet(self._get_text_edit_style())
        details_layout.addWidget(self.details_text)

        # Action buttons
        action_layout = QHBoxLayout()

        self.terminate_button = QPushButton("Terminate")
        self.terminate_button.setEnabled(False)
        self.terminate_button.setStyleSheet(self._get_danger_button_style())
        self.terminate_button.clicked.connect(self._terminate_process)
        action_layout.addWidget(self.terminate_button)

        self.kill_button = QPushButton("Force Kill")
        self.kill_button.setEnabled(False)
        self.kill_button.setStyleSheet(self._get_danger_button_style())
        self.kill_button.clicked.connect(self._kill_process)
        action_layout.addWidget(self.kill_button)

        self.suspend_button = QPushButton("Suspend")
        self.suspend_button.setEnabled(False)
        self.suspend_button.setStyleSheet(self._get_button_style())
        self.suspend_button.clicked.connect(self._suspend_process)
        action_layout.addWidget(self.suspend_button)

        self.resume_button = QPushButton("Resume")
        self.resume_button.setEnabled(False)
        self.resume_button.setStyleSheet(self._get_button_style())
        self.resume_button.clicked.connect(self._resume_process)
        action_layout.addWidget(self.resume_button)

        # Priority controls
        priority_layout = QHBoxLayout()
        priority_layout.addWidget(QLabel("Priority:"))
        self.priority_combo = QComboBox()
        for priority in ProcessPriority:
            self.priority_combo.addItem(priority.value.replace('_', ' ').title(), priority)
        self.priority_combo.setEnabled(False)
        self.priority_combo.setStyleSheet(self._get_input_style())
        self.priority_combo.currentTextChanged.connect(self._change_priority)
        priority_layout.addWidget(self.priority_combo)

        action_layout.addLayout(priority_layout)
        action_layout.addStretch()

        details_layout.addLayout(action_layout)
        widget.addTab(details_tab, "Process Details")

        # Process tree tab
        tree_tab = QWidget()
        tree_layout = QVBoxLayout(tree_tab)

        self.process_tree = QTreeWidget()
        self.process_tree.setHeaderLabels(["PID", "Name", "CPU %", "Memory %"])
        self.process_tree.setStyleSheet(self._get_tree_style())
        tree_layout.addWidget(self.process_tree)

        widget.addTab(tree_tab, "Process Tree")

        return widget

    def _get_tab_widget_style(self) -> str:
        """Get stylesheet for tab widgets."""
        return f"""
            QTabWidget::pane {{
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
                border-radius: {self.design_tokens.borders.border_radius}px;
                background-color: {self.design_tokens.colors.surface};
                top: -{self.design_tokens.borders.border_width}px;
            }}
            QTabBar::tab {{
                background-color: {self.design_tokens.colors.background};
                color: {self.design_tokens.colors.text};
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
                border-bottom: none;
                border-top-left-radius: {self.design_tokens.borders.border_radius}px;
                border-top-right-radius: {self.design_tokens.borders.border_radius}px;
                padding: {self.design_tokens.spacing.space_100}px {self.design_tokens.spacing.space_200}px;
                margin-right: {self.design_tokens.spacing.space_025}px;
            }}
            QTabBar::tab:selected {{
                background-color: {self.design_tokens.colors.surface};
                color: {self.design_tokens.colors.text};
            }}
            QTabBar::tab:hover {{
                background-color: {self.design_tokens.colors.primary};
                color: white;
            }}
        """

    def _get_text_edit_style(self) -> str:
        """Get stylesheet for text edit widgets."""
        return f"""
            QTextEdit {{
                background-color: {self.design_tokens.colors.surface};
                color: {self.design_tokens.colors.text};
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
                border-radius: {self.design_tokens.borders.border_radius}px;
                padding: {self.design_tokens.spacing.space_100}px;
                font-family: {self.design_tokens.typography.font_family_mono};
                font-size: {self.design_tokens.typography.font_size_sm}px;
            }}
        """

    def _get_tree_style(self) -> str:
        """Get stylesheet for tree widgets."""
        return f"""
            QTreeWidget {{
                background-color: {self.design_tokens.colors.surface};
                color: {self.design_tokens.colors.text};
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
                border-radius: {self.design_tokens.borders.border_radius}px;
            }}
            QTreeWidget::item {{
                padding: {self.design_tokens.spacing.space_075}px;
                border-bottom: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
            }}
            QTreeWidget::item:selected {{
                background-color: {self.design_tokens.colors.primary};
                color: white;
            }}
            QTreeWidget::header {{
                background-color: {self.design_tokens.colors.surface};
                color: {self.design_tokens.colors.text};
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
                padding: {self.design_tokens.spacing.space_100}px;
                font-size: {self.design_tokens.typography.font_size_sm}px;
                font-weight: {self.design_tokens.typography.font_weight_medium};
            }}
        """

    def _get_danger_button_style(self) -> str:
        """Get stylesheet for danger buttons (terminate, kill)."""
        return f"""
            QPushButton {{
                background-color: {self.design_tokens.colors.error};
                color: white;
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.error};
                border-radius: {self.design_tokens.borders.border_radius}px;
                padding: {self.design_tokens.spacing.space_100}px {self.design_tokens.spacing.space_200}px;
                font-size: {self.design_tokens.typography.font_size_sm}px;
                font-weight: {self.design_tokens.typography.font_weight_medium};
            }}
            QPushButton:hover {{
                background-color: {self.design_tokens.colors.error};
                opacity: 0.8;
            }}
            QPushButton:pressed {{
                background-color: {self.design_tokens.colors.error};
                opacity: 0.9;
            }}
            QPushButton:disabled {{
                background-color: {self.design_tokens.colors.text_disabled};
                color: {self.design_tokens.colors.text};
                border-color: {self.design_tokens.colors.text_disabled};
            }}
        """

    def _update_filter(self):
        """Update the process filter based on UI controls."""
        self.current_filter.name_filter = self.search_input.text() or None
        self.current_filter.status_filter = self.status_filter.currentData()

        cpu_threshold = self.cpu_threshold.value()
        self.current_filter.cpu_threshold = cpu_threshold if cpu_threshold > 0 else None

        memory_threshold = self.memory_threshold.value()
        self.current_filter.memory_threshold = memory_threshold if memory_threshold > 0 else None

        if not self.show_system_processes.isChecked():
            self.current_filter.system_processes = False
        else:
            self.current_filter.system_processes = None

        self.current_filter.search_cmdline = self.search_cmdline.isChecked()

        # Refresh with new filter
        self._refresh_processes()

    def _refresh_processes(self):
        """Refresh the process list."""
        processes = self.process_manager.get_process_list(self.current_filter, force_refresh=True)
        self._populate_table(processes)
        self._update_statistics(processes)

    def _populate_table(self, processes: List[ProcessInfo]):
        """Populate the process table with data."""
        self.process_table.setRowCount(len(processes))

        for row, process in enumerate(processes):
            # PID
            pid_item = QTableWidgetItem(str(process.pid))
            pid_item.setData(Qt.UserRole, process)  # Store process object
            self.process_table.setItem(row, 0, pid_item)

            # Name
            name_item = QTableWidgetItem(process.name)
            if process.is_system_process:
                name_item.setFont(QFont("", -1, QFont.Bold))
            self.process_table.setItem(row, 1, name_item)

            # Status
            status_item = QTableWidgetItem(process.status.value.title())
            self.process_table.setItem(row, 2, status_item)

            # CPU %
            cpu_item = QTableWidgetItem(f"{process.cpu_percent:.1f}")
            if process.cpu_percent > 50:
                cpu_item.setBackground(Qt.red)
            elif process.cpu_percent > 25:
                cpu_item.setBackground(Qt.yellow)
            self.process_table.setItem(row, 3, cpu_item)

            # Memory %
            memory_item = QTableWidgetItem(f"{process.memory_percent:.1f}")
            if process.memory_percent > 10:
                memory_item.setBackground(Qt.red)
            elif process.memory_percent > 5:
                memory_item.setBackground(Qt.yellow)
            self.process_table.setItem(row, 4, memory_item)

            # Memory MB
            memory_mb = process.memory_rss / (1024 * 1024)
            memory_mb_item = QTableWidgetItem(f"{memory_mb:.1f}")
            self.process_table.setItem(row, 5, memory_mb_item)

            # Threads
            threads_item = QTableWidgetItem(str(process.num_threads))
            self.process_table.setItem(row, 6, threads_item)

            # User
            user_item = QTableWidgetItem(process.username)
            self.process_table.setItem(row, 7, user_item)

            # Uptime
            from datetime import datetime
            uptime_seconds = datetime.now().timestamp() - process.create_time
            if uptime_seconds < 3600:
                uptime_str = f"{uptime_seconds/60:.0f}m"
            elif uptime_seconds < 86400:
                uptime_str = f"{uptime_seconds/3600:.1f}h"
            else:
                uptime_str = f"{uptime_seconds/86400:.1f}d"

            uptime_item = QTableWidgetItem(uptime_str)
            self.process_table.setItem(row, 8, uptime_item)

    def _update_statistics(self, processes: List[ProcessInfo]):
        """Update process statistics display."""
        total_processes = len(processes)
        total_cpu = sum(p.cpu_percent for p in processes)
        total_memory = sum(p.memory_percent for p in processes)

        stats_text = f"Processes: {total_processes} | Total CPU: {total_cpu:.1f}% | Total Memory: {total_memory:.1f}%"
        self.stats_label.setText(stats_text)

    def _on_selection_changed(self):
        """Handle process selection change."""
        selected_items = self.process_table.selectedItems()
        if not selected_items:
            self._clear_selection()
            return

        # Get the process from the first column (PID)
        row = selected_items[0].row()
        pid_item = self.process_table.item(row, 0)
        process = pid_item.data(Qt.UserRole)

        if process:
            self.selected_processes = [process]
            self._update_process_details(process)
            self._enable_action_buttons(True)
        else:
            self._clear_selection()

    def _clear_selection(self):
        """Clear process selection."""
        self.selected_processes = []
        self.details_text.clear()
        self._enable_action_buttons(False)

    def _update_process_details(self, process: ProcessInfo):
        """Update process details display."""
        details = f"""
<b>Process Details</b><br>
<b>PID:</b> {process.pid}<br>
<b>Parent PID:</b> {process.ppid}<br>
<b>Name:</b> {process.name}<br>
<b>Status:</b> {process.status.value.title()}<br>
<b>CPU Usage:</b> {process.cpu_percent:.1f}%<br>
<b>Memory Usage:</b> {process.memory_percent:.1f}% ({process.memory_rss // (1024*1024)} MB)<br>
<b>Virtual Memory:</b> {process.memory_vms // (1024*1024)} MB<br>
<b>Threads:</b> {process.num_threads}<br>
<b>Handles:</b> {process.num_handles}<br>
<b>User:</b> {process.username}<br>
<b>Priority:</b> {process.priority}<br>
<b>Working Directory:</b> {process.cwd or 'N/A'}<br>
<b>Executable:</b> {process.executable or 'N/A'}<br>
<b>Command Line:</b> {' '.join(process.cmdline) if process.cmdline else 'N/A'}<br>
<b>Connections:</b> {process.connections}<br>
<b>Children:</b> {process.children_count}<br>
        """
        self.details_text.setHtml(details)

    def _enable_action_buttons(self, enabled: bool):
        """Enable or disable action buttons."""
        self.terminate_button.setEnabled(enabled)
        self.kill_button.setEnabled(enabled)
        self.suspend_button.setEnabled(enabled)
        self.resume_button.setEnabled(enabled)
        self.priority_combo.setEnabled(enabled)

    def _show_context_menu(self, position):
        """Show context menu for process table."""
        if not self.selected_processes:
            return

        menu = QMenu(self)

        terminate_action = QAction("🛑 Terminate", self)
        terminate_action.triggered.connect(self._terminate_process)
        menu.addAction(terminate_action)

        kill_action = QAction("⚡ Force Kill", self)
        kill_action.triggered.connect(self._kill_process)
        menu.addAction(kill_action)

        menu.addSeparator()

        suspend_action = QAction("⏸️ Suspend", self)
        suspend_action.triggered.connect(self._suspend_process)
        menu.addAction(suspend_action)

        resume_action = QAction("▶️ Resume", self)
        resume_action.triggered.connect(self._resume_process)
        menu.addAction(resume_action)

        menu.exec(self.process_table.mapToGlobal(position))

    def _terminate_process(self):
        """Terminate selected process."""
        if not self.selected_processes:
            return

        process = self.selected_processes[0]
        reply = QMessageBox.question(
            self,
            "Terminate Process",
            f"Are you sure you want to terminate process '{process.name}' (PID: {process.pid})?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            result = self.process_manager.kill_process(process.pid, force=False)
            self._show_action_result("Terminate", result)
            self._refresh_processes()

    def _kill_process(self):
        """Force kill selected process."""
        if not self.selected_processes:
            return

        process = self.selected_processes[0]
        reply = QMessageBox.question(
            self,
            "Force Kill Process",
            f"Are you sure you want to force kill process '{process.name}' (PID: {process.pid})?\nThis may cause data loss!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            result = self.process_manager.kill_process(process.pid, force=True)
            self._show_action_result("Force Kill", result)
            self._refresh_processes()

    def _suspend_process(self):
        """Suspend selected process."""
        if not self.selected_processes:
            return

        process = self.selected_processes[0]
        result = self.process_manager.suspend_process(process.pid)
        self._show_action_result("Suspend", result)
        self._refresh_processes()

    def _resume_process(self):
        """Resume selected process."""
        if not self.selected_processes:
            return

        process = self.selected_processes[0]
        result = self.process_manager.resume_process(process.pid)
        self._show_action_result("Resume", result)
        self._refresh_processes()

    def _change_priority(self):
        """Change process priority."""
        if not self.selected_processes:
            return

        process = self.selected_processes[0]
        priority = self.priority_combo.currentData()

        if priority:
            result = self.process_manager.set_process_priority(process.pid, priority)
            self._show_action_result("Priority Change", result)
            self._refresh_processes()

    def _show_action_result(self, action: str, result: Dict[str, Any]):
        """Show result of process action."""
        if result.get("success"):
            QMessageBox.information(
                self,
                f"{action} Successful",
                f"{action} completed successfully."
            )
        else:
            QMessageBox.warning(
                self,
                f"{action} Failed",
                f"{action} failed: {result.get('error', 'Unknown error')}"
            )

    def _setup_auto_refresh(self):
        """Setup auto-refresh functionality."""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_processes)
        self.refresh_timer.start(3000)  # Refresh every 3 seconds

    def _toggle_auto_refresh(self, enabled: bool):
        """Toggle auto-refresh on/off."""
        if enabled:
            self.refresh_timer.start(3000)
        else:
            self.refresh_timer.stop()

    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.update_worker:
            self.update_worker.stop()
            self.update_worker.wait()

        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()

        event.accept()