from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QKeySequence, QPalette, QPen, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QSpinBox,
    QStyledItemDelegate,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from copy import deepcopy
import difflib
import os
import webbrowser
from file_initializer import FileInitializer
from image_cache import ImageCache


BOM_ROW_BACKGROUND_ROLE = Qt.ItemDataRole.UserRole + 1
BOM_ROW_FOREGROUND_ROLE = Qt.ItemDataRole.UserRole + 2


def populate_bin_combo(combo_box, backend, selected_location=None):
    selected = str(selected_location or "").strip()
    get_bins = getattr(backend, "get_bin_locations", lambda: [])
    get_group = getattr(backend, "get_auto_bin_group", lambda value: "Other")
    combo_box.blockSignals(True)
    combo_box.clear()
    for location in get_bins():
        label = f"{location} ({get_group(location)})"
        combo_box.addItem(label, location)
    if selected:
        index = combo_box.findData(selected)
        if index >= 0:
            combo_box.setCurrentIndex(index)
    combo_box.blockSignals(False)


def find_component_index(backend, target_component):
    if target_component is None:
        return -1

    for index, component in enumerate(backend.get_all_components()):
        if component is target_component:
            return index

    part_info = target_component.get("part_info", {})
    part_number = str(part_info.get("part_number", "")).strip().lower()
    manufacturer_number = str(part_info.get("manufacturer_number", "")).strip().lower()
    for index, component in enumerate(backend.get_all_components()):
        existing = component.get("part_info", {})
        if (
            str(existing.get("part_number", "")).strip().lower() == part_number
            and str(existing.get("manufacturer_number", "")).strip().lower() == manufacturer_number
        ):
            return index
    return -1


class MainWindow(QMainWindow):
    def __init__(self, backend, digikey_api=None, initializer=None):
        super().__init__()
        self.backend = backend
        self.digikey_api = digikey_api
        self.initializer = initializer or FileInitializer()
        self.test_mode = False
        self.production_data_file = backend.data_file
        self.test_data_file = self._build_test_data_file(self.production_data_file)

        self.setWindowTitle("L.E.A.D. Inventory")
        self.resize(1280, 760)

        shell = QWidget()
        shell.setObjectName("appShell")
        shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        sidebar_panel = QWidget()
        sidebar_panel.setObjectName("sidebarPanel")
        sidebar_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sidebar_panel.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar_panel)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        brand_title = QLabel("L.E.A.D.")
        brand_title.setObjectName("sidebarBrand")
        self.help_button = QPushButton("?")
        self.help_button.setObjectName("helpButton")
        self.help_button.setToolTip("How To")
        self.help_button.setFixedSize(36, 36)
        self.help_button.clicked.connect(self.open_help_dialog)
        self.settings_button = QPushButton()
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.setToolTip("Settings")
        self.settings_button.setFixedSize(36, 36)
        self.settings_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.settings_button.clicked.connect(self.open_settings_dialog)

        header_row.addWidget(brand_title)
        header_row.addStretch(1)
        header_row.addWidget(self.help_button)
        header_row.addWidget(self.settings_button)

        brand_subtitle = QLabel("Inventory Control")
        brand_subtitle.setObjectName("sidebarSubtitle")
        self.test_mode_badge = QLabel("TEST MODE")
        self.test_mode_badge.setObjectName("testModeBadge")
        self.test_mode_badge.hide()
        nav_label = QLabel("Navigation")
        nav_label.setObjectName("sidebarSection")
        divider = QFrame()
        divider.setObjectName("sidebarDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)

        self.nav = QListWidget()
        self.nav.setObjectName("sidebar")
        self.nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for label in ("Home", "Inventory", "Add Part"):
            self.nav.addItem(QListWidgetItem(label))

        footer_hint = QLabel("Double-click a part in any table to open details.")
        footer_hint.setObjectName("sidebarFooter")
        footer_hint.setWordWrap(True)

        sidebar_layout.addLayout(header_row)
        sidebar_layout.addWidget(brand_subtitle)
        sidebar_layout.addWidget(self.test_mode_badge, 0, Qt.AlignmentFlag.AlignLeft)
        sidebar_layout.addSpacing(8)
        sidebar_layout.addWidget(nav_label)
        sidebar_layout.addWidget(divider)
        sidebar_layout.addWidget(self.nav, 1)
        sidebar_layout.addWidget(footer_hint)

        self.pages = QStackedWidget()
        self.pages.setObjectName("pageStack")
        self.pages.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.home_page = HomePage(self.backend)
        self.inventory_page = InventoryPage(self.backend)
        self.add_page = AddPartPage(self.backend, self.digikey_api)
        self.add_page.part_added.connect(self.refresh_all_pages)
        self.home_page.bom_processed.connect(self.refresh_all_pages)
        self.inventory_page.component_deleted.connect(self.refresh_all_pages)
        self.inventory_page.undo_requested.connect(self.undo_last_deletion)
        self.add_page.component_deleted.connect(self.refresh_all_pages)
        self.add_page.undo_requested.connect(self.undo_last_deletion)

        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.inventory_page)
        self.pages.addWidget(self.add_page)

        shell_layout.addWidget(sidebar_panel)
        shell_layout.addWidget(self.pages, 1)

        self.setCentralWidget(shell)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.currentRowChanged.connect(self.refresh_current_page)
        for table in (self.home_page.table, self.inventory_page.table, self.add_page.recent_table):
            table.itemDoubleClicked.connect(self.show_component_details)
        self.nav.setCurrentRow(0)
        self.test_mode_shortcut = QShortcut(QKeySequence("Ctrl+Alt+T"), self)
        self.test_mode_shortcut.activated.connect(self.toggle_test_mode)

        self.setStyleSheet(
            """
            QMainWindow {
                background: #f6f7f9;
            }
            QWidget#appShell, QStackedWidget#pageStack, QWidget#pageRoot, QWidget#pageContent, QWidget#pageViewport {
                background: #f6f7f9;
                color: #20242b;
            }
            QWidget#sidebarPanel {
                background: #182028;
                color: #f2f4f7;
                border-right: 1px solid #2c3945;
            }
            QLabel#sidebarBrand {
                color: #ffffff;
                font-size: 24px;
                font-weight: 800;
            }
            QPushButton#settingsButton, QPushButton#helpButton {
                background: #25333f;
                color: #ffffff;
                border: 1px solid #314250;
                border-radius: 6px;
                padding: 0;
                font-size: 18px;
                font-weight: 700;
            }
            QPushButton#settingsButton:hover, QPushButton#helpButton:hover {
                background: #2d3d4b;
                color: #ffffff;
            }
            QLabel#sidebarSubtitle {
                color: #9db1c2;
                font-size: 12px;
            }
            QLabel#testModeBadge {
                background: #7b1f1f;
                color: #ffffff;
                border: 1px solid #b94b4b;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#sidebarSection {
                color: #d7e2ea;
                font-size: 12px;
                font-weight: 700;
            }
            QFrame#sidebarDivider {
                background: #2c3945;
                max-height: 1px;
                border: none;
            }
            QListWidget#sidebar {
                background: transparent;
                color: #f2f4f7;
                border: none;
                padding: 4px 0;
                font-size: 14px;
                outline: none;
            }
            QListWidget#sidebar::item {
                padding: 12px 14px;
                border-left: 4px solid transparent;
                border-radius: 6px;
                color: #f2f4f7;
                margin: 2px 0;
            }
            QListWidget#sidebar::item:hover {
                background: #212c36;
                color: #ffffff;
            }
            QListWidget#sidebar::item:selected {
                background: #25333f;
                border-left-color: #4f9d8c;
                color: #ffffff;
            }
            QLabel#sidebarFooter {
                color: #98adbd;
                font-size: 12px;
                line-height: 1.4;
            }
            QLabel#pageTitle {
                font-size: 22px;
                font-weight: 700;
                color: #20242b;
            }
            QLabel#metricValue {
                font-size: 26px;
                font-weight: 700;
                color: #20242b;
            }
            QLabel#metricLabel {
                color: #59616d;
            }
            QFrame#metricCard {
                background: white;
                border: 1px solid #d9dde3;
                border-radius: 6px;
            }
            QFrame#ledStatusPanel {
                background: white;
                border: 1px solid #d9dde3;
                border-radius: 6px;
            }
            QLabel#ledStatusTitle {
                color: #20242b;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#ledStatusBadge {
                border-radius: 10px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#ledStatusBadge[statusState="connected"] {
                background: #d1e7dd;
                color: #0f5132;
                border: 1px solid #badbcc;
            }
            QLabel#ledStatusBadge[statusState="disconnected"] {
                background: #f8d7da;
                color: #842029;
                border: 1px solid #f1aeb5;
            }
            QLabel#ledStatusBadge[statusState="unavailable"] {
                background: #fff3cd;
                color: #664d03;
                border: 1px solid #ffecb5;
            }
            QLabel#ledStatusDetail {
                color: #5d6a75;
                font-size: 12px;
            }
            QDialog#detailsDialog {
                background: #f6f7f9;
                color: #20242b;
            }
            QDialog#barcodeDialog {
                background: #f6f7f9;
                color: #20242b;
            }
            QDialog#bulkBarcodeDialog {
                background: #f6f7f9;
                color: #20242b;
            }
            QDialog#settingsDialog {
                background: #f6f7f9;
                color: #20242b;
            }
            QDialog#helpDialog {
                background: #f6f7f9;
                color: #20242b;
            }
            QDialog#actionDialog {
                background: #f6f7f9;
                color: #20242b;
            }
            QDialog#bomDialog, QDialog#bomResultsDialog {
                background: #f6f7f9;
                color: #20242b;
            }
            QMessageBox {
                background: #f6f7f9;
                color: #20242b;
            }
            QMessageBox QWidget {
                background: #f6f7f9;
                color: #20242b;
            }
            QMessageBox QLabel {
                background: transparent;
                color: #20242b;
            }
            QMessageBox QPushButton {
                background: #326b60;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 14px;
                min-width: 88px;
                font-weight: 600;
            }
            QMessageBox QPushButton:hover {
                background: #3a7a6d;
                color: white;
            }
            QFrame#barcodePanel {
                background: white;
                border: 1px solid #d9dde3;
                border-radius: 6px;
            }
            QFrame#bulkBarcodePanel {
                background: white;
                border: 1px solid #d9dde3;
                border-radius: 6px;
            }
            QFrame#settingsPanel {
                background: white;
                border: 1px solid #d9dde3;
                border-radius: 6px;
            }
            QFrame#helpPanel {
                background: white;
                border: 1px solid #d9dde3;
                border-radius: 6px;
            }
            QFrame#actionPanel {
                background: white;
                border: 1px solid #d9dde3;
                border-radius: 6px;
            }
            QFrame#bomPanel, QFrame#bomResultsPanel {
                background: white;
                border: 1px solid #d9dde3;
                border-radius: 6px;
            }
            QLabel#barcodeHint {
                color: #5d6a75;
                font-size: 12px;
            }
            QFrame#detailsHero, QFrame#detailsStatCard {
                background: white;
                border: 1px solid #d9dde3;
                border-radius: 6px;
            }
            QLabel#detailsEyebrow {
                color: #5d6a75;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#detailsHeadline {
                color: #182028;
                font-size: 24px;
                font-weight: 800;
            }
            QLabel#detailsSubline {
                color: #5d6a75;
                font-size: 13px;
            }
            QLabel#detailsStatLabel {
                color: #5d6a75;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#detailsStatValue {
                color: #182028;
                font-size: 20px;
                font-weight: 800;
            }
            QLabel#detailsFieldLabel {
                color: #4d5963;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#detailsFieldValue {
                color: #20242b;
                font-size: 13px;
            }
            QLineEdit[detailsReadonly="true"], QTextEdit[detailsReadonly="true"] {
                background: #f7f8fa;
                color: #20242b;
                border: 1px solid #e1e5ea;
            }
            QLineEdit[detailsReadonly="false"], QTextEdit[detailsReadonly="false"] {
                background: white;
                color: #20242b;
                border: 1px solid #8da7a1;
            }
            QScrollArea {
                background: #f6f7f9;
                border: none;
            }
            QWidget {
                color: #20242b;
            }
            QGroupBox {
                background: white;
                border: 1px solid #d9dde3;
                border-radius: 6px;
                color: #20242b;
                font-weight: 600;
                margin-top: 12px;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
            }
            QLabel {
                color: #20242b;
            }
            QTableWidget, QTableView {
                background: white;
                color: #20242b;
                border: 1px solid #d9dde3;
                gridline-color: #edf0f3;
                alternate-background-color: #f5f7f8;
                selection-background-color: #d8eee8;
                selection-color: #20242b;
            }
            QTableWidget::item, QTableView::item {
                background: white;
                color: #20242b;
            }
            QTableWidget::item:alternate, QTableView::item:alternate {
                background: #f5f7f8;
                color: #20242b;
            }
            QTableWidget::item:selected, QTableView::item:selected {
                background: #d8eee8;
                color: #20242b;
            }
            QHeaderView::section {
                background: #eef1f4;
                color: #303640;
                border: none;
                border-right: 1px solid #d9dde3;
                padding: 7px;
                font-weight: 600;
            }
            QTableCornerButton::section {
                background: #eef1f4;
                border: none;
                border-right: 1px solid #d9dde3;
                border-bottom: 1px solid #d9dde3;
            }
            QLineEdit {
                background: white;
                color: #20242b;
                border: 1px solid #c8ced6;
                border-radius: 4px;
                padding: 8px;
                selection-background-color: #d8eee8;
                selection-color: #20242b;
            }
            QComboBox {
                background: white;
                color: #20242b;
                border: 1px solid #c8ced6;
                border-radius: 4px;
                padding: 7px;
            }
            QComboBox QAbstractItemView {
                background: white;
                color: #20242b;
                selection-background-color: #d8eee8;
                selection-color: #20242b;
            }
            QTextEdit {
                background: white;
                color: #20242b;
                border: 1px solid #c8ced6;
                border-radius: 4px;
                padding: 8px;
                selection-background-color: #d8eee8;
                selection-color: #20242b;
            }
            QPushButton {
                background: #326b60;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:checked {
                background: #214b43;
                color: white;
            }
            QPushButton:disabled {
                background: #aab2bd;
                color: #20242b;
            }
            """
        )

    def refresh_current_page(self, index):
        page = self.pages.widget(index)
        refresh = getattr(page, "refresh", None)
        if refresh:
            refresh()

    def refresh_all_pages(self):
        for page in (self.home_page, self.inventory_page, self.add_page):
            refresh = getattr(page, "refresh", None)
            if refresh:
                refresh()

    def show_component_details(self, item):
        table = item.tableWidget()
        component = table.component_for_row(item.row()) if table else None
        if not component:
            return

        dialog = ComponentDetailsDialog(component, self.backend, self)
        dialog.saved.connect(self.refresh_all_pages)
        dialog.exec()

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.initializer, self.backend, self.digikey_api, self)
        dialog.config_saved.connect(self.handle_config_saved)
        dialog.availability_changed.connect(self.refresh_all_pages)
        dialog.finished.connect(lambda _result: self.refresh_all_pages())
        dialog.exec()

    def open_help_dialog(self):
        HelpDialog(self).exec()

    def undo_last_deletion(self):
        if self.backend.undo_delete():
            self.refresh_all_pages()
            QMessageBox.information(self, "Undo Delete", "Last deletion undone.")
        else:
            QMessageBox.information(self, "Undo Delete", "No deletion to undo.")

    def handle_config_saved(self):
        config = self.initializer.load_config()
        files_config = config.get("FILES", {})
        self.production_data_file = self.initializer.resolve_file_path(
            files_config.get("COMPONENT_CATALOGUE", ""),
            "COMPONENT_CATALOGUE",
        )
        self.test_data_file = self._build_test_data_file(self.production_data_file)
        if self.test_mode:
            self.initializer.ensure_catalogue_at_path(self.test_data_file)
            self.backend.data_file = self.test_data_file
            self.backend.load_components()
        else:
            self.backend.data_file = self.production_data_file
            self.backend.load_components()
        self.backend.undo_stack.clear()
        self.refresh_all_pages()
        self._update_test_mode_ui()

    def toggle_test_mode(self):
        self.test_mode = not self.test_mode

        if self.test_mode:
            self.initializer.ensure_catalogue_at_path(self.test_data_file)
            self.backend.data_file = self.test_data_file
            message = f"Test Mode enabled.\nCatalogue: {self.test_data_file}"
        else:
            self.backend.data_file = self.production_data_file
            message = f"Test Mode disabled.\nCatalogue: {self.production_data_file}"

        self.backend.load_components()
        self.backend.undo_stack.clear()
        self.refresh_all_pages()
        self._update_test_mode_ui()
        QMessageBox.information(self, "Test Mode", message)

    def _update_test_mode_ui(self):
        self.test_mode_badge.setVisible(self.test_mode)
        title_suffix = " [TEST MODE]" if self.test_mode else ""
        self.setWindowTitle(f"L.E.A.D. Inventory{title_suffix}")

    def _build_test_data_file(self, production_data_file):
        current_dir = os.path.dirname(production_data_file)
        return os.path.join(current_dir, "test_catalogue.json")


