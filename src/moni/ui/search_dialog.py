"""
Moni Search UI Components
Advanced search interface with multilingual support for YouTube, academic papers, and web content.
"""

import logging
from typing import Optional, List, Callable, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QTextEdit,
    QPushButton, QTreeWidget, QTreeWidgetItem, QProgressBar,
    QTabWidget, QWidget, QScrollArea, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QPixmap, QIcon

from .components import AtlassianButton, ButtonAppearance, create_primary_button
from ..internationalization import i18n_manager
from ..search_engine import (
    SearchManager, SearchQuery, SearchType, SearchEngine,
    SearchResult, SearchResponse
)

logger = logging.getLogger(__name__)


class SearchWorker(QThread):
    """Background worker for search operations."""

    # Signals
    search_started = Signal()
    search_finished = Signal(object)  # SearchResponse
    search_error = Signal(str)
    progress_updated = Signal(int, str)

    def __init__(self, search_query: SearchQuery):
        super().__init__()
        self.search_query = search_query
        self.search_manager = SearchManager()

    def run(self):
        """Execute search in background thread."""
        try:
            self.search_started.emit()

            # Import here to avoid circular imports
            import asyncio

            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Perform search
            response = loop.run_until_complete(
                self.search_manager.search(self.search_query)
            )

            self.search_finished.emit(response)

        except Exception as e:
            logger.error(f"Search error: {e}")
            self.search_error.emit(str(e))


class SearchTypeSelector(QWidget):
    """Widget for selecting search type (YouTube, Academic, Web, etc.)."""

    search_type_changed = Signal(SearchType)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_type = SearchType.WEB
        self._setup_ui()

    def _setup_ui(self):
        """Setup search type selector UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Create radio buttons for each search type
        self.type_buttons = {}

        for search_type in SearchType:
            button = AtlassianButton(
                i18n_manager.get_text(f"search.type.{search_type.value}"),
                appearance=ButtonAppearance.DEFAULT
            )
            button.setCheckable(True)
            button.setAutoExclusive(True)

            if search_type == SearchType.WEB:
                button.setChecked(True)

            button.clicked_signal.connect(
                lambda checked, st=search_type: self._on_type_changed(st) if checked else None
            )

            self.type_buttons[search_type] = button
            layout.addWidget(button)

        layout.addStretch()

    def _on_type_changed(self, search_type: SearchType):
        """Handle search type change."""
        self.current_type = search_type
        self.search_type_changed.emit(search_type)

    def get_current_type(self) -> SearchType:
        """Get currently selected search type."""
        return self.current_type

    def set_search_type(self, search_type: SearchType):
        """Set search type programmatically."""
        if search_type in self.type_buttons:
            self.type_buttons[search_type].setChecked(True)
            self.current_type = search_type


class SearchEngineSelector(QWidget):
    """Widget for selecting search engine."""

    engine_changed = Signal(SearchEngine)

    def __init__(self, search_type: SearchType = SearchType.WEB, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_type = search_type
        self.search_manager = SearchManager()
        self._setup_ui()
        self._update_engines()

    def _setup_ui(self):
        """Setup search engine selector UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Label
        self.label = QLabel(i18n_manager.get_text("search.engine.label", "Search Engine:"))
        layout.addWidget(self.label)

        # Combo box for engines
        self.engine_combo = QComboBox(self)
        self.engine_combo.currentTextChanged.connect(self._on_engine_changed)
        layout.addWidget(self.engine_combo)

    def _update_engines(self):
        """Update available engines based on search type."""
        self.engine_combo.clear()

        engines = self.search_manager.get_supported_engines(self.current_type)
        engine_names = self.search_manager.providers[self.current_type].get_translator().get_engine_names()

        for engine in engines:
            display_name = engine_names.get(engine.value, engine.value)
            self.engine_combo.addItem(display_name, engine)

        # Set default engine
        if engines:
            default_engine = engines[0]
            self.set_engine(default_engine)

    def _on_engine_changed(self, text: str):
        """Handle engine selection change."""
        for i in range(self.engine_combo.count()):
            if self.engine_combo.itemText(i) == text:
                engine = self.engine_combo.itemData(i)
                if engine:
                    self.engine_changed.emit(engine)
                break

    def set_search_type(self, search_type: SearchType):
        """Update search type and refresh engines."""
        self.current_type = search_type
        self._update_engines()

    def get_current_engine(self) -> SearchEngine:
        """Get currently selected engine."""
        current_data = self.engine_combo.currentData()
        return current_data if current_data else SearchEngine.GOOGLE

    def set_engine(self, engine: SearchEngine):
        """Set engine programmatically."""
        for i in range(self.engine_combo.count()):
            if self.engine_combo.itemData(i) == engine:
                self.engine_combo.setCurrentIndex(i)
                break


