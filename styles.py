# styles.py

DARK_THEME = """
QMainWindow {
    background-color: #2b2b2b;
}

QLabel {
    color: #e0e0e0;
    font-size: 14px;
    font-family: 'Segoe UI', sans-serif;
}

QLabel#Header {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
}

QLabel#Status {
    font-size: 13px;
    color: #aaaaaa;
    padding: 5px;
}

QPushButton {
    background-color: #3d3d3d;
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 6px;
    padding: 10px;
    font-size: 14px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #4d4d4d;
    border: 1px solid #007acc;
}

QPushButton:pressed {
    background-color: #007acc;
    border: 1px solid #005c99;
}

/* Specific styling for the Big Reset Button */
QPushButton#ResetBtn {
    background-color: #c0392b; /* Red */
    font-size: 16px;
}
QPushButton#ResetBtn:hover {
    background-color: #e74c3c;
}

/* Specific styling for the Bind Button */
QPushButton#BindBtn {
    background-color: #2980b9; /* Blue */
}
QPushButton#BindBtn:hover {
    background-color: #3498db;
}

QTabWidget::pane {
    border: 1px solid #444;
    background: #2b2b2b;
}

QTabBar::tab {
    background: #2b2b2b;
    color: #aaa;
    padding: 8px 20px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background: #3d3d3d;
    color: white;
    border-bottom: 2px solid #007acc;
}

QTextEdit {
    background-color: #1e1e1e;
    color: #cccccc;
    border: 1px solid #444;
    font-family: Consolas, monospace;
}
"""