class HomePage(QWidget):
    bom_processed = pyqtSignal()

    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.setObjectName("pageRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title = QLabel("Home")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.total_parts = MetricCard("Total Parts", "0")
        self.low_stock = MetricCard("Low Stock Items", "0")
        self.type_count = MetricCard("Part Types", "0")
        metrics.addWidget(self.total_parts)
        metrics.addWidget(self.low_stock)
        metrics.addWidget(self.type_count)
        metrics.addStretch(1)
        layout.addLayout(metrics)

        self.led_status_panel = QFrame()
        self.led_status_panel.setObjectName("ledStatusPanel")
        led_layout = QHBoxLayout(self.led_status_panel)
        led_layout.setContentsMargins(16, 14, 16, 14)
        led_layout.setSpacing(12)

        led_copy = QVBoxLayout()
        led_copy.setSpacing(6)
        led_header = QHBoxLayout()
        led_header.setSpacing(10)

        led_title = QLabel("LED System")
        led_title.setObjectName("ledStatusTitle")
        self.led_status_badge = QLabel("Unknown")
        self.led_status_badge.setObjectName("ledStatusBadge")

        led_header.addWidget(led_title)
        led_header.addWidget(self.led_status_badge)
        led_header.addStretch(1)

        self.led_status_detail = QLabel("")
        self.led_status_detail.setObjectName("ledStatusDetail")
        self.led_status_detail.setWordWrap(True)

        led_copy.addLayout(led_header)
        led_copy.addWidget(self.led_status_detail)

        led_layout.addLayout(led_copy, 1)
        self.led_reconnect_button = QPushButton("Reconnect LED")
        self.led_reconnect_button.clicked.connect(self.reconnect_led_controller)
        led_layout.addWidget(self.led_reconnect_button, 0, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.led_status_panel)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.checkout_bom_button = QPushButton("Checkout BOM")
        self.checkin_bom_button = QPushButton("Check In BOM")
        actions.addWidget(self.checkout_bom_button)
        actions.addWidget(self.checkin_bom_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        section_label = QLabel("Low Stock")
        section_label.setObjectName("pageTitle")
        layout.addWidget(section_label)

        low_stock_actions = QHBoxLayout()
        low_stock_actions.setSpacing(10)
        self.export_low_stock_button = QPushButton("Export Low Stock")
        low_stock_actions.addWidget(self.export_low_stock_button)
        low_stock_actions.addStretch(1)
        layout.addLayout(low_stock_actions)

        self.table = ComponentTable()
        layout.addWidget(self.table, 1)

        self.checkout_bom_button.clicked.connect(lambda: self.process_bom_file("out"))
        self.checkin_bom_button.clicked.connect(lambda: self.process_bom_file("in"))
        self.export_low_stock_button.clicked.connect(self.export_low_stock_data)
        self.refresh()

    def refresh(self):
        stats = self.backend.get_statistics()
        low_stock_components = self.backend.get_low_stock_components()

        self.total_parts.set_value(str(stats["total_parts"]))
        self.low_stock.set_value(str(len(low_stock_components)))
        self.type_count.set_value(str(len(stats["types"])))
        self.refresh_led_status()
        self.table.set_components(low_stock_components)

    def refresh_led_status(self):
        led_controller = getattr(self.backend, "ledControl", None)
        if led_controller is not None and hasattr(led_controller, "get_status"):
            status = led_controller.get_status()
        else:
            status = {
                "connected": False,
                "label": "Unavailable",
                "details": "LED controller status is unavailable.",
            }

        label = str(status.get("label", "Unavailable"))
        state = "connected" if status.get("connected") else label.strip().lower()
        if state not in {"connected", "disconnected", "unavailable"}:
            state = "disconnected"

        self.led_status_badge.setText(label)
        self.led_status_badge.setProperty("statusState", state)
        self.led_status_badge.style().unpolish(self.led_status_badge)
        self.led_status_badge.style().polish(self.led_status_badge)
        self.led_status_badge.update()

        self.led_status_detail.setText(str(status.get("details", "")))
        self.led_reconnect_button.setVisible(hasattr(led_controller, "reconnect"))

    def reconnect_led_controller(self):
        led_controller = getattr(self.backend, "ledControl", None)
        if led_controller is None or not hasattr(led_controller, "reconnect"):
            QMessageBox.information(self, "LED Status", "LED reconnection is not available in this session.")
            self.refresh_led_status()
            return

        led_controller.reconnect()
        self.refresh_led_status()
        status = led_controller.get_status() if hasattr(led_controller, "get_status") else {}
        if status.get("connected"):
            QMessageBox.information(self, "LED Status", status.get("details", "LED controller connected."))
        else:
            QMessageBox.warning(self, "LED Status", status.get("details", "LED controller is still disconnected."))

    def process_bom_file(self, mode):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select BOM File",
            "",
            "CSV Files (*.csv);;All Files (*.*)",
        )
        if not file_path:
            return

        try:
            bom_list = self.backend.parse_bom(file_path)
        except Exception as exc:
            QMessageBox.critical(self, "Error Reading BOM", str(exc))
            return

        board_name = file_path.split("/")[-1].split("\\")[-1]
        if mode == "out":
            dialog = BomCheckoutPreviewDialog(self.backend, bom_list, board_name, self)
        else:
            dialog = BomCheckinPreviewDialog(self.backend, bom_list, self)

        dialog.processed.connect(self.bom_processed.emit)
        dialog.exec()

    def export_low_stock_data(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Low Stock Data",
            "",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not file_path:
            return

        low_stock_components = self.backend.get_low_stock_components()
        lines = []
        for component in low_stock_components:
            part_info = component.get("part_info", {})
            metadata = component.get("metadata", {})
            part_number = part_info.get("part_number", "N/A")
            count = part_info.get("count", "N/A")
            low_stock_value = metadata.get("low_stock", "N/A")
            product_url = metadata.get("product_url", "N/A")
            lines.append(
                f"Part Number: {part_number} | Count: {count} | Low Stock: {low_stock_value} | URL: {product_url}"
            )

        try:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write("\n".join(lines))
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"Failed to export file:\n{exc}")
            return

        QMessageBox.information(self, "Export Successful", f"Low stock data exported to:\n{file_path}")


class InventoryPage(QWidget):
    component_deleted = pyqtSignal()
    undo_requested = pyqtSignal()

    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.setObjectName("pageRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        title = QLabel("Inventory")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        controls = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search part number, manufacturer number, location, type, or metadata")
        self.refresh_button = QPushButton("Refresh")
        self.delete_button = QPushButton("Delete Selected")
        self.undo_button = QPushButton("Undo Delete")
        controls.addWidget(self.search_input, 1)
        controls.addWidget(self.refresh_button)
        controls.addWidget(self.delete_button)
        controls.addWidget(self.undo_button)
        layout.addLayout(controls)

        self.table = ComponentTable()
        layout.addWidget(self.table, 1)

        self.search_input.textChanged.connect(self.refresh)
        self.search_input.returnPressed.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)
        self.delete_button.clicked.connect(self.delete_selected_component)
        self.undo_button.clicked.connect(self.undo_requested.emit)
        self.table.deleteRequested.connect(self.delete_selected_component)
        self.refresh()

    def refresh(self):
        query = self.search_input.text().strip()
        if query:
            components = self.backend.search_components(query)
        else:
            components = self.backend.get_all_components()
        self.table.set_components(components)

    def delete_selected_component(self):
        component = self.table.selected_component()
        if component is None:
            QMessageBox.warning(self, "Delete Component", "Select a component to delete.")
            return

        part_info = component.get("part_info", {})
        label = part_info.get("part_number") or part_info.get("manufacturer_number") or "this component"
        response = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {label} from the catalogue?",
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        component_index = find_component_index(self.backend, component)
        if component_index < 0:
            QMessageBox.warning(self, "Delete Component", "Could not locate this component in the catalogue.")
            return

        self.backend.delete_component(component_index)
        self.component_deleted.emit()