class SearchFiltersWidget(QWidget):
    """Widget for search filters and options."""

    filters_changed = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_filters = {}
        self._setup_ui()

    def _setup_ui(self):
        """Setup filters UI."""
        layout = QFormLayout(self)
        layout.setSpacing(8)

        # Safe search
        self.safe_search_checkbox = QCheckBox(
            i18n_manager.get_text("settings.safe_search")
        )
        self.safe_search_checkbox.setChecked(True)
        self.safe_search_checkbox.stateChanged.connect(self._update_filters)
        layout.addRow("", self.safe_search_checkbox)

        # Max results
        self.max_results_spin = QSpinBox(self)
        self.max_results_spin.setRange(1, 50)
        self.max_results_spin.setValue(10)
        self.max_results_spin.valueChanged.connect(self._update_filters)
        layout.addRow(
            i18n_manager.get_text("settings.max_results") + ":",
            self.max_results_spin
        )

        # Language selector
        self.language_combo = QComboBox(self)
        self._populate_languages()
        self.language_combo.currentTextChanged.connect(self._update_filters)
        layout.addRow(
            i18n_manager.get_text("settings.language") + ":",
            self.language_combo
        )

    def _populate_languages(self):
        """Populate language dropdown."""
        self.language_combo.clear()
        self.language_combo.addItem("Auto", "")

        # Add common languages
        common_languages = [
            ("en", "English"),
            ("ja", "日本語"),
            ("zh-CN", "中文 (简体)"),
            ("es", "Español"),
            ("fr", "Français"),
            ("de", "Deutsch"),
            ("it", "Italiano"),
            ("pt", "Português"),
            ("ru", "Русский"),
            ("ko", "한국어"),
        ]

        for code, name in common_languages:
            self.language_combo.addItem(name, code)

    def _update_filters(self):
        """Update filters and emit signal."""
        self.current_filters = {
            'safe_search': self.safe_search_checkbox.isChecked(),
            'max_results': self.max_results_spin.value(),
            'language': self.language_combo.currentData() or "",
        }
        self.filters_changed.emit(self.current_filters.copy())

    def get_filters(self) -> Dict[str, Any]:
        """Get current filters."""
        return self.current_filters.copy()


