import os
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QLabel,
                             QFrame, QProgressBar, QTableWidget, QTableWidgetItem,
                             QHeaderView, QCheckBox, QMenu, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QCursor
import threading


class SearchThread(QThread):
    progress_updated = pyqtSignal(int, int, int)
    result_found = pyqtSignal(dict, int)
    search_finished = pyqtSignal(int, float)
    search_error = pyqtSignal(str)

    def __init__(self, search_term, directory, file_extensions, exclude_patterns, case_sensitive):
        super().__init__()
        self.search_term = search_term
        self.directory = directory
        self.file_extensions = file_extensions
        self.exclude_patterns = exclude_patterns
        self.case_sensitive = case_sensitive
        self.is_running = True

    def run(self):
        try:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            pattern = re.compile(re.escape(self.search_term), flags)

            all_files = []
            exclude_dirs = set(self.exclude_patterns)

            for root, dirs, files in os.walk(self.directory):
                if not self.is_running:
                    self.search_finished.emit(0, 0)
                    return
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for file in files:
                    if not self.is_running:
                        self.search_finished.emit(0, 0)
                        return
                    file_path = Path(root) / file
                    if self.file_extensions:
                        if file_path.suffix.lower() not in [ext.lower() for ext in self.file_extensions]:
                            continue
                    all_files.append(file_path)

            total = len(all_files)
            if total == 0:
                self.search_finished.emit(0, 0)
                return

            start_time = time.time()
            found_count = 0
            lock = threading.Lock()

            def search_file(fp):
                nonlocal found_count
                if not self.is_running:
                    return False
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if not self.is_running:
                                return False
                            if pattern.search(line):
                                result = {'path': str(fp), 'line': line_num, 'content': line.strip()}
                                with lock:
                                    found_count += 1
                                    count = found_count
                                self.result_found.emit(result, count)
                                return True
                except:
                    pass
                return False

            processed = 0
            futures = []
            with ThreadPoolExecutor(max_workers=8) as executor:
                for fp in all_files:
                    if not self.is_running:
                        break
                    future = executor.submit(search_file, fp)
                    futures.append(future)
                
                for future in as_completed(futures):
                    if not self.is_running:
                        break
                    processed += 1
                    progress = int((processed / total) * 100)
                    self.progress_updated.emit(processed, total, progress)

            elapsed = time.time() - start_time
            self.search_finished.emit(found_count, elapsed)

        except Exception as e:
            self.search_error.emit(str(e))

    def stop(self):
        self.is_running = False


class ModernSearchApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.search_thread = None
        self.results = []
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("文件搜索工具-lx")
        self.setMinimumSize(1100, 770)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.setStyleSheet("""
        QMainWindow {
            background: #1E1E2E;
        }
        * {
            font-family: 'Microsoft YaHei UI', 'Segoe UI', sans-serif;
        }
        """)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(16)

        header = self.create_header()
        main_layout.addWidget(header)

        search_panel = self.create_search_panel()
        main_layout.addWidget(search_panel)

        results_area = self.create_results_area()
        main_layout.addWidget(results_area, 1)

    def create_header(self):
        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 12)

        title_label = QLabel("FileSearch")
        title_font = QFont("Microsoft YaHei UI", 26, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #E0E0E0;")

        version_label = QLabel("v1.0")
        version_label.setFont(QFont("Consolas", 11))
        version_label.setStyleSheet("color: #6B6B7B;")

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(version_label)

        return header_frame

    def create_search_panel(self):
        panel = QFrame()
        panel.setObjectName("searchPanel")
        panel.setStyleSheet("""
            #searchPanel {
                background: #2B2B3B;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setSpacing(16)

        path_row = self.create_path_row()
        layout.addWidget(path_row)

        keyword_row = self.create_keyword_row()
        layout.addWidget(keyword_row)

        file_types_row = self.create_file_types_row()
        layout.addWidget(file_types_row)

        exclude_row = self.create_exclude_row()
        layout.addWidget(exclude_row)

        control_row = self.create_control_row()
        layout.addWidget(control_row)

        return panel

    def create_path_row(self):
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)

        path_label = QLabel("搜索路径")
        path_label.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.Medium))
        path_label.setStyleSheet("color: #E0E0E0;")

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("选择要搜索的目录...")
        self.path_input.setText(os.path.expanduser("~"))
        self.path_input.setStyleSheet("""
            QLineEdit {
                background: #1E1E2E;
                color: #E0E0E0;
                border: none;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 13px;
            }
            QLineEdit:focus {
                background: #363649;
            }
            QLineEdit::placeholder {
                color: #6B6B7B;
            }
        """)

        browse_btn = QPushButton("浏览")
        browse_btn.setFont(QFont("Microsoft YaHei UI", 11))
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.setStyleSheet("""
            QPushButton {
                background: #5865F2;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 20px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #4752C4;
            }
            QPushButton:pressed {
                background: #3C45A5;
            }
        """)
        browse_btn.clicked.connect(self.browse_directory)

        row_layout.addWidget(path_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignCenter)
        row_layout.addWidget(self.path_input, 1)
        row_layout.addWidget(browse_btn, 0, Qt.AlignmentFlag.AlignLeft)

        return row

    def create_keyword_row(self):
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)

        keyword_label = QLabel("关键词")
        keyword_label.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.Medium))
        keyword_label.setStyleSheet("color: #E0E0E0;")

        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("输入要搜索的关键词，按回车开始...")
        self.keyword_input.returnPressed.connect(self.start_search)
        self.keyword_input.setStyleSheet("""
            QLineEdit {
                background: #1E1E2E;
                color: #E0E0E0;
                border: none;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 13px;
            }
            QLineEdit:focus {
                background: #363649;
            }
            QLineEdit::placeholder {
                color: #6B6B7B;
            }
        """)

        self.case_checkbox = QCheckBox("区分大小写")
        # ===================== 修复这里 =====================
        self.case_checkbox.setStyleSheet("""
            QCheckBox {
                color: #B0B0B0;
                spacing: 8px;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #5865F2;
                background: transparent;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #5865F2;
                background: #5865F2;
            }
            QCheckBox:hover {
                color: #E0E0E0;
            }
        """)
        # ====================================================

        row_layout.addWidget(keyword_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignCenter)
        row_layout.addWidget(self.keyword_input, 1)
        row_layout.addWidget(self.case_checkbox, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignCenter)

        return row

    def create_file_types_row(self):
        row = QFrame()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        label_row = QHBoxLayout()
        file_types_label = QLabel("文件类型")
        file_types_label.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.Medium))
        file_types_label.setStyleSheet("color: #E0E0E0;")
        label_row.addWidget(file_types_label)
        label_row.addStretch()

        checkboxes_row = QHBoxLayout()
        checkboxes_row.setSpacing(12)

        self.file_type_checks = {}
        file_types = ['.py', '.js', '.ts', '.txt', '.md', '.html', '.css', '.json']
        for ext in file_types:
            cb = QCheckBox(ext)
            cb.setFont(QFont("Consolas", 11))
            # ===================== 修复这里 =====================
            cb.setStyleSheet("""
                QCheckBox {
                    color: #B0B0B0;
                    spacing: 6px;
                    font-family: 'Consolas', monospace;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 4px;
                    border: 2px solid #5865F2;
                    background: transparent;
                }
                QCheckBox::indicator:checked {
                    border: 2px solid #5865F2;
                    background: #5865F2;
                }
                QCheckBox:hover {
                    color: #E0E0E0;
                }
            """)
            # ====================================================
            self.file_type_checks[ext] = cb
            checkboxes_row.addWidget(cb)

        checkboxes_row.addStretch()

        custom_row = QHBoxLayout()
        custom_label = QLabel("自定义:")
        custom_label.setStyleSheet("color: #6B6B7B; font-size: 11px;")
        self.custom_file_type_input = QLineEdit()
        self.custom_file_type_input.setPlaceholderText(".java|.go|.rs")
        self.custom_file_type_input.setMaximumWidth(220)
        self.custom_file_type_input.setStyleSheet("""
            QLineEdit {
                background: #1E1E2E;
                color: #E0E0E0;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                font-family: 'Consolas', monospace;
            }
            QLineEdit:focus {
                background: #363649;
            }
            QLineEdit::placeholder {
                color: #4B4B5B;
            }
        """)
        custom_hint = QLabel("(用 | 分割)")
        custom_hint.setStyleSheet("color: #4B4B5B; font-size: 10px;")

        custom_row.addWidget(custom_label)
        custom_row.addWidget(self.custom_file_type_input)
        custom_row.addWidget(custom_hint)
        custom_row.addStretch()

        row_layout.addLayout(label_row)
        row_layout.addLayout(checkboxes_row)
        row_layout.addLayout(custom_row)

        return row

    def create_exclude_row(self):
        row = QFrame()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        label_row = QHBoxLayout()
        exclude_label = QLabel("排除目录")
        exclude_label.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.Medium))
        exclude_label.setStyleSheet("color: #E0E0E0;")
        label_row.addWidget(exclude_label)
        label_row.addStretch()

        checkboxes_row = QHBoxLayout()
        checkboxes_row.setSpacing(12)

        self.exclude_checks = {}
        exclude_patterns = ['.git', '__pycache__', '.vscode', '.idea', 'node_modules']
        for pattern in exclude_patterns:
            cb = QCheckBox(pattern)
            cb.setChecked(True)
            cb.setFont(QFont("Consolas", 11))
            # ===================== 修复这里 =====================
            cb.setStyleSheet("""
                QCheckBox {
                    color: #B0B0B0;
                    spacing: 6px;
                    font-family: 'Consolas', monospace;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 4px;
                    border: 2px solid #5865F2;
                    background: transparent;
                }
                QCheckBox::indicator:checked {
                    border: 2px solid #5865F2;
                    background: #5865F2;
                }
                QCheckBox:hover {
                    color: #E0E0E0;
                }
            """)
            # ====================================================
            self.exclude_checks[pattern] = cb
            checkboxes_row.addWidget(cb)

        checkboxes_row.addStretch()

        custom_row = QHBoxLayout()
        custom_label = QLabel("自定义:")
        custom_label.setStyleSheet("color: #6B6B7B; font-size: 11px;")
        self.custom_exclude_input = QLineEdit()
        self.custom_exclude_input.setPlaceholderText("log|tmp|bak")
        self.custom_exclude_input.setMaximumWidth(220)
        self.custom_exclude_input.setStyleSheet("""
            QLineEdit {
                background: #1E1E2E;
                color: #E0E0E0;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                font-family: 'Consolas', monospace;
            }
            QLineEdit:focus {
                background: #363649;
            }
            QLineEdit::placeholder {
                color: #4B4B5B;
            }
        """)
        custom_hint = QLabel("(用 | 分割)")
        custom_hint.setStyleSheet("color: #4B4B5B; font-size: 10px;")

        custom_row.addWidget(custom_label)
        custom_row.addWidget(self.custom_exclude_input)
        custom_row.addWidget(custom_hint)
        custom_row.addStretch()

        row_layout.addLayout(label_row)
        row_layout.addLayout(checkboxes_row)
        row_layout.addLayout(custom_row)

        return row

    def create_control_row(self):
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 6, 0, 0)

        btn_container = QHBoxLayout()
        btn_container.setSpacing(8)

        self.search_btn = QPushButton("开始搜索")
        self.search_btn.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.Medium))
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: #5865F2;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 28px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #4752C4;
            }
            QPushButton:pressed {
                background: #3C45A5;
            }
        """)
        self.search_btn.clicked.connect(self.start_search)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setFont(QFont("Microsoft YaHei UI", 11))
        self.stop_btn.setEnabled(False)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #3B3B4F;
                color: #B0B0B0;
                border: none;
                border-radius: 10px;
                padding: 12px 28px;
            }
            QPushButton:hover {
                background: #4B4B5F;
            }
            QPushButton:enabled {
                background: #F04747;
                color: white;
            }
            QPushButton:enabled:hover {
                background: #D13939;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_search)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setFont(QFont("Microsoft YaHei UI", 11))
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #3B3B4F;
                color: #B0B0B0;
                border: none;
                border-radius: 10px;
                padding: 12px 28px;
            }
            QPushButton:hover {
                background: #4B4B5F;
                color: #E0E0E0;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_results)

        btn_container.addWidget(self.search_btn)
        btn_container.addWidget(self.stop_btn)
        btn_container.addWidget(self.clear_btn)

        status_container = QHBoxLayout()
        status_container.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_container.setSpacing(16)

        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont("Microsoft YaHei UI", 11))
        self.status_label.setStyleSheet("color: #5865F2;")

        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(180)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #1E1E2E;
                border: none;
                border-radius: 4px;
                height: 6px;
            }
            QProgressBar::chunk {
                background: #5865F2;
                border-radius: 4px;
            }
        """)

        self.progress_label = QLabel("0%")
        self.progress_label.setFont(QFont("Consolas", 10))
        self.progress_label.setStyleSheet("color: #6B6B7B;")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)

        status_container.addWidget(self.status_label)
        status_container.addLayout(progress_layout)

        row_layout.addLayout(btn_container)
        row_layout.addStretch()
        row_layout.addLayout(status_container)

        return row

    def create_results_area(self):
        container = QFrame()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 12, 0, 0)

        self.results_label = QLabel("搜索结果 (0)")
        self.results_label.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.Medium))
        self.results_label.setStyleSheet("color: #E0E0E0;")

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(['#', '文件路径', '行号', '匹配内容'])

        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.results_table.setStyleSheet("""
            QTableWidget {
                background: #2B2B3B;
                color: #E0E0E0;
                border: none;
                border-radius: 12px;
                gridline-color: #3B3B4F;
                selection-background-color: #5865F2;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 10px 6px;
                border-bottom: 1px solid #3B3B4F;
                background: #2B2B3B;
            }
            QTableWidget::item:alternate {
                background: #363649;
            }
            QTableWidget::item:selected {
                background: #5865F2;
            }
            QHeaderView::section {
                background: #363649;
                color: #B0B0B0;
                padding: 12px 6px;
                border: none;
                font-weight: 500;
                font-size: 12px;
            }
        """)

        self.results_table.setAlternatingRowColors(True)
        self.results_table.setShowGrid(False)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self.show_context_menu)
        self.results_table.itemDoubleClicked.connect(self.open_file)

        container_layout.addWidget(self.results_label)
        container_layout.addWidget(self.results_table)

        return container

    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "选择目录", self.path_input.text()
        )
        if directory:
            self.path_input.setText(directory)

    def get_selected_file_types(self):
        types = [ext for ext, cb in self.file_type_checks.items() if cb.isChecked()]
        custom = self.custom_file_type_input.text().strip()
        if custom:
            for ext in custom.split('|'):
                ext = ext.strip()
                if ext:
                    if not ext.startswith('.'):
                        ext = '.' + ext
                    types.append(ext)
        return types if types else None

    def get_excluded_patterns(self):
        patterns = [p for p, cb in self.exclude_checks.items() if cb.isChecked()]
        custom = self.custom_exclude_input.text().strip()
        if custom:
            patterns.extend([p.strip() for p in custom.split('|') if p.strip()])
        return patterns

    def start_search(self):
        directory = self.path_input.text().strip()
        keyword = self.keyword_input.text().strip()

        if not directory:
            QMessageBox.warning(self, "提示", "请选择搜索目录")
            return

        if not os.path.exists(directory):
            QMessageBox.warning(self, "提示", f"目录不存在:\n{directory}")
            return

        if not keyword:
            QMessageBox.warning(self, "提示", "请输入搜索关键词")
            return

        self.search_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("搜索中...")
        self.status_label.setStyleSheet("color: #F04747;")
        self.clear_results()

        file_types = self.get_selected_file_types()
        exclude_patterns = self.get_excluded_patterns()

        self.search_thread = SearchThread(
            keyword, directory, file_types, exclude_patterns, self.case_checkbox.isChecked()
        )
        self.search_thread.progress_updated.connect(self.update_progress)
        self.search_thread.result_found.connect(self.add_result)
        self.search_thread.search_finished.connect(self.search_complete)
        self.search_thread.search_error.connect(self.search_error)
        self.search_thread.start()

    def stop_search(self):
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.stop()
            self.status_label.setText("正在停止...")
            self.status_label.setStyleSheet("color: #F04747;")

    def update_progress(self, processed, total, percentage):
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(f"{percentage}%")

    def add_result(self, result, count):
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        content = result['content']
        if len(content) > 120:
            content = content[:120] + "..."

        self.results_table.setItem(row, 0, QTableWidgetItem(str(count)))
        self.results_table.setItem(row, 1, QTableWidgetItem(result['path']))
        self.results_table.setItem(row, 2, QTableWidgetItem(str(result['line'])))
        self.results_table.setItem(row, 3, QTableWidgetItem(content))

        self.results_label.setText(f"搜索结果 ({count})")
        self.results_table.scrollToBottom()

    def search_complete(self, result_count, elapsed):
        self.search_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(100)
        self.progress_label.setText("100%")

        if result_count > 0:
            self.status_label.setText(f"完成 | 找到 {result_count} 个匹配 | 耗时 {elapsed:.2f}s")
            self.status_label.setStyleSheet("color: #43B581;")
        else:
            self.status_label.setText("未找到匹配结果")
            self.status_label.setStyleSheet("color: #6B6B7B;")

    def search_error(self, error_msg):
        self.search_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText(f"错误: {error_msg}")
        self.status_label.setStyleSheet("color: #F04747;")
        QMessageBox.critical(self, "错误", f"搜索出错:\n{error_msg}")

    def clear_results(self):
        self.results_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.progress_label.setText("0%")
        self.results_label.setText("搜索结果 (0)")

    def show_context_menu(self, position):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: rgba(43, 43, 59, 0.95);
                border: 1px solid #3B3B4F;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 10px 20px;
                color: #E0E0E0;
                font-size: 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #5865F2;
            }
        """)

        copy_path_action = QAction("复制文件路径", self)
        copy_path_action.triggered.connect(self.copy_file_path)

        copy_line_action = QAction("复制行号", self)
        copy_line_action.triggered.connect(self.copy_line_number)

        copy_content_action = QAction("复制内容", self)
        copy_content_action.triggered.connect(self.copy_content)

        copy_all_action = QAction("复制整行", self)
        copy_all_action.triggered.connect(self.copy_full_row)

        menu.addAction(copy_path_action)
        menu.addAction(copy_line_action)
        menu.addAction(copy_content_action)
        menu.addSeparator()
        menu.addAction(copy_all_action)

        menu.exec(self.results_table.viewport().mapToGlobal(position))

    def copy_file_path(self):
        row = self.results_table.currentRow()
        if row >= 0:
            path = self.results_table.item(row, 1).text()
            QApplication.clipboard().setText(path)

    def copy_line_number(self):
        row = self.results_table.currentRow()
        if row >= 0:
            line = self.results_table.item(row, 2).text()
            QApplication.clipboard().setText(line)

    def copy_content(self):
        row = self.results_table.currentRow()
        if row >= 0:
            content = self.results_table.item(row, 3).text()
            QApplication.clipboard().setText(content)

    def copy_full_row(self):
        row = self.results_table.currentRow()
        if row >= 0:
            path = self.results_table.item(row, 1).text()
            line = self.results_table.item(row, 2).text()
            content = self.results_table.item(row, 3).text()
            QApplication.clipboard().setText(f"{path} | {line} | {content}")

    def open_file(self, item):
        row = item.row()
        if row >= 0:
            file_path = self.results_table.item(row, 1).text()
            try:
                os.startfile(file_path)
            except Exception:
                pass


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = ModernSearchApp()
    window.show()
    sys.exit(app.exec())