class AddPartPage(QWidget):
    part_added = pyqtSignal()
    component_deleted = pyqtSignal()
    undo_requested = pyqtSignal()

    COMPONENT_TYPES = (
        "Cable",
        "Capacitor",
        "Connector",
        "Crystal",
        "Diode",
        "Evaluation",
        "Hardware",
        "IC",
        "Inductor",
        "Kit",
        "LED",
        "Module",
        "Other",
        "Relay",
        "Resistor",
        "Sensor",
        "Switch",
        "Transformer",
        "Transistor",
    )
    STORAGE_MODE_AUTO = "auto_vial"
    STORAGE_MODE_AUTO_BIN = "auto_bin"
    STORAGE_MODE_BIN = "shared_bin"
    STORAGE_MODE_MANUAL = "manual_location"

    def __init__(self, backend, digikey_api=None):
        super().__init__()
        self.backend = backend
        self.digikey_api = digikey_api
        self.lookup_thread = None
        self.lookup_worker = None
        self.lookup_context = None
        self.loaded_digikey_component = None
        self.setObjectName("pageRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.viewport().setObjectName("pageViewport")
        scroll_area.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("pageContent")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        scroll_area.setWidget(content)
        page_layout.addWidget(scroll_area)

        title = QLabel("Add Part")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        lookup_group = QGroupBox("DigiKey Lookup")
        lookup_layout = QHBoxLayout(lookup_group)
        self.lookup_input = QLineEdit()
        self.lookup_input.setPlaceholderText("DigiKey or manufacturer part number")
        self.lookup_button = QPushButton("Lookup")
        self.barcode_button = QPushButton("Scan Barcode")
        self.bulk_barcode_button = QPushButton("Bulk Scan")
        lookup_layout.addWidget(self.lookup_input, 1)
        lookup_layout.addWidget(self.lookup_button)
        lookup_layout.addWidget(self.barcode_button)
        lookup_layout.addWidget(self.bulk_barcode_button)
        layout.addWidget(lookup_group)

        form_group = QGroupBox("Part Details")
        form_layout = QGridLayout(form_group)
        form_layout.setColumnStretch(1, 1)
        form_layout.setColumnStretch(3, 1)

        self.part_number_input = QLineEdit()
        self.manufacturer_number_input = QLineEdit()
        self.location_input = QLineEdit()
        self.auto_location_input = QLineEdit()
        self.auto_location_input.setReadOnly(True)
        self.auto_location_input.setText("Next available vial will be assigned automatically")
        self.auto_bin_input = QLineEdit()
        self.auto_bin_input.setReadOnly(True)
        self.bin_input = QComboBox()
        self.location_stack = QStackedWidget()
        self.location_stack.addWidget(self.auto_location_input)
        self.location_stack.addWidget(self.auto_bin_input)
        self.location_stack.addWidget(self.bin_input)
        self.location_stack.addWidget(self.location_input)
        self.storage_type_input = QComboBox()
        self.storage_type_input.addItem("Auto Vial", self.STORAGE_MODE_AUTO)
        self.storage_type_input.addItem("Auto Bin", self.STORAGE_MODE_AUTO_BIN)
        self.storage_type_input.addItem("Shared Bin", self.STORAGE_MODE_BIN)
        self.storage_type_input.addItem("Manual Location", self.STORAGE_MODE_MANUAL)
        self.count_input = QLineEdit()
        self.low_stock_input = QLineEdit()
        self.price_input = QLineEdit()
        self.type_input = QComboBox()
        self.type_input.addItems(self.COMPONENT_TYPES)
        self.type_input.setEditable(True)

        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(84)
        self.photo_url_input = QLineEdit()
        self.datasheet_url_input = QLineEdit()
        self.product_url_input = QLineEdit()

        self._add_row(form_layout, 0, "Part Number", self.part_number_input, "Manufacturer Number", self.manufacturer_number_input)
        self._add_row(form_layout, 1, "Storage", self.storage_type_input, "Count", self.count_input)
        self._add_row(form_layout, 2, "Location", self.location_stack, "Low Stock", self.low_stock_input)
        self._add_row(form_layout, 3, "Type", self.type_input, "Price", self.price_input)

        form_layout.addWidget(QLabel("Description"), 4, 0, alignment=Qt.AlignmentFlag.AlignTop)
        form_layout.addWidget(self.description_input, 4, 1, 1, 3)
        form_layout.addWidget(QLabel("Photo URL"), 5, 0)
        form_layout.addWidget(self.photo_url_input, 5, 1, 1, 3)
        form_layout.addWidget(QLabel("Datasheet URL"), 6, 0)
        form_layout.addWidget(self.datasheet_url_input, 6, 1, 1, 3)
        form_layout.addWidget(QLabel("Product URL"), 7, 0)
        form_layout.addWidget(self.product_url_input, 7, 1, 1, 3)

        layout.addWidget(form_group)

        actions = QHBoxLayout()
        self.save_button = QPushButton("Save Part")
        self.clear_button = QPushButton("Clear")
        self.delete_button = QPushButton("Delete Selected")
        self.undo_button = QPushButton("Undo Delete")
        actions.addWidget(self.save_button)
        actions.addWidget(self.clear_button)
        actions.addWidget(self.delete_button)
        actions.addWidget(self.undo_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        recent_label = QLabel("Recently Added")
        recent_label.setObjectName("pageTitle")
        layout.addWidget(recent_label)

        self.recent_table = ComponentTable()
        self.recent_table.setMinimumHeight(360)
        layout.addWidget(self.recent_table, 2)

        self.lookup_button.clicked.connect(self.lookup_part)
        self.lookup_input.returnPressed.connect(self.lookup_part)
        self.barcode_button.clicked.connect(self.open_barcode_dialog)
        self.bulk_barcode_button.clicked.connect(self.open_bulk_barcode_dialog)
        self.storage_type_input.currentIndexChanged.connect(self.update_storage_mode)
        self.type_input.currentTextChanged.connect(self.update_auto_bin_preview)
        self.save_button.clicked.connect(self.save_part)
        self.clear_button.clicked.connect(self.clear_form)
        self.delete_button.clicked.connect(self.delete_selected_component)
        self.undo_button.clicked.connect(self.undo_requested.emit)
        self.recent_table.deleteRequested.connect(self.delete_selected_component)

        self.refresh_bin_locations()
        self.update_auto_bin_preview()
        self.update_storage_mode()
        self.refresh()

    def _add_row(self, layout, row, left_label, left_widget, right_label, right_widget):
        layout.addWidget(QLabel(left_label), row, 0)
        layout.addWidget(left_widget, row, 1)
        if right_label and right_widget:
            layout.addWidget(QLabel(right_label), row, 2)
            layout.addWidget(right_widget, row, 3)

    def lookup_part(self):
        if not self.digikey_api:
            QMessageBox.warning(self, "DigiKey Unavailable", "No DigiKey client is configured for this window.")
            return

        part_number = self.lookup_input.text().strip()
        if not part_number:
            QMessageBox.warning(self, "Missing Part Number", "Enter a part number to look up.")
            return

        self.start_lookup(part_number, {"mode": "lookup"})

    def start_lookup(self, part_number, context):
        self.set_lookup_busy(True)
        self.lookup_context = context
        self.lookup_thread = QThread(self)
        self.lookup_worker = DigikeyLookupWorker(self.digikey_api, part_number)
        self.lookup_worker.moveToThread(self.lookup_thread)
        self.lookup_thread.started.connect(self.lookup_worker.run)
        self.lookup_worker.finished.connect(self.handle_lookup_finished)
        self.lookup_worker.finished.connect(self.lookup_thread.quit)
        self.lookup_worker.finished.connect(self.lookup_worker.deleteLater)
        self.lookup_thread.finished.connect(self.lookup_thread.deleteLater)
        self.lookup_thread.finished.connect(self.clear_lookup_thread)
        self.lookup_thread.start()

    def handle_lookup_finished(self, component, error):
        self.set_lookup_busy(False)
        context = self.lookup_context or {}
        if error:
            QMessageBox.critical(self, "DigiKey Lookup Failed", error)
            return
        if not component:
            if context.get("mode") == "barcode":
                self._populate_manual_barcode_data(
                    context.get("barcode_data", {}),
                    context.get("low_stock"),
                    context.get("storage_mode"),
                    context.get("storage_location"),
                )
                QMessageBox.information(self, "No Match", "No DigiKey match was found. The Add Part form was populated for manual review.")
            else:
                QMessageBox.information(self, "No Match", "DigiKey did not return a matching part.")
            return

        if context.get("mode") == "barcode":
            barcode_data = context.get("barcode_data", {})
            component["part_info"]["count"] = int(barcode_data.get("count", 0))
            component["metadata"]["low_stock"] = context.get("low_stock", "N/A")
            component["part_info"]["location"] = self.resolve_storage_location(
                context.get("storage_mode"),
                bin_location=context.get("storage_location", ""),
                manual_location=context.get("storage_location", ""),
                component_type=component.get("part_info", {}).get("type", ""),
            )
            try:
                self.backend.add_component(component)
            except Exception as exc:
                QMessageBox.critical(self, "Barcode Add Failed", str(exc))
                return

            QMessageBox.information(self, "Barcode Added", "The scanned part was added to the catalogue.")
            self.clear_form()
            self.refresh()
            self.part_added.emit()
            return

        self.loaded_digikey_component = component
        self.populate_form(component)

    def clear_lookup_thread(self):
        self.lookup_thread = None
        self.lookup_worker = None
        self.lookup_context = None

    def set_lookup_busy(self, busy):
        self.lookup_button.setDisabled(busy)
        self.barcode_button.setDisabled(busy)
        self.bulk_barcode_button.setDisabled(busy)
        self.lookup_input.setDisabled(busy)
        self.lookup_button.setText("Looking Up..." if busy else "Lookup")

    def refresh_bin_locations(self, selected_location=None):
        selected = str(selected_location or self.bin_input.currentData() or "").strip()
        populate_bin_combo(self.bin_input, self.backend, selected)

    def update_auto_bin_preview(self):
        component_type = self.type_input.currentText().strip() or "Other"
        auto_bin = getattr(self.backend, "get_auto_bin_for_type", lambda value: "Bin 10")(component_type)
        group = getattr(self.backend, "get_auto_bin_group", lambda value: "Other")(auto_bin)
        self.auto_bin_input.setText(f"{auto_bin} ({group})")

    def update_storage_mode(self):
        mode = self.storage_type_input.currentData()
        if mode == self.STORAGE_MODE_AUTO_BIN:
            self.update_auto_bin_preview()
            self.location_stack.setCurrentWidget(self.auto_bin_input)
        elif mode == self.STORAGE_MODE_BIN:
            self.refresh_bin_locations()
            self.location_stack.setCurrentWidget(self.bin_input)
        elif mode == self.STORAGE_MODE_MANUAL:
            self.location_stack.setCurrentWidget(self.location_input)
        else:
            self.location_stack.setCurrentWidget(self.auto_location_input)

    def set_storage_from_location(self, location, storage_mode=None):
        if storage_mode == self.STORAGE_MODE_AUTO_BIN:
            self.storage_type_input.setCurrentIndex(self.storage_type_input.findData(self.STORAGE_MODE_AUTO_BIN))
            self.update_auto_bin_preview()
            self.update_storage_mode()
            return

        normalized = str(location or "").strip()
        if not normalized or normalized.upper() == "N/A":
            self.storage_type_input.setCurrentIndex(self.storage_type_input.findData(self.STORAGE_MODE_AUTO))
            self.location_input.clear()
            self.refresh_bin_locations()
            self.update_storage_mode()
            return

        if normalized.lower().startswith("bin "):
            self.storage_type_input.setCurrentIndex(self.storage_type_input.findData(self.STORAGE_MODE_BIN))
            self.refresh_bin_locations(normalized.title())
            self.update_storage_mode()
            return

        self.storage_type_input.setCurrentIndex(self.storage_type_input.findData(self.STORAGE_MODE_MANUAL))
        self.location_input.setText(normalized)
        self.update_storage_mode()

    def populate_form(self, component):
        part_info = component.get("part_info", {})
        metadata = component.get("metadata", {})

        self.part_number_input.setText(str(part_info.get("part_number", "")))
        self.manufacturer_number_input.setText(str(part_info.get("manufacturer_number", "")))
        self.type_input.setCurrentText(str(part_info.get("type", "Other") or "Other"))
        self.set_storage_from_location(part_info.get("location", "N/A"))
        self.count_input.setText(str(part_info.get("count", "")) if part_info.get("count") != "N/A" else "")
        self.low_stock_input.setText("" if metadata.get("low_stock") == "N/A" else str(metadata.get("low_stock", "")))
        self.price_input.setText("" if metadata.get("price") == "N/A" else str(metadata.get("price", "")))
        self.description_input.setPlainText("" if metadata.get("description") == "N/A" else str(metadata.get("description", "")))
        self.photo_url_input.setText("" if metadata.get("photo_url") == "N/A" else str(metadata.get("photo_url", "")))
        self.datasheet_url_input.setText("" if metadata.get("datasheet_url") == "N/A" else str(metadata.get("datasheet_url", "")))
        self.product_url_input.setText("" if metadata.get("product_url") == "N/A" else str(metadata.get("product_url", "")))

    def save_part(self):
        part_number = self.part_number_input.text().strip()
        manufacturer_number = self.manufacturer_number_input.text().strip()
        component_type = self.type_input.currentText().strip() or "Other"
        storage_mode = self.storage_type_input.currentData()

        if not part_number and not manufacturer_number:
            QMessageBox.warning(self, "Missing Identifier", "Part number or manufacturer number is required.")
            return

        count = self.parse_int(self.count_input.text(), "Count")
        if count is None:
            return

        low_stock_text = self.low_stock_input.text().strip()
        low_stock = self.parse_int(low_stock_text, "Low stock threshold") if low_stock_text else "N/A"
        if low_stock is None:
            return

        try:
            location = self.resolve_storage_location(
                storage_mode,
                bin_location=self.bin_input.currentData(),
                manual_location=self.location_input.text(),
                component_type=component_type,
            )
        except ValueError as exc:
            title = "Missing Bin" if storage_mode == self.STORAGE_MODE_BIN else "Missing Location"
            QMessageBox.warning(self, title, str(exc))
            return

        component = {
            "part_info": {
                "part_number": part_number or manufacturer_number,
                "manufacturer_number": manufacturer_number or part_number,
                "location": location or "N/A",
                "count": count,
                "type": component_type,
            },
            "metadata": {
                "price": self.price_input.text().strip() or "N/A",
                "low_stock": low_stock,
                "description": self.description_input.toPlainText().strip() or "N/A",
                "photo_url": self.photo_url_input.text().strip() or "N/A",
                "datasheet_url": self.datasheet_url_input.text().strip() or "N/A",
                "product_url": self.product_url_input.text().strip() or "N/A",
                "in_use": "Available",
            },
        }

        try:
            self.backend.add_component(component)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            return

        QMessageBox.information(self, "Part Saved", "The part was added to the catalogue.")
        self.clear_form()
        self.refresh()
        self.part_added.emit()

    def resolve_storage_location(self, storage_mode, bin_location="", manual_location="", component_type=""):
        if storage_mode == self.STORAGE_MODE_AUTO_BIN:
            return getattr(self.backend, "get_auto_bin_for_type", lambda value: "Bin 10")(component_type)
        if storage_mode == self.STORAGE_MODE_BIN:
            location = str(bin_location or "").strip()
            if not location:
                raise ValueError("Select a bin for this component.")
            return location
        if storage_mode == self.STORAGE_MODE_MANUAL:
            location = str(manual_location).strip()
            if not location:
                raise ValueError("Enter a manual location or switch to Auto Vial.")
            return location
        return "N/A"

    def open_barcode_dialog(self):
        dialog = BarcodeScanDialog(self.backend, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        barcode, low_stock, storage_mode, storage_location = dialog.values()
        try:
            barcode_data = self.backend.barcode_decoder(barcode, show_errors=False)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Barcode", str(exc))
            return

        if self._handle_barcode_duplicate(barcode_data):
            self.refresh()
            self.part_added.emit()
            return

        if not self.digikey_api:
            self._populate_manual_barcode_data(barcode_data, low_stock, storage_mode, storage_location)
            QMessageBox.information(self, "DigiKey Unavailable", "DigiKey lookup is unavailable. The Add Part form was populated from the barcode.")
            return

        self.start_lookup(
            barcode_data["part_number"],
            {
                "mode": "barcode",
                "barcode_data": barcode_data,
                "low_stock": low_stock,
                "storage_mode": storage_mode,
                "storage_location": storage_location,
            },
        )

    def open_bulk_barcode_dialog(self):
        dialog = BulkBarcodeDialog(self.backend, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        entries = dialog.entries()
        self.process_bulk_barcodes(entries)

    def process_bulk_barcodes(self, entries):
        summary = {
            "added": 0,
            "duplicates": 0,
            "invalid": [],
            "unmatched": [],
            "errors": [],
            "possible_duplicates": [],
        }

        for entry in entries:
            try:
                barcode_data = self.backend.barcode_decoder(entry["barcode"], show_errors=False)
            except ValueError as exc:
                summary["invalid"].append(f"{entry['barcode'][:32]}: {exc}")
                continue

            duplicate_result = self._handle_barcode_duplicate(barcode_data, interactive=False)
            if duplicate_result == "duplicate":
                summary["duplicates"] += 1
                continue
            if duplicate_result == "possible_duplicate":
                summary["possible_duplicates"].append(barcode_data.get("manufacturer_number", barcode_data.get("part_number", "Unknown")))
                continue

            if not self.digikey_api:
                summary["unmatched"].append(barcode_data.get("part_number", "Unknown"))
                continue

            component = self.digikey_api.fetch_part_details(barcode_data["part_number"])
            error = getattr(self.digikey_api, "last_error", "")
            if error:
                summary["errors"].append(f"{barcode_data['part_number']}: {error}")
                continue
            if not component:
                summary["unmatched"].append(barcode_data.get("part_number", "Unknown"))
                continue

            component["part_info"]["count"] = int(barcode_data.get("count", 0))
            component["metadata"]["low_stock"] = entry["low_stock"]
            component["part_info"]["location"] = self.resolve_storage_location(
                entry.get("storage_mode"),
                bin_location=entry.get("storage_location", ""),
                manual_location=entry.get("storage_location", ""),
                component_type=component.get("part_info", {}).get("type", ""),
            )
            try:
                self.backend.add_component(component)
                summary["added"] += 1
            except Exception as exc:
                summary["errors"].append(f"{barcode_data['part_number']}: {exc}")

        self.refresh()
        self.part_added.emit()
        self._show_bulk_summary(summary)

    def _show_bulk_summary(self, summary):
        lines = [
            f"Added: {summary['added']}",
            f"Updated duplicates: {summary['duplicates']}",
        ]
        if summary["possible_duplicates"]:
            lines.append(f"Possible duplicates skipped: {len(summary['possible_duplicates'])}")
        if summary["unmatched"]:
            lines.append(f"No DigiKey match: {len(summary['unmatched'])}")
        if summary["invalid"]:
            lines.append(f"Invalid barcodes: {len(summary['invalid'])}")
        if summary["errors"]:
            lines.append(f"Errors: {len(summary['errors'])}")

        details = []
        if summary["possible_duplicates"]:
            details.append("Possible duplicates:")
            details.extend(summary["possible_duplicates"][:5])
        if summary["unmatched"]:
            details.append("No DigiKey match:")
            details.extend(summary["unmatched"][:5])
        if summary["invalid"]:
            details.append("Invalid:")
            details.extend(summary["invalid"][:5])
        if summary["errors"]:
            details.append("Errors:")
            details.extend(summary["errors"][:5])

        message = "\n".join(lines)
        if details:
            message = f"{message}\n\n" + "\n".join(details)
        QMessageBox.information(self, "Bulk Scan Complete", message)

    def _handle_barcode_duplicate(self, barcode_data, interactive=True):
        new_raw = barcode_data.get("manufacturer_number", "").strip().lower()
        if not new_raw:
            return False

        new_part_number = self.backend.normalize_part_number(new_raw)
        existing_components = self.backend.get_all_components()
        part_map = {}
        normalized_parts = []

        for component in existing_components:
            manufacturer = component.get("part_info", {}).get("manufacturer_number", "").strip().lower()
            if manufacturer:
                normalized = self.backend.normalize_part_number(manufacturer)
                part_map[normalized] = manufacturer
                normalized_parts.append(normalized)

        if new_part_number in normalized_parts:
            actual_match = part_map[new_part_number]
            for component in existing_components:
                existing = component.get("part_info", {}).get("manufacturer_number", "").strip().lower()
                if existing == actual_match:
                    self._increment_existing_component(component, barcode_data, "barcode exact match")
                    if interactive:
                        QMessageBox.information(self, "Duplicate Found", f"Updated existing component {actual_match} from the scanned barcode.")
                    return "duplicate"

        close_matches = difflib.get_close_matches(new_part_number, normalized_parts, n=1, cutoff=0.8)
        if close_matches:
            suggested_norm = close_matches[0]
            suggested_actual = part_map[suggested_norm]
            if not interactive:
                return "possible_duplicate"
            response = QMessageBox.question(
                self,
                "Possible Duplicate",
                f"Did you mean '{suggested_actual}' instead of '{new_raw}'?",
            )
            if response == QMessageBox.StandardButton.Yes:
                for component in existing_components:
                    existing = component.get("part_info", {}).get("manufacturer_number", "").strip().lower()
                    if existing == suggested_actual:
                        self._increment_existing_component(component, barcode_data, "barcode fuzzy match")
                        QMessageBox.information(self, "Duplicate Found", f"Updated existing component {suggested_actual} from the scanned barcode.")
                        return "duplicate"

        return False

    def _increment_existing_component(self, component, barcode_data, reason):
        try:
            existing_count = int(component.get("part_info", {}).get("count", 0))
        except ValueError:
            existing_count = 0
        new_count = existing_count + int(barcode_data.get("count", 0))
        component["part_info"]["count"] = new_count
        self.backend.log_change(
            f"Updated component '{component.get('part_info', {}).get('manufacturer_number', 'Unknown')}' "
            f"count from {existing_count} to {new_count} ({reason})."
        )
        self.backend.save_components()

    def _populate_manual_barcode_data(self, barcode_data, low_stock, storage_mode=None, storage_location=None):
        self.part_number_input.setText(str(barcode_data.get("part_number", "")))
        self.manufacturer_number_input.setText(str(barcode_data.get("manufacturer_number", "")))
        self.location_input.clear()
        self.type_input.setCurrentText("Other")
        self.set_storage_from_location(
            storage_location if storage_mode != self.STORAGE_MODE_AUTO else "N/A",
            storage_mode=storage_mode,
        )
        self.count_input.setText(str(barcode_data.get("count", "")))
        self.low_stock_input.setText(str(low_stock))
        self.price_input.clear()
        self.description_input.clear()
        self.photo_url_input.clear()
        self.datasheet_url_input.clear()
        self.product_url_input.clear()
        self.loaded_digikey_component = None

    def parse_int(self, value, label):
        try:
            return int(value)
        except ValueError:
            QMessageBox.warning(self, "Invalid Number", f"{label} must be an integer.")
            return None

    def clear_form(self):
        self.loaded_digikey_component = None
        for widget in (
            self.lookup_input,
            self.part_number_input,
            self.manufacturer_number_input,
            self.location_input,
            self.count_input,
            self.low_stock_input,
            self.price_input,
            self.photo_url_input,
            self.datasheet_url_input,
            self.product_url_input,
        ):
            widget.clear()
        self.description_input.clear()
        self.type_input.setCurrentText("Other")
        self.storage_type_input.setCurrentIndex(self.storage_type_input.findData(self.STORAGE_MODE_AUTO))
        self.refresh_bin_locations()
        self.update_storage_mode()

    def refresh(self):
        self.recent_table.set_components(self.backend.get_all_components()[:25])

    def delete_selected_component(self):
        component = self.recent_table.selected_component()
        if component is None:
            QMessageBox.warning(self, "Delete Component", "Select a component from the recent parts list to delete.")
            return

        part_info = component.get("part_info", {})
        label = part_info.get("part_number") or part_info.get("manufacturer_number") or "this component"
        response = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {label} from the catalogue?",
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        component_index = find_component_index(self.backend, component)
        if component_index < 0:
            QMessageBox.warning(self, "Delete Component", "Could not locate this component in the catalogue.")
            return

        self.backend.delete_component(component_index)
        self.component_deleted.emit()


class DigikeyLookupWorker(QObject):
    finished = pyqtSignal(object, str)

    def __init__(self, digikey_api, part_number):
        super().__init__()
        self.digikey_api = digikey_api
        self.part_number = part_number

    def run(self):
        try:
            component = self.digikey_api.fetch_part_details(self.part_number)
            error = getattr(self.digikey_api, "last_error", "")
            self.finished.emit(component, error if component is None else "")
        except Exception as exc:
            self.finished.emit(None, str(exc))


class MetricCard(QFrame):
    def __init__(self, label, value):
        super().__init__()
        self.setObjectName("metricCard")
        self.setMinimumWidth(170)
        self.setMaximumWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricValue")
        label_widget = QLabel(label)
        label_widget.setObjectName("metricLabel")

        layout.addWidget(self.value_label)
        layout.addWidget(label_widget)

    def set_value(self, value):
        self.value_label.setText(value)


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("helpDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("How To Use L.E.A.D.")
        self.setModal(True)
        self.resize(860, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("helpPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(14)
        layout.addWidget(panel)

        title = QLabel("How To Use L.E.A.D.")
        title.setObjectName("pageTitle")
        panel_layout.addWidget(title)

        hint = QLabel("Use this guide for the main workflows: setup, adding parts, scanning, checkout, and BOM processing.")
        hint.setObjectName("barcodeHint")
        hint.setWordWrap(True)
        panel_layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel_layout.addWidget(scroll, 1)

        body = QWidget()
        body.setObjectName("pageViewport")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)
        scroll.setWidget(body)

        sections = (
            (
                "Getting Started",
                (
                    "Use the gear button to enter DigiKey, serial, and file-path settings.",
                    "If this is a fresh setup, save settings first so the app can create any missing runtime files.",
                    "The LED status card on Home shows whether the lighting hardware is connected.",
                ),
            ),
            (
                "Navigation",
                (
                    "Home shows inventory stats, low-stock parts, LED status, and BOM actions.",
                    "Inventory is for searching, reviewing, and deleting existing parts.",
                    "Add Part is for DigiKey lookup, manual entry, barcode scans, and bulk scans.",
                ),
            ),
            (
                "Adding Parts",
                (
                    "Use DigiKey Lookup when you know a DigiKey or manufacturer part number.",
                    "Use the Storage selector to choose between automatic vial assignment, automatic type-based bin assignment, a shared bin, or a manual location.",
                    "Fill in Count and Low Stock before saving. In Auto Vial mode, the app assigns the next open vial slot.",
                    "The Recently Added table at the bottom of Add Part lets you review or open details right away.",
                ),
            ),
            (
                "Barcode Scanning",
                (
                    "Scan Barcode on the Add Part page handles one barcode at a time.",
                    "Bulk Scan lets you paste or scan several barcodes and low-stock values in one pass.",
                    "If a barcode does not resolve through DigiKey, the Add Part form is populated for manual review.",
                ),
            ),
            (
                "Part Details",
                (
                    "Double-click any part row to open the Part Details window.",
                    "Use Edit to make fields writable, then Save to commit changes back to the catalogue.",
                    "Highlight turns the LED for that location on and off. Checkout removes quantity and guides the grab/return flow.",
                ),
            ),
            (
                "BOM Workflows",
                (
                    "Start BOM checkout or check-in from Home and choose a CSV file.",
                    "The preview colors rows by status: green means enough stock, yellow means too few parts, red means not found.",
                    "During checkout, the app can highlight storage locations for the required vials if the LED system is connected.",
                ),
            ),
            (
                "Inventory Management",
                (
                    "Use Inventory search to filter by part number, manufacturer number, type, location, or other displayed data.",
                    "Delete removes the selected part from the catalogue. Undo Delete restores the most recent removal.",
                    "Low-stock export writes a text report you can use for reordering.",
                ),
            ),
            (
                "Helpful Shortcuts",
                (
                    "Press Enter in lookup and quantity fields to trigger the same action as the main button.",
                    "Press Ctrl+Alt+T to toggle Test Mode and switch to the test catalogue file.",
                    "Double-clicking a part row is the fastest way to view details, edit, highlight, or check out parts.",
                ),
            ),
        )

        for heading, bullets in sections:
            group = QGroupBox(heading)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(12, 12, 12, 12)
            group_layout.setSpacing(8)
            for bullet in bullets:
                label = QLabel(f"- {bullet}")
                label.setWordWrap(True)
                group_layout.addWidget(label)
            body_layout.addWidget(group)

        body_layout.addStretch(1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        panel_layout.addLayout(actions)


class AvailabilityManagerDialog(QDialog):
    availability_changed = pyqtSignal()

    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.setObjectName("settingsDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Part Availability")
        self.setModal(True)
        self.resize(960, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("settingsPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)
        layout.addWidget(panel)

        title = QLabel("Part Availability")
        title.setObjectName("pageTitle")
        panel_layout.addWidget(title)

        hint = QLabel("Review every part's current availability status and force items back to Available one at a time or all at once.")
        hint.setObjectName("barcodeHint")
        hint.setWordWrap(True)
        panel_layout.addWidget(hint)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("Part Number", "Manufacturer Number", "Location", "Availability", "Action"))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        panel_layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("barcodeHint")
        actions.addWidget(self.summary_label)
        actions.addStretch(1)
        force_all_button = QPushButton("Force All Available")
        force_all_button.clicked.connect(self.force_all_available)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        actions.addWidget(force_all_button)
        actions.addWidget(close_button)
        panel_layout.addLayout(actions)

        self.refresh_table()

    def refresh_table(self):
        rows = self.backend.get_component_availability()
        self.table.setRowCount(len(rows))

        unavailable_count = 0
        for row_index, row in enumerate(rows):
            in_use = row.get("in_use", "Available")
            is_available = str(in_use).strip().lower() == "available"
            if not is_available:
                unavailable_count += 1

            values = (
                row.get("part_number", "N/A"),
                row.get("manufacturer_number", "N/A"),
                row.get("location", "N/A"),
                in_use,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 3:
                    item.setData(
                        Qt.ItemDataRole.ForegroundRole,
                        QColor("#0f5132") if is_available else QColor("#7a1f1f"),
                    )
                self.table.setItem(row_index, column, item)

            button = QPushButton("Force Available")
            button.setEnabled(not is_available)
            button.clicked.connect(lambda _checked=False, index=row["index"]: self.force_single_available(index))
            self.table.setCellWidget(row_index, 4, button)

        total = len(rows)
        self.summary_label.setText(f"Unavailable: {unavailable_count} of {total}")

    def force_single_available(self, index):
        changed = self.backend.set_component_available(index)
        if changed:
            self.availability_changed.emit()
        self.refresh_table()

    def force_all_available(self):
        changed = self.backend.set_all_components_available()
        if changed:
            self.availability_changed.emit()
            QMessageBox.information(self, "Availability Updated", f"Forced {changed} parts to Available.")
        else:
            QMessageBox.information(self, "Availability Updated", "All parts were already marked Available.")
        self.refresh_table()


class SettingsDialog(QDialog):
    config_saved = pyqtSignal()
    availability_changed = pyqtSignal()

    FIELD_GROUPS = (
        (
            "API",
            (
                ("DIGIKEY_CLIENT_ID", "DigiKey Client ID"),
                ("DIGIKEY_CLIENT_SECRET", "DigiKey Client Secret"),
            ),
        ),
        (
            "SERIAL",
            (
                ("PORT", "Serial Port"),
                ("BAUDRATE", "Baud Rate"),
                ("TIMEOUT", "Timeout"),
            ),
        ),
        (
            "FILES",
            (
                ("COMPONENT_CATALOGUE", "Component Catalogue"),
                ("CHANGELOG", "Changelog"),
                ("IMAGE_CACHE", "Image Cache"),
            ),
        ),
    )

    def __init__(self, initializer, backend, digikey_api=None, parent=None):
        super().__init__(parent)
        self.initializer = initializer
        self.backend = backend
        self.digikey_api = digikey_api
        self.inputs = {}

        self.setObjectName("settingsDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(760, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("settingsPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(14)
        layout.addWidget(panel)

        title = QLabel("Setup and Settings")
        title.setObjectName("pageTitle")
        panel_layout.addWidget(title)

        hint = QLabel("Edit the application configuration here. Blank file paths fall back to the default Databases folder.")
        hint.setObjectName("barcodeHint")
        hint.setWordWrap(True)
        panel_layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel_layout.addWidget(scroll, 1)

        scroll_body = QWidget()
        scroll_body.setObjectName("pageViewport")
        form_stack = QVBoxLayout(scroll_body)
        form_stack.setContentsMargins(0, 0, 0, 0)
        form_stack.setSpacing(12)
        scroll.setWidget(scroll_body)

        config = self.initializer.load_config()
        for section_name, fields in self.FIELD_GROUPS:
            group = QGroupBox(section_name)
            form = QFormLayout(group)
            form.setContentsMargins(12, 12, 12, 12)
            form.setSpacing(10)

            for key, label in fields:
                editor = QLineEdit()
                editor.setText(str(config.get(section_name, {}).get(key, "")))
                if "SECRET" in key:
                    editor.setEchoMode(QLineEdit.EchoMode.Password)
                self.inputs[(section_name, key)] = editor
                form.addRow(label, editor)

            form_stack.addWidget(group)

        form_stack.addStretch(1)

        actions = QHBoxLayout()
        availability_button = QPushButton("Manage Availability")
        availability_button.clicked.connect(self.open_availability_dialog)
        actions.addWidget(availability_button)
        actions.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)
        actions.addWidget(cancel_button)
        actions.addWidget(save_button)
        panel_layout.addLayout(actions)

    def save_settings(self):
        config = self.initializer.load_config()
        for (section, key), editor in self.inputs.items():
            value = editor.text().strip()
            config.setdefault(section, {})[key] = value

        if not self._validate_numeric(config):
            return

        self.initializer.save_config(config)
        self.initializer.ensure_runtime_files()
        self._apply_runtime_settings(config)
        self.config_saved.emit()
        QMessageBox.information(self, "Settings Saved", "Configuration updated successfully.")
        self.accept()

    def _validate_numeric(self, config):
        baudrate = str(config.get("SERIAL", {}).get("BAUDRATE", "")).strip()
        timeout = str(config.get("SERIAL", {}).get("TIMEOUT", "")).strip()
        if baudrate and not baudrate.isdigit():
            QMessageBox.warning(self, "Invalid Baud Rate", "Baud Rate must be blank or an integer.")
            return False
        if timeout and not timeout.isdigit():
            QMessageBox.warning(self, "Invalid Timeout", "Timeout must be blank or an integer.")
            return False
        return True

    def _apply_runtime_settings(self, config):
        files_config = config.get("FILES", {})
        self.backend.data_file = self.initializer.resolve_file_path(files_config.get("COMPONENT_CATALOGUE", ""), "COMPONENT_CATALOGUE")
        self.backend.changelog_file = self.initializer.resolve_file_path(files_config.get("CHANGELOG", ""), "CHANGELOG")
        self.backend.load_components()

        if self.digikey_api is not None:
            self.digikey_api.load_config()
            self.digikey_api.image_cache = ImageCache()

        led_controller = getattr(self.backend, "ledControl", None)
        if led_controller is not None and hasattr(led_controller, "load_config"):
            led_controller.load_config()
        if led_controller is not None and hasattr(led_controller, "reconnect"):
            led_controller.reconnect()

    def open_availability_dialog(self):
        dialog = AvailabilityManagerDialog(self.backend, self)
        dialog.availability_changed.connect(self.availability_changed.emit)
        dialog.exec()


class BomStatusItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        background = index.data(BOM_ROW_BACKGROUND_ROLE)
        foreground = index.data(BOM_ROW_FOREGROUND_ROLE)
        display_text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")

        painter.save()
        fill_color = background if isinstance(background, QColor) else QColor("#ffffff")
        painter.fillRect(option.rect, fill_color)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(0, 0, 0, 12))

        text_color = foreground if isinstance(foreground, QColor) else QColor("#20242b")
        text_rect = option.rect.adjusted(10, 0, -10, 0)
        elided_text = option.fontMetrics.elidedText(
            display_text,
            Qt.TextElideMode.ElideRight,
            max(text_rect.width(), 0),
        )
        painter.setFont(option.font)
        painter.setPen(text_color)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            elided_text,
        )

        grid_pen = QPen(QColor("#e1e5ea"))
        painter.setPen(grid_pen)
        painter.drawLine(option.rect.topRight(), option.rect.bottomRight())
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

        if option.state & QStyle.StateFlag.State_HasFocus:
            focus_pen = QPen(QColor("#7f9c95"))
            painter.setPen(focus_pen)
            painter.drawRect(option.rect.adjusted(0, 0, -1, -1))

        painter.restore()


class BarcodeScanDialog(QDialog):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.setObjectName("barcodeDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Scan Barcode")
        self.setModal(True)
        self.resize(560, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        panel = QFrame()
        panel.setObjectName("barcodePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)
        layout.addWidget(panel)

        title = QLabel("Scan Barcode")
        title.setObjectName("pageTitle")
        panel_layout.addWidget(title)

        hint = QLabel("Paste or scan the barcode payload, set the low stock threshold, then choose whether the part goes to a vial, an automatic type-based bin, or a specific shared bin.")
        hint.setObjectName("barcodeHint")
        hint.setWordWrap(True)
        panel_layout.addWidget(hint)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.barcode_input = SubmitTextEdit()
        self.barcode_input.setMinimumHeight(96)
        self.low_stock_input = QLineEdit()
        self.low_stock_input.setPlaceholderText("Required")
        self.storage_type_input = QComboBox()
        self.storage_type_input.addItem("Auto Vial", AddPartPage.STORAGE_MODE_AUTO)
        self.storage_type_input.addItem("Auto Bin", AddPartPage.STORAGE_MODE_AUTO_BIN)
        self.storage_type_input.addItem("Shared Bin", AddPartPage.STORAGE_MODE_BIN)
        self.storage_type_input.addItem("Manual Location", AddPartPage.STORAGE_MODE_MANUAL)
        self.auto_location_input = QLineEdit()
        self.auto_location_input.setReadOnly(True)
        self.auto_location_input.setText("Next available vial will be assigned automatically")
        self.auto_bin_input = QLineEdit()
        self.auto_bin_input.setReadOnly(True)
        self.auto_bin_input.setText("Assigned automatically from the resolved part type")
        self.bin_input = QComboBox()
        populate_bin_combo(self.bin_input, self.backend)
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("Example: 3A")
        self.location_stack = QStackedWidget()
        self.location_stack.addWidget(self.auto_location_input)
        self.location_stack.addWidget(self.auto_bin_input)
        self.location_stack.addWidget(self.bin_input)
        self.location_stack.addWidget(self.location_input)

        form.addWidget(QLabel("Barcode"), 0, 0, alignment=Qt.AlignmentFlag.AlignTop)
        form.addWidget(self.barcode_input, 0, 1)
        form.addWidget(QLabel("Low Stock"), 1, 0)
        form.addWidget(self.low_stock_input, 1, 1)
        form.addWidget(QLabel("Storage"), 2, 0)
        form.addWidget(self.storage_type_input, 2, 1)
        form.addWidget(QLabel("Location"), 3, 0)
        form.addWidget(self.location_stack, 3, 1)
        panel_layout.addLayout(form)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        process_button = QPushButton("Process")
        process_button.clicked.connect(self.validate_and_accept)
        actions.addWidget(cancel_button)
        actions.addWidget(process_button)
        panel_layout.addLayout(actions)

        self.barcode_input.submitRequested.connect(self.validate_and_accept)
        self.low_stock_input.returnPressed.connect(self.validate_and_accept)
        self.storage_type_input.currentIndexChanged.connect(self.update_storage_mode)
        self.update_storage_mode()
        self.barcode_input.setFocus()

    def update_storage_mode(self):
        mode = self.storage_type_input.currentData()
        if mode == AddPartPage.STORAGE_MODE_AUTO_BIN:
            self.location_stack.setCurrentWidget(self.auto_bin_input)
        elif mode == AddPartPage.STORAGE_MODE_BIN:
            self.location_stack.setCurrentWidget(self.bin_input)
        elif mode == AddPartPage.STORAGE_MODE_MANUAL:
            self.location_stack.setCurrentWidget(self.location_input)
        else:
            self.location_stack.setCurrentWidget(self.auto_location_input)

    def validate_and_accept(self):
        barcode = self.barcode_input.toPlainText().strip()
        low_stock_text = self.low_stock_input.text().strip()
        if not barcode:
            QMessageBox.warning(self, "Missing Barcode", "Scan or paste a barcode value.")
            return
        try:
            int(low_stock_text)
        except ValueError:
            QMessageBox.warning(self, "Invalid Low Stock", "Low Stock must be an integer.")
            return
        storage_mode = self.storage_type_input.currentData()
        if storage_mode == AddPartPage.STORAGE_MODE_BIN and not self.bin_input.currentText().strip():
            QMessageBox.warning(self, "Missing Bin", "Select a bin for this component.")
            return
        if storage_mode == AddPartPage.STORAGE_MODE_MANUAL and not self.location_input.text().strip():
            QMessageBox.warning(self, "Missing Location", "Enter a manual location or switch to Auto Vial.")
            return
        self.accept()

    def values(self):
        storage_mode = self.storage_type_input.currentData()
        if storage_mode == AddPartPage.STORAGE_MODE_BIN:
            storage_location = str(self.bin_input.currentData() or "").strip()
        elif storage_mode == AddPartPage.STORAGE_MODE_MANUAL:
            storage_location = self.location_input.text().strip()
        else:
            storage_location = "N/A"
        return (
            self.barcode_input.toPlainText().strip(),
            int(self.low_stock_input.text().strip()),
            storage_mode,
            storage_location,
        )


class SubmitTextEdit(QTextEdit):
    submitRequested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.submitRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class BulkBarcodeDialog(QDialog):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.setObjectName("bulkBarcodeDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Bulk Scan")
        self.setModal(True)
        self.resize(820, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        panel = QFrame()
        panel.setObjectName("bulkBarcodePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)
        layout.addWidget(panel)

        title = QLabel("Bulk Scan")
        title.setObjectName("pageTitle")
        panel_layout.addWidget(title)

        hint = QLabel("Enter one barcode and one low stock threshold per row. Choose the storage mode for this batch. Empty rows are ignored.")
        hint.setObjectName("barcodeHint")
        hint.setWordWrap(True)
        panel_layout.addWidget(hint)

        storage_form = QGridLayout()
        storage_form.setHorizontalSpacing(12)
        storage_form.setVerticalSpacing(10)
        self.storage_type_input = QComboBox()
        self.storage_type_input.addItem("Auto Vial", AddPartPage.STORAGE_MODE_AUTO)
        self.storage_type_input.addItem("Auto Bin", AddPartPage.STORAGE_MODE_AUTO_BIN)
        self.storage_type_input.addItem("Shared Bin", AddPartPage.STORAGE_MODE_BIN)
        self.storage_type_input.addItem("Manual Location", AddPartPage.STORAGE_MODE_MANUAL)
        self.auto_location_input = QLineEdit()
        self.auto_location_input.setReadOnly(True)
        self.auto_location_input.setText("All scanned parts will use automatic vial assignment")
        self.auto_bin_input = QLineEdit()
        self.auto_bin_input.setReadOnly(True)
        self.auto_bin_input.setText("Each scanned part will be assigned from its resolved part type")
        self.bin_input = QComboBox()
        populate_bin_combo(self.bin_input, self.backend)
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("Example: 3A")
        self.location_stack = QStackedWidget()
        self.location_stack.addWidget(self.auto_location_input)
        self.location_stack.addWidget(self.auto_bin_input)
        self.location_stack.addWidget(self.bin_input)
        self.location_stack.addWidget(self.location_input)
        storage_form.addWidget(QLabel("Batch Storage"), 0, 0)
        storage_form.addWidget(self.storage_type_input, 0, 1)
        storage_form.addWidget(QLabel("Location"), 1, 0)
        storage_form.addWidget(self.location_stack, 1, 1)
        panel_layout.addLayout(storage_form)

        toolbar = QHBoxLayout()
        add_row_button = QPushButton("Add Row")
        add_row_button.clicked.connect(self.add_row)
        remove_row_button = QPushButton("Remove Selected")
        remove_row_button.clicked.connect(self.remove_selected_rows)
        toolbar.addWidget(add_row_button)
        toolbar.addWidget(remove_row_button)
        toolbar.addStretch(1)
        panel_layout.addLayout(toolbar)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(("Barcode", "Low Stock"))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setMinimumHeight(280)
        panel_layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        process_button = QPushButton("Process All")
        process_button.clicked.connect(self.validate_and_accept)
        actions.addWidget(cancel_button)
        actions.addWidget(process_button)
        panel_layout.addLayout(actions)

        self.storage_type_input.currentIndexChanged.connect(self.update_storage_mode)
        for _ in range(5):
            self.add_row()
        self.update_storage_mode()
        self.table.setCurrentCell(0, 0)
        self.table.editItem(self.table.item(0, 0))

    def update_storage_mode(self):
        mode = self.storage_type_input.currentData()
        if mode == AddPartPage.STORAGE_MODE_AUTO_BIN:
            self.location_stack.setCurrentWidget(self.auto_bin_input)
        elif mode == AddPartPage.STORAGE_MODE_BIN:
            self.location_stack.setCurrentWidget(self.bin_input)
        elif mode == AddPartPage.STORAGE_MODE_MANUAL:
            self.location_stack.setCurrentWidget(self.location_input)
        else:
            self.location_stack.setCurrentWidget(self.auto_location_input)

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))

    def remove_selected_rows(self):
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()}, reverse=True)
        if not rows:
            return
        for row in rows:
            self.table.removeRow(row)
        if self.table.rowCount() == 0:
            self.add_row()

    def validate_and_accept(self):
        parsed_entries = []
        storage_mode = self.storage_type_input.currentData()
        if storage_mode == AddPartPage.STORAGE_MODE_BIN:
            storage_location = str(self.bin_input.currentData() or "").strip()
            if not storage_location:
                QMessageBox.warning(self, "Missing Bin", "Select a bin for this batch.")
                return
        elif storage_mode == AddPartPage.STORAGE_MODE_MANUAL:
            storage_location = self.location_input.text().strip()
            if not storage_location:
                QMessageBox.warning(self, "Missing Location", "Enter a manual location or switch to Auto Vial.")
                return
        else:
            storage_location = "N/A"

        for row in range(self.table.rowCount()):
            barcode_item = self.table.item(row, 0)
            low_stock_item = self.table.item(row, 1)
            barcode = barcode_item.text().strip() if barcode_item else ""
            low_stock_text = low_stock_item.text().strip() if low_stock_item else ""
            if not barcode and not low_stock_text:
                continue
            if not barcode:
                QMessageBox.warning(self, "Missing Barcode", f"Row {row + 1} is missing a barcode.")
                return
            try:
                low_stock = int(low_stock_text)
            except ValueError:
                QMessageBox.warning(self, "Invalid Low Stock", f"Row {row + 1} must have an integer low stock value.")
                return
            parsed_entries.append(
                {
                    "barcode": barcode,
                    "low_stock": low_stock,
                    "storage_mode": storage_mode,
                    "storage_location": storage_location,
                }
            )

        if not parsed_entries:
            QMessageBox.warning(self, "No Entries", "Enter at least one barcode row to process.")
            return

        if storage_mode == AddPartPage.STORAGE_MODE_MANUAL and len(parsed_entries) > 1:
            QMessageBox.warning(
                self,
                "Manual Location Not Allowed",
                "Manual Location can only be used with a single bulk-scan row. Use Auto Vial or Shared Bin for multi-row batches.",
            )
            return

        self._entries = parsed_entries
        self.accept()

    def entries(self):
        return getattr(self, "_entries", [])


class BomCheckoutPreviewDialog(QDialog):
    processed = pyqtSignal()

    def __init__(self, backend, bom_list, board_name, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.bom_list = bom_list
        self.board_name = board_name
        self.led_controller = getattr(backend, "ledControl", None)
        self.setObjectName("bomDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setWindowTitle("BOM Preview")
        self.setModal(True)
        self.resize(860, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("bomPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)
        layout.addWidget(panel)

        title = QLabel("BOM Checkout Preview")
        title.setObjectName("pageTitle")
        panel_layout.addWidget(title)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("bomStatusTable")
        self.table.setItemDelegate(BomStatusItemDelegate(self.table))
        self.table.setHorizontalHeaderLabels(("DigiKey", "Quantity", "Found", "Current Count", "Location"))
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setStyleSheet(
            """
            QTableWidget#bomStatusTable {
                selection-background-color: transparent;
                selection-color: #20242b;
            }
            QTableWidget#bomStatusTable::item {
                background: transparent;
                color: #20242b;
                border: none;
            }
            QTableWidget#bomStatusTable::item:selected {
                background: transparent;
                color: #20242b;
                border: none;
            }
            """
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        panel_layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_button = QPushButton("Close")
        cancel_button.clicked.connect(self.reject)
        process_button = QPushButton("Consume Components")
        process_button.clicked.connect(self.process_bom)
        actions.addWidget(cancel_button)
        actions.addWidget(process_button)
        panel_layout.addLayout(actions)

        self.populate_rows()
        self.table.currentCellChanged.connect(lambda *_: self.highlight_selected_location())
        if self.table.rowCount() > 0:
            self.table.setCurrentCell(0, 0)
            self.highlight_selected_location()

    def populate_rows(self):
        self.table.setRowCount(len(self.bom_list))
        for row_index, row in enumerate(self.bom_list):
            try:
                qty = int(row.get("quantity", 0))
            except ValueError:
                qty = 0
            current = row.get("current_count", 0) or 0
            if not row.get("found"):
                row_color = QColor("#f8d7da")
            elif current < qty:
                row_color = QColor("#fff3cd")
            else:
                row_color = QColor("#d1e7dd")
            values = (
                row.get("digikey", "N/A"),
                row.get("quantity", "0"),
                "Yes" if row.get("found") else "No",
                row.get("current_count", "N/A"),
                row.get("location", "N/A"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(BOM_ROW_BACKGROUND_ROLE, row_color)
                item.setData(BOM_ROW_FOREGROUND_ROLE, QColor("#20242b"))
                self.table.setItem(row_index, column, item)

    def highlight_selected_location(self):
        if self.led_controller is None or not hasattr(self.led_controller, "highlight_location"):
            return

        row = self.table.currentRow()
        if row < 0 or row >= len(self.bom_list):
            return

        selected = self.bom_list[row]
        if not selected.get("found"):
            return

        location = str(selected.get("location") or "").strip()
        if not location or location.upper() == "N/A":
            return

        self.led_controller.highlight_location(location)

    def process_bom(self):
        results = self.backend.process_bom_out(self.bom_list, self.board_name)
        self.processed.emit()
        self._turn_off_recent_leds()

        locations = [
            str(row.get("location")).strip()
            for row in self.bom_list
            if row.get("found") and str(row.get("location") or "").strip() and str(row.get("location")).strip().upper() != "N/A"
        ]
        if locations:
            leds_connected = self._leds_connected()
            if leds_connected and self.led_controller is not None and hasattr(self.led_controller, "highlight_all"):
                self.led_controller.highlight_all(locations)
                message = "Please grab all highlighted component vials, then press OK when done."
            else:
                message = "Please grab the required component vials for this BOM, then press OK when done."

            grab_dialog = CheckoutActionDialog(
                "Grab Components",
                message,
                "Components Grabbed",
                self,
            )
            grab_dialog.exec()
            if leds_connected:
                self._turn_off_all_leds()

        BomResultsDialog("BOM Processing Results", results, self).exec()
        self.accept()

    def reject(self):
        self._turn_off_all_leds()
        super().reject()

    def _turn_off_recent_leds(self):
        if self.led_controller is not None and hasattr(self.led_controller, "turn_off_recent"):
            self.led_controller.turn_off_recent()

    def _turn_off_all_leds(self):
        if self.led_controller is not None and hasattr(self.led_controller, "turn_off_all"):
            self.led_controller.turn_off_all()

    def _leds_connected(self):
        if self.led_controller is None:
            return False
        if hasattr(self.led_controller, "is_connected"):
            try:
                return bool(self.led_controller.is_connected())
            except Exception:
                return False
        return False


class BomCheckinPreviewDialog(QDialog):
    processed = pyqtSignal()

    def __init__(self, backend, bom_list, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.bom_list = bom_list
        self.led_controller = getattr(backend, "ledControl", None)
        self.setObjectName("bomDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setWindowTitle("BOM Return Preview")
        self.setModal(True)
        self.resize(920, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("bomPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)
        layout.addWidget(panel)

        title = QLabel("BOM Check In Preview")
        title.setObjectName("pageTitle")
        panel_layout.addWidget(title)

        self.table = QTableWidget(0, 6)
        self.table.setObjectName("bomStatusTable")
        self.table.setItemDelegate(BomStatusItemDelegate(self.table))
        self.table.setHorizontalHeaderLabels(("DigiKey", "Used", "Found", "Current Count", "Location", "Additional Used"))
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setStyleSheet(
            """
            QTableWidget#bomStatusTable {
                selection-background-color: transparent;
                selection-color: #20242b;
            }
            QTableWidget#bomStatusTable::item {
                background: transparent;
                color: #20242b;
                border: none;
            }
            QTableWidget#bomStatusTable::item:selected {
                background: transparent;
                color: #20242b;
                border: none;
            }
            """
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        panel_layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_button = QPushButton("Close")
        cancel_button.clicked.connect(self.reject)
        process_button = QPushButton("Return Components")
        process_button.clicked.connect(self.process_bom)
        actions.addWidget(cancel_button)
        actions.addWidget(process_button)
        panel_layout.addLayout(actions)

        self.populate_rows()

    def populate_rows(self):
        self.table.setRowCount(len(self.bom_list))
        for row_index, row in enumerate(self.bom_list):
            values = (
                row.get("digikey", "N/A"),
                row.get("quantity", "0"),
                "Yes" if row.get("found") else "No",
                row.get("current_count", "N/A"),
                row.get("location", "N/A"),
            )
            row_background = QColor("#ffffff") if row.get("found") else QColor("#f8d7da")
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(BOM_ROW_BACKGROUND_ROLE, row_background)
                item.setData(BOM_ROW_FOREGROUND_ROLE, QColor("#20242b"))
                self.table.setItem(row_index, column, item)

            spin = QSpinBox()
            spin.setMinimum(0)
            spin.setMaximum(999999)
            spin.setStyleSheet(
                """
                QSpinBox {
                    background: #ffffff;
                    color: #20242b;
                    border: 1px solid #c8ced6;
                    border-radius: 4px;
                    padding: 6px 26px 6px 8px;
                    selection-background-color: #d8eee8;
                    selection-color: #20242b;
                }
                QSpinBox::up-button, QSpinBox::down-button {
                    background: #ffffff;
                    border: none;
                    width: 18px;
                }
                QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                    background: #f3f5f7;
                }
                QSpinBox::up-arrow, QSpinBox::down-arrow {
                    width: 9px;
                    height: 9px;
                }
                """
            )
            self.table.setCellWidget(row_index, 5, spin)

    def process_bom(self):
        additional_usage = {}
        for row_index, row in enumerate(self.bom_list):
            spin = self.table.cellWidget(row_index, 5)
            additional_usage[row.get("digikey", "")] = spin.value() if spin else 0

        self._guide_component_returns()
        results = self.backend.process_returned_vials(self.bom_list, additional_usage)
        self.processed.emit()
        BomResultsDialog("BOM Return Results", results, self).exec()
        self.accept()

    def reject(self):
        self._turn_off_all_leds()
        super().reject()

    def _guide_component_returns(self):
        for row in self.bom_list:
            if not row.get("found"):
                continue

            location = str(row.get("location") or "").strip()
            if not location or location.upper() == "N/A":
                continue

            part_number = str(row.get("digikey") or "this part").strip()
            led_enabled = self._leds_connected() and self._supports_led_location(location)
            if led_enabled and self.led_controller is not None and hasattr(self.led_controller, "highlight_location"):
                self.led_controller.highlight_location(location)

            message = f"Return {part_number} to location {location}, then press OK."
            dialog = CheckoutActionDialog(
                "Return Component",
                message,
                "Component Returned",
                self,
            )
            dialog.exec()
            self._turn_off_location_led(location)

        self._turn_off_all_leds()

    def _turn_off_location_led(self, location):
        if self.led_controller is None or not location:
            return
        if self._supports_led_location(location) and hasattr(self.led_controller, "turn_off_led"):
            self.led_controller.turn_off_led(location)
            return
        if hasattr(self.led_controller, "turn_off_recent"):
            self.led_controller.turn_off_recent()

    def _turn_off_all_leds(self):
        if self.led_controller is not None and hasattr(self.led_controller, "turn_off_all"):
            self.led_controller.turn_off_all()

    def _leds_connected(self):
        if self.led_controller is None:
            return False
        if hasattr(self.led_controller, "is_connected"):
            try:
                return bool(self.led_controller.is_connected())
            except Exception:
                return False
        return False

    def _supports_led_location(self, location):
        row_part = "".join(filter(str.isdigit, str(location or "")))
        col_part = "".join(filter(str.isalpha, str(location or "")))
        return bool(row_part and len(col_part) == 1)


class BomResultsDialog(QDialog):
    def __init__(self, title_text, results, parent=None):
        super().__init__(parent)
        self.setObjectName("bomResultsDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle(title_text)
        self.setModal(True)
        self.resize(720, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("bomResultsPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)
        layout.addWidget(panel)

        title = QLabel(title_text)
        title.setObjectName("pageTitle")
        panel_layout.addWidget(title)

        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(("Part", "Remaining", "Status"))
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setRowCount(len(results))

        for row_index, result in enumerate(results):
            values = (
                result.get("part", "N/A"),
                result.get("remaining", "N/A"),
                result.get("status", "N/A"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.BackgroundRole, QColor("#ffffff"))
                item.setData(Qt.ItemDataRole.ForegroundRole, QColor("#20242b"))
                table.setItem(row_index, column, item)

        panel_layout.addWidget(table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        panel_layout.addLayout(actions)


class QuantityPromptDialog(QDialog):
    def __init__(self, part_number, parent=None):
        super().__init__(parent)
        self.setObjectName("actionDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Checkout Part")
        self.setModal(True)
        self.resize(420, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("actionPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)
        layout.addWidget(panel)

        title = QLabel("Checkout Part")
        title.setObjectName("pageTitle")
        panel_layout.addWidget(title)

        message = QLabel(f"How many components do you want to remove from {part_number}?")
        message.setWordWrap(True)
        panel_layout.addWidget(message)

        self.quantity_input = QLineEdit()
        self.quantity_input.setPlaceholderText("Quantity")
        self.quantity_input.returnPressed.connect(self.validate_and_accept)
        panel_layout.addWidget(self.quantity_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        panel_layout.addWidget(buttons)

        self.quantity_input.setFocus()

    def validate_and_accept(self):
        try:
            quantity = int(self.quantity_input.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid Quantity", "Please enter a valid integer quantity.")
            return

        if quantity <= 0:
            QMessageBox.warning(self, "Invalid Quantity", "Quantity must be greater than zero.")
            return

        self._quantity = quantity
        self.accept()

    def quantity(self):
        return getattr(self, "_quantity", None)


class CheckoutActionDialog(QDialog):
    def __init__(self, title_text, message_text, button_text="OK", parent=None):
        super().__init__(parent)
        self.setObjectName("actionDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle(title_text)
        self.setModal(True)
        self.resize(480, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("actionPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)
        layout.addWidget(panel)

        title = QLabel(title_text)
        title.setObjectName("pageTitle")
        panel_layout.addWidget(title)

        message = QLabel(message_text)
        message.setWordWrap(True)
        panel_layout.addWidget(message)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText(button_text)
            ok_button.setDefault(True)
            ok_button.setAutoDefault(True)
        buttons.accepted.connect(self.accept)
        panel_layout.addWidget(buttons)


class ComponentDetailsDialog(QDialog):
    saved = pyqtSignal()

    PART_INFO_FIELDS = (
        ("part_number", "Part Number"),
        ("manufacturer_number", "Manufacturer Number"),
        ("location", "Location"),
        ("count", "Count"),
        ("type", "Type"),
    )

    METADATA_FIELDS = (
        ("price", "Price"),
        ("low_stock", "Low Stock"),
        ("in_use", "In Use"),
        ("photo_url", "Photo URL"),
        ("datasheet_url", "Datasheet URL"),
        ("product_url", "Product URL"),
    )

    def __init__(self, component, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.led_controller = getattr(backend, "ledControl", None)
        self.source_component = component
        self.component = deepcopy(component)
        self.edit_mode = False
        self.part_info_editors = {}
        self.metadata_editors = {}
        self.highlight_location = None
        self.setObjectName("detailsDialog")

        self.setWindowTitle("Part Details")
        self.setModal(True)
        self.resize(860, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)

        part_info = component.get("part_info", {})
        metadata = component.get("metadata", {})

        hero = QFrame()
        hero.setObjectName("detailsHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(6)

        eyebrow = QLabel("Part Details")
        eyebrow.setObjectName("detailsEyebrow")
        self.title_label = QLabel()
        self.title_label.setObjectName("detailsHeadline")
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("detailsSubline")

        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(self.title_label)
        hero_layout.addWidget(self.subtitle_label)
        layout.addWidget(hero)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.location_stat = self._build_stat_card("Location")
        self.count_stat = self._build_stat_card("Count")
        self.low_stock_stat = self._build_stat_card("Low Stock")
        stats_row.addWidget(self.location_stat)
        stats_row.addWidget(self.count_stat)
        stats_row.addWidget(self.low_stock_stat)
        stats_row.addStretch(1)
        layout.addLayout(stats_row)

        content = QGridLayout()
        content.setHorizontalSpacing(16)
        content.setVerticalSpacing(12)

        part_info_group = QGroupBox("Part Info")
        part_info_layout = QGridLayout(part_info_group)
        part_info_layout.setColumnStretch(1, 1)

        metadata_group = QGroupBox("Metadata")
        metadata_layout = QGridLayout(metadata_group)
        metadata_layout.setColumnStretch(1, 1)

        self._add_editor_rows(part_info_layout, self.PART_INFO_FIELDS, self.part_info_editors)
        self._add_editor_rows(metadata_layout, self.METADATA_FIELDS, self.metadata_editors)

        description_label = QLabel("Description")
        description_label.setObjectName("detailsFieldLabel")
        self.description_value = QTextEdit()
        self.description_value.setMinimumHeight(120)
        self._set_editor_readonly(self.description_value, True)

        metadata_layout.addWidget(description_label, metadata_layout.rowCount(), 0, alignment=Qt.AlignmentFlag.AlignTop)
        metadata_layout.addWidget(self.description_value, metadata_layout.rowCount() - 1, 1)

        content.addWidget(part_info_group, 0, 0)
        content.addWidget(metadata_group, 0, 1)
        content.setColumnStretch(0, 1)
        content.setColumnStretch(1, 1)
        layout.addLayout(content)

        links = QHBoxLayout()
        links.setSpacing(10)
        self.datasheet_button = QPushButton("Datasheet")
        self.datasheet_button.clicked.connect(lambda: self._open_url_field("datasheet_url"))
        self.product_button = QPushButton("Product Page")
        self.product_button.clicked.connect(lambda: self._open_url_field("product_url"))
        self.highlight_button = QPushButton("Highlight")
        self.highlight_button.setCheckable(True)
        self.highlight_button.toggled.connect(self.toggle_highlight)
        self.checkout_button = QPushButton("Checkout")
        self.checkout_button.clicked.connect(self.checkout_component)
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.enter_edit_mode)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_changes)
        self.save_button.hide()

        links.addWidget(self.datasheet_button)
        links.addWidget(self.product_button)
        links.addWidget(self.highlight_button)
        links.addWidget(self.checkout_button)
        links.addStretch(1)
        links.addWidget(self.edit_button)
        links.addWidget(self.save_button)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        links.addWidget(close_button)
        layout.addLayout(links)

        self.populate_from_component(self.component)

    def _add_editor_rows(self, layout, field_defs, target):
        for row_index, (field_key, label_text) in enumerate(field_defs):
            label = QLabel(label_text)
            label.setObjectName("detailsFieldLabel")
            value_label = QLineEdit()
            value_label.setObjectName("detailsFieldValue")
            self._set_editor_readonly(value_label, True)
            target[field_key] = value_label
            layout.addWidget(label, row_index, 0, alignment=Qt.AlignmentFlag.AlignTop)
            layout.addWidget(value_label, row_index, 1)

    def _build_stat_card(self, label_text):
        card = QFrame()
        card.setObjectName("detailsStatCard")
        card.setMinimumWidth(140)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(4)

        label = QLabel(str(label_text))
        label.setObjectName("detailsStatLabel")
        value_label = QLabel("")
        value_label.setObjectName("detailsStatValue")

        card_layout.addWidget(label)
        card_layout.addWidget(value_label)
        card.value_label = value_label
        return card

    def populate_from_component(self, component):
        previous_location = self._current_location()
        self.component = deepcopy(component)
        part_info = self.component.get("part_info", {})
        metadata = self.component.get("metadata", {})

        self.title_label.setText(str(part_info.get("part_number", "Part Details")))
        self.subtitle_label.setText(
            f"{part_info.get('manufacturer_number', 'N/A')}  |  {part_info.get('type', 'N/A')}"
        )
        self.location_stat.value_label.setText(str(part_info.get("location", "N/A")))
        self.count_stat.value_label.setText(str(part_info.get("count", "N/A")))
        self.low_stock_stat.value_label.setText(str(metadata.get("low_stock", "N/A")))

        for key, _ in self.PART_INFO_FIELDS:
            self.part_info_editors[key].setText(str(part_info.get(key, "N/A")))
        for key, _ in self.METADATA_FIELDS:
            self.metadata_editors[key].setText(str(metadata.get(key, "N/A")))

        self.description_value.setPlainText(str(metadata.get("description", "N/A")))
        self.refresh_link_buttons()
        self.set_edit_mode(False)
        if self.highlight_button.isChecked():
            new_location = self._current_location()
            if previous_location and previous_location != new_location:
                self._turn_off_led(previous_location)
            self._apply_led_state()

    def enter_edit_mode(self):
        self.set_edit_mode(True)
        self.part_info_editors["part_number"].setFocus()

    def set_edit_mode(self, enabled):
        self.edit_mode = enabled
        for editor in self.part_info_editors.values():
            self._set_editor_readonly(editor, not enabled)
        for editor in self.metadata_editors.values():
            self._set_editor_readonly(editor, not enabled)
        self._set_editor_readonly(self.description_value, not enabled)
        self.save_button.setVisible(enabled)
        self.edit_button.setVisible(not enabled)

    def save_changes(self):
        updated_component = self._collect_component_data()
        if updated_component is None:
            return

        component_index = self._find_component_index()
        if component_index < 0:
            QMessageBox.critical(self, "Save Failed", "Could not locate this component in the catalogue.")
            return

        try:
            self.backend.edit_component(component_index, updated_component)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            return

        self.source_component = self.backend.get_all_components()[component_index]
        self.populate_from_component(self.source_component)
        self.saved.emit()

    def toggle_highlight(self, checked):
        if checked and not self._has_valid_location():
            QMessageBox.warning(self, "Missing Location", "This component does not have a valid storage location.")
            self.highlight_button.blockSignals(True)
            self.highlight_button.setChecked(False)
            self.highlight_button.blockSignals(False)
            return
        if checked and not self._supports_led_location():
            QMessageBox.information(self, "Highlight Unavailable", "Highlight is only available for vial locations on the LED grid.")
            self.highlight_button.blockSignals(True)
            self.highlight_button.setChecked(False)
            self.highlight_button.blockSignals(False)
            return
        self._apply_led_state()

    def checkout_component(self):
        if self.edit_mode:
            QMessageBox.warning(self, "Finish Editing", "Save your changes before checking out this component.")
            return

        part_number = self.part_info_editors["part_number"].text().strip()
        if not part_number:
            QMessageBox.warning(self, "Missing Part Number", "This component does not have a valid part number.")
            return

        quantity_dialog = QuantityPromptDialog(part_number, self)
        if quantity_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        result = self.backend.checkout(part_number, quantity_dialog.quantity())
        if not result.get("success"):
            QMessageBox.warning(self, "Checkout Failed", result.get("message", "Checkout failed."))
            return

        location = str(result.get("location") or "").strip()
        self._reload_component_from_backend()

        if location and location.upper() != "N/A":
            self._turn_on_led(location)

            grab_dialog = CheckoutActionDialog(
                "Grab Part",
                f"{result['message']}\n\nGrab the part from location {location}, then press OK.",
                "Part Grabbed",
                self,
            )
            if grab_dialog.exec() != QDialog.DialogCode.Accepted:
                self._restore_led_state_after_checkout(location)
                return

            return_dialog = CheckoutActionDialog(
                "Return Components",
                f"Return the remaining components to location {location}, then press OK.",
                "Components Returned",
                self,
            )
            return_accepted = return_dialog.exec() == QDialog.DialogCode.Accepted
            self._restore_led_state_after_checkout(location)
            if return_accepted:
                QMessageBox.information(self, "Checkout Complete", result["message"])
        else:
            QMessageBox.information(self, "Checkout Complete", result["message"])

        self.saved.emit()

    def _collect_component_data(self):
        part_number = self.part_info_editors["part_number"].text().strip()
        manufacturer_number = self.part_info_editors["manufacturer_number"].text().strip()
        if not part_number and not manufacturer_number:
            QMessageBox.warning(self, "Missing Identifier", "Part number or manufacturer number is required.")
            return None

        count_text = self.part_info_editors["count"].text().strip()
        try:
            count = int(count_text)
        except ValueError:
            QMessageBox.warning(self, "Invalid Count", "Count must be an integer.")
            return None

        low_stock_text = self.metadata_editors["low_stock"].text().strip()
        if low_stock_text and low_stock_text != "N/A":
            try:
                low_stock = int(low_stock_text)
            except ValueError:
                QMessageBox.warning(self, "Invalid Low Stock", "Low Stock must be an integer or N/A.")
                return None
        else:
            low_stock = "N/A"

        return {
            "part_info": {
                "part_number": part_number or manufacturer_number,
                "manufacturer_number": manufacturer_number or part_number,
                "location": self._normalized_text(self.part_info_editors["location"].text()),
                "count": count,
                "type": self._normalized_text(self.part_info_editors["type"].text()),
            },
            "metadata": {
                "price": self._normalized_text(self.metadata_editors["price"].text()),
                "low_stock": low_stock,
                "description": self._normalized_text(self.description_value.toPlainText()),
                "photo_url": self._normalized_text(self.metadata_editors["photo_url"].text()),
                "datasheet_url": self._normalized_text(self.metadata_editors["datasheet_url"].text()),
                "product_url": self._normalized_text(self.metadata_editors["product_url"].text()),
                "in_use": self._normalized_text(self.metadata_editors["in_use"].text()),
            },
        }

    def _normalized_text(self, value):
        text = str(value).strip()
        return text if text else "N/A"

    def _find_component_index(self):
        for index, component in enumerate(self.backend.get_all_components()):
            if component is self.source_component:
                return index

        part_number = self.source_component.get("part_info", {}).get("part_number", "").strip().lower()
        manufacturer_number = self.source_component.get("part_info", {}).get("manufacturer_number", "").strip().lower()
        for index, component in enumerate(self.backend.get_all_components()):
            part_info = component.get("part_info", {})
            if (
                part_info.get("part_number", "").strip().lower() == part_number
                and part_info.get("manufacturer_number", "").strip().lower() == manufacturer_number
            ):
                return index
        return -1

    def refresh_link_buttons(self):
        datasheet_url = self.metadata_editors["datasheet_url"].text().strip()
        product_url = self.metadata_editors["product_url"].text().strip()
        self.datasheet_button.setVisible(bool(datasheet_url and datasheet_url != "N/A"))
        self.product_button.setVisible(bool(product_url and product_url != "N/A"))

    def _open_url_field(self, field_name):
        field = self.metadata_editors.get(field_name)
        if field is None:
            return
        url = field.text().strip()
        if url and url != "N/A":
            webbrowser.open(url)

    def _set_editor_readonly(self, editor, readonly):
        if isinstance(editor, QTextEdit):
            editor.setReadOnly(readonly)
        else:
            editor.setReadOnly(readonly)
        editor.setProperty("detailsReadonly", readonly)
        editor.style().unpolish(editor)
        editor.style().polish(editor)
        editor.update()

    def _current_location(self):
        return str(self.component.get("part_info", {}).get("location", "")).strip()

    def _has_valid_location(self):
        location = self._current_location()
        return bool(location and location.upper() != "N/A")

    def _supports_led_location(self):
        location = self._current_location()
        if not location or location.upper() == "N/A":
            return False
        row_part = "".join(filter(str.isdigit, location))
        col_part = "".join(filter(str.isalpha, location))
        return bool(row_part and len(col_part) == 1)

    def _turn_on_led(self, location):
        if self.led_controller is None or not location or location.upper() == "N/A":
            return
        self.led_controller.set_led_on(location, 0, 255, 0)
        self.highlight_location = location

    def _turn_off_led(self, location):
        if self.led_controller is None or not location or location.upper() == "N/A":
            return
        self.led_controller.turn_off_led(location)
        if self.highlight_location == location:
            self.highlight_location = None

    def _apply_led_state(self):
        current_location = self._current_location()
        if self.highlight_button.isChecked() and self._has_valid_location():
            if self.highlight_location and self.highlight_location != current_location:
                self._turn_off_led(self.highlight_location)
            self._turn_on_led(current_location)
            return

        if self.highlight_location:
            self._turn_off_led(self.highlight_location)

    def _restore_led_state_after_checkout(self, checkout_location):
        if self.highlight_button.isChecked() and self._has_valid_location():
            self._turn_on_led(self._current_location())
        else:
            self._turn_off_led(checkout_location)

    def _reload_component_from_backend(self):
        component_index = self._find_component_index()
        if component_index >= 0:
            self.source_component = self.backend.get_all_components()[component_index]
            self.populate_from_component(self.source_component)

    def accept(self):
        self._turn_off_led(self.highlight_location)
        super().accept()

    def reject(self):
        self._turn_off_led(self.highlight_location)
        super().reject()


class ComponentTable(QTableWidget):
    deleteRequested = pyqtSignal()

    COLUMNS = (
        "Part Number",
        "Manufacturer Number",
        "Location",
        "Count",
        "Type",
        "Low Stock",
        "In Use",
    )

    def __init__(self):
        super().__init__(0, len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.verticalHeader().setVisible(False)
        self.viewport().setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f5f7f8"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#20242b"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#20242b"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#d8eee8"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#20242b"))
        palette.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
        self.setPalette(palette)
        self.viewport().setPalette(palette)

        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

    def set_components(self, components):
        self.setSortingEnabled(False)
        self.setRowCount(len(components))

        for row, component in enumerate(components):
            part_info = component.get("part_info", {})
            metadata = component.get("metadata", {})
            values = (
                part_info.get("part_number", "N/A"),
                part_info.get("manufacturer_number", "N/A"),
                part_info.get("location", "N/A"),
                part_info.get("count", "N/A"),
                part_info.get("type", "N/A"),
                metadata.get("low_stock", "N/A"),
                metadata.get("in_use", "N/A"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, component)
                if column == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.setItem(row, column, item)

        self.setSortingEnabled(True)

    def component_for_row(self, row):
        item = self.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def selected_component(self):
        row = self.currentRow()
        if row < 0:
            return None
        return self.component_for_row(row)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.deleteRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


def run_preview(backend, digikey_api=None):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(backend, digikey_api)
    window.show()
    return app.exec()