class SearchResultWidget(QTreeWidget):
    """Widget for displaying search results."""

    result_selected = Signal(SearchResult)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.results: List[SearchResult] = []
        self._setup_ui()

    def _setup_ui(self):
        """Setup results tree UI."""
        self.setColumnCount(2)
        self.setHeaderLabels([
            i18n_manager.get_text("search.results"),
            i18n_manager.get_text("search.type.source", "Source")
        ])

        # Enable sorting
        self.setSortingEnabled(True)

        # Set column widths
        self.setColumnWidth(0, 400)
        self.setColumnWidth(1, 150)

        # Connect selection
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self):
        """Handle result selection."""
        current_item = self.currentItem()
        if current_item and hasattr(current_item, 'result_data'):
            self.result_selected.emit(current_item.result_data)

    def update_results(self, response: SearchResponse):
        """Update results display."""
        self.clear()
        self.results = response.results

        for result in self.results:
            # Create main item
            title_item = QTreeWidgetItem([
                result.title,
                f"{result.search_type.value.title()} - {result.source.value.title()}"
            ])

            # Store result data
            title_item.result_data = result

            # Add description as child
            if result.description:
                desc_item = QTreeWidgetItem([result.description, ""])
                desc_item.setDisabled(True)
                title_item.addChild(desc_item)

            # Add metadata as children
            if result.author:
                author_item = QTreeWidgetItem([f"Author: {result.author}", ""])
                author_item.setDisabled(True)
                title_item.addChild(author_item)

            if result.published_date:
                date_item = QTreeWidgetItem([
                    f"Published: {result.published_date.strftime('%Y-%m-%d')}",
                    ""
                ])
                date_item.setDisabled(True)
                title_item.addChild(date_item)

            # Add URL as clickable child
            if result.url:
                url_item = QTreeWidgetItem([f"URL: {result.url}", ""])
                url_item.setDisabled(True)
                title_item.addChild(url_item)

            self.addTopLevelItem(title_item)
            title_item.setExpanded(False)

        # Update header
        self.setHeaderLabels([
            i18n_manager.get_text("search.results") + f" ({len(self.results)})",
            i18n_manager.get_text("search.type.source", "Source")
        ])

    def open_selected_result(self):
        """Open selected result in browser."""
        current_item = self.currentItem()
        if current_item and hasattr(current_item, 'result_data'):
            result: SearchResult = current_item.result_data
            if result.url:
                QDesktopServices.openUrl(QUrl(result.url))


