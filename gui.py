# gui.py
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QPushButton,
                             QLabel, QTabWidget, QTextEdit, QHBoxLayout, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from logic import ConfigManager, JoystickMonitor, ResetWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LMU Thrustmaster Reset Tool")
        self.resize(450, 320)

        # Initialize Logic
        self.config = ConfigManager()
        self.monitor = JoystickMonitor(self.config)
        self.reset_worker = None

        # Setup UI
        self.setup_ui()

        # Connect Signals
        self.monitor.status_update.connect(self.update_status)
        self.monitor.binding_complete.connect(self.on_binding_complete)
        self.monitor.button_triggered.connect(self.start_reset_sequence)

        # Start Background Thread
        self.monitor.start()

    def setup_ui(self):
        """Builds the widgets and layouts."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # --- Tab 1: Dashboard ---
        self.tab_dashboard = QWidget()
        dash_layout = QVBoxLayout(self.tab_dashboard)

        # Header
        self.lbl_header = QLabel("Wheel Status")
        self.lbl_header.setObjectName("Header")
        self.lbl_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dash_layout.addWidget(self.lbl_header)

        # Status Text
        self.lbl_status = QLabel("Initializing...")
        self.lbl_status.setObjectName("Status")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dash_layout.addWidget(self.lbl_status)

        # Reset Button (Manual)
        self.btn_reset = QPushButton("FORCE RESET NOW")
        self.btn_reset.setObjectName("ResetBtn")
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self.start_reset_sequence)
        dash_layout.addWidget(self.btn_reset)

        dash_layout.addStretch()
        self.tabs.addTab(self.tab_dashboard, "🎮 Dashboard")

        # --- Tab 2: Settings ---
        self.tab_settings = QWidget()
        settings_layout = QVBoxLayout(self.tab_settings)

        self.lbl_bind_info = QLabel("Click below, then press a button on your wheel.")
        self.lbl_bind_info.setWordWrap(True)
        self.lbl_bind_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_layout.addWidget(self.lbl_bind_info)

        self.btn_bind = QPushButton("Bind Wheel Button")
        self.btn_bind.setObjectName("BindBtn")
        self.btn_bind.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bind.clicked.connect(self.enable_bind_mode)
        settings_layout.addWidget(self.btn_bind)

        self.lbl_current_bind = QLabel()
        self.update_bind_label()
        self.lbl_current_bind.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_layout.addWidget(self.lbl_current_bind)

        settings_layout.addStretch()
        self.tabs.addTab(self.tab_settings, "⚙️ Settings")

        # --- Tab 3: Info ---
        self.tab_info = QWidget()
        info_layout = QVBoxLayout(self.tab_info)

        info_text = """
        <b>How to Fix Force Feedback in Le Mans Ultimate:</b>
        <br><br>
        1. <b>Run this App:</b> Keep it running in the background.
        <br>
        2. <b>The Problem:</b> When FFB dies, the USB driver often hangs.
        <br>
        3. <b>Step 1 (Hardware):</b> Press your bound button on the wheel (or click Reset in this app). This restarts the USB driver. You will hear the USB disconnect sound.
        <br>
        4. <b>Step 2 (Game):</b> Assign a button in LMU Settings called "Reset FFB". Press that button <i>after</i> the wheel reconnects.
        """
        self.txt_info = QLabel(info_text)
        self.txt_info.setWordWrap(True)
        self.txt_info.setTextFormat(Qt.TextFormat.RichText)
        self.txt_info.setAlignment(Qt.AlignmentFlag.AlignTop)
        info_layout.addWidget(self.txt_info)

        self.tabs.addTab(self.tab_info, "ℹ️ Help")

    def update_bind_label(self):
        if self.config.bound_button is not None:
            self.lbl_current_bind.setText(f"Current Binding: Button {self.config.bound_button}")
        else:
            self.lbl_current_bind.setText("Current Binding: None")

    @pyqtSlot(str)
    def update_status(self, text):
        self.lbl_status.setText(text)

    def enable_bind_mode(self):
        self.lbl_bind_info.setText("⏳ Waiting for button press on wheel...")
        self.btn_bind.setEnabled(False)
        self.monitor.set_binding_mode(True)

    @pyqtSlot(int)
    def on_binding_complete(self, btn_index):
        self.lbl_bind_info.setText("✅ Button bound successfully!")
        self.btn_bind.setEnabled(True)
        self.update_bind_label()

    def start_reset_sequence(self):
        """Starts the Reset Sequence cleanly."""
        if self.reset_worker and self.reset_worker.isRunning():
            return

        self.update_status("🛑 Pausing Monitor for Reset...")
        self.btn_reset.setEnabled(False)

        # 1. PAUSE Monitoring (Releases Pygame handle)
        self.monitor.pause()

        # 2. Schedule the reset execution slightly later to ensure lock is released
        QTimer.singleShot(200, self._execute_reset)

    def _execute_reset(self):
        self.update_status("🔄 Resetting USB Driver...")
        self.reset_worker = ResetWorker()
        self.reset_worker.finished.connect(self.on_reset_finished)
        self.reset_worker.start()

    @pyqtSlot(str)
    def on_reset_finished(self, message):
        self.update_status(message)
        self.btn_reset.setEnabled(True)

        # 3. RESUME Monitoring (Re-inits Pygame)
        # We give Windows a second to settle the new USB ID before trying to grab it
        QTimer.singleShot(1000, self.monitor.resume)

    def closeEvent(self, event):
        self.monitor.stop()
        event.accept()