class SearchDialog(QDialog):
    """Main search dialog with comprehensive search functionality."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.search_manager = SearchManager()
        self.current_search: Optional[SearchQuery] = None
        self.search_worker: Optional[SearchWorker] = None

        self.setWindowTitle(i18n_manager.get_text("search.title"))
        self.setMinimumSize(800, 600)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup main dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Search input section
        search_section = self._create_search_section()
        layout.addWidget(search_section)

        # Filters section
        filters_section = self._create_filters_section()
        layout.addWidget(filters_section)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        layout.addWidget(self.progress_bar)

        # Results section
        results_section = self._create_results_section()
        layout.addWidget(results_section)

        # Buttons
        buttons_layout = QHBoxLayout()

        self.search_button = create_primary_button(
            i18n_manager.get_text("search.button"),
            parent=self
        )
        self.search_button.clicked_signal.connect(self._start_search)
        buttons_layout.addWidget(self.search_button)

        self.clear_button = AtlassianButton(
            i18n_manager.get_text("ui.button.clear", "Clear"),
            appearance=ButtonAppearance.DEFAULT,
            parent=self
        )
        self.clear_button.clicked_signal.connect(self._clear_results)
        buttons_layout.addWidget(self.clear_button)

        buttons_layout.addStretch()

        self.open_button = AtlassianButton(
            i18n_manager.get_text("ui.button.open", "Open in Browser"),
            appearance=ButtonAppearance.LINK,
            parent=self
        )
        self.open_button.clicked_signal.connect(self._open_selected_result)
        buttons_layout.addWidget(self.open_button)

        layout.addLayout(buttons_layout)

        # Status label
        self.status_label = QLabel("", self)
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

    def _create_search_section(self) -> QWidget:
        """Create search input section."""
        section = QWidget(self)
        section.setObjectName("searchSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(16, 16, 16, 16)

        # Search type selector
        self.search_type_selector = SearchTypeSelector(self)
        layout.addWidget(self.search_type_selector)

        # Search engine selector
        self.engine_selector = SearchEngineSelector(self)
        layout.addWidget(self.engine_selector)

        # Search input
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText(
            i18n_manager.get_text("search.placeholder")
        )
        self.search_input.returnPressed.connect(self._start_search)
        input_layout.addWidget(self.search_input)

        layout.addLayout(input_layout)

        return section

    def _create_filters_section(self) -> QWidget:
        """Create filters section."""
        section = QWidget(self)
        section.setObjectName("filtersSection")

        layout = QVBoxLayout(section)
        layout.setContentsMargins(16, 8, 16, 8)

        self.filters_widget = SearchFiltersWidget(self)
        layout.addWidget(self.filters_widget)

        return section

    def _create_results_section(self) -> QWidget:
        """Create results display section."""
        section = QWidget(self)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(16, 8, 16, 8)

        # Results label
        self.results_label = QLabel(
            i18n_manager.get_text("search.no_results"),
            self
        )
        self.results_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.results_label)

        # Results tree
        self.results_tree = SearchResultWidget(self)
        layout.addWidget(self.results_tree)

        return section

    def _connect_signals(self):
        """Connect UI signals."""
        self.search_type_selector.search_type_changed.connect(
            self.engine_selector.set_search_type
        )
        self.filters_widget.filters_changed.connect(self._update_search_query)
        self.results_tree.result_selected.connect(self._on_result_selected)

    def _update_search_query(self, filters: Dict[str, Any]):
        """Update current search query with new filters."""
        if self.current_search:
            for key, value in filters.items():
                if hasattr(self.current_search, key):
                    setattr(self.current_search, key, value)

    def _start_search(self):
        """Start search operation."""
        query_text = self.search_input.text().strip()
        if not query_text:
            self.status_label.setText(
                i18n_manager.get_text("search.error.empty", "Please enter a search query")
            )
            return

        # Create search query
        search_type = self.search_type_selector.get_current_type()
        engine = self.engine_selector.get_current_engine()
        filters = self.filters_widget.get_filters()

        self.current_search = SearchQuery(
            query=query_text,
            search_type=search_type,
            engine=engine,
            language=filters.get('language', 'en'),
            max_results=filters.get('max_results', 10),
            safe_search=filters.get('safe_search', True)
        )

        # Disable search button during search
        self.search_button.set_loading(True)
        self.search_button.setEnabled(False)

        # Show progress
        self.progress_bar.setVisible(True)
        self.status_label.setText(i18n_manager.get_text("search.loading"))

        # Start background search
        self.search_worker = SearchWorker(self.current_search)
        self.search_worker.search_started.connect(self._on_search_started)
        self.search_worker.search_finished.connect(self._on_search_finished)
        self.search_worker.search_error.connect(self._on_search_error)
        self.search_worker.start()

    def _on_search_started(self):
        """Handle search started."""
        self.status_label.setText(i18n_manager.get_text("search.loading"))

    def _on_search_finished(self, response: SearchResponse):
        """Handle search completed."""
        # Re-enable UI
        self.search_button.set_loading(False)
        self.search_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        # Update results
        if response.results:
            self.results_tree.update_results(response)
            self.results_label.setText(
                i18n_manager.get_text("search.results") + f" ({len(response.results)})"
            )
            self.status_label.setText(
                f"{i18n_manager.get_text('search.completed')} - {response.search_time:.2f}s"
            )
        else:
            self.results_label.setText(i18n_manager.get_text("search.no_results"))
            self.status_label.setText(i18n_manager.get_text("search.no_results"))

    def _on_search_error(self, error: str):
        """Handle search error."""
        # Re-enable UI
        self.search_button.set_loading(False)
        self.search_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        # Show error
        self.status_label.setText(
            i18n_manager.get_text("search.error") + f": {error}"
        )

    def _clear_results(self):
        """Clear search results."""
        self.search_input.clear()
        self.results_tree.clear()
        self.results_label.setText(i18n_manager.get_text("search.no_results"))
        self.status_label.clear()

    def _open_selected_result(self):
        """Open selected result in browser."""
        self.results_tree.open_selected_result()

    def _on_result_selected(self, result: SearchResult):
        """Handle result selection."""
        self.status_label.setText(f"Selected: {result.title}")


def open_search_dialog(parent: Optional[QWidget] = None) -> Optional[SearchResponse]:
    """Open search dialog and return results."""
    dialog = SearchDialog(parent)

    if dialog.exec() == QDialog.Accepted:
        # Return last search results if available
        if hasattr(dialog, 'current_search') and dialog.current_search:
            # This would need to be modified to return actual results
            return None

    return None
