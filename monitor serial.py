import sys
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QHBoxLayout
)
from PyQt6.QtCore import QThread, pyqtSignal
from serial import Serial, SerialException
import time


class SerialReader(QThread):
    data_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, serial_port):
        super().__init__()
        self.serial = serial_port
        self._running = True

    def run(self):
        while self._running:
            try:
                if self.serial.in_waiting > 0:
                    data = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    if data:
                        self.data_received.emit(data)
                time.sleep(0.05)
            except SerialException as e:
                self.error_occurred.emit(f"Erro serial: {e}")
                break
            except Exception as e:
                self.error_occurred.emit(f"Erro inesperado: {e}")
                break

    def stop(self):
        self._running = False
        self.wait()


class SerialMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor Serial USB")
        self.setGeometry(100, 100, 600, 400)

        self.serial = None
        self.reader_thread = None

        self.init_ui()
        self.update_ports()

    def init_ui(self):
        layout = QVBoxLayout()

        self.port_combo = QComboBox()
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["300", "1200", "2400", "4800", "9600", "14400", "19200",
    "28800", "38400", "57600", "74880", "115200", "128000",
    "230400", "250000", "460800", "921600", "1000000", "2000000"])
        self.refresh_btn = QPushButton("🔄 Atualizar Portas")
        self.refresh_btn.clicked.connect(self.update_ports)

        self.connect_btn = QPushButton("🔌 Conectar")
        self.connect_btn.clicked.connect(self.toggle_connection)

        self.status_label = QLabel("Status: Desconectado")

        top_row = QHBoxLayout()
        top_row.addWidget(self.port_combo)
        top_row.addWidget(self.baud_combo)
        top_row.addWidget(self.refresh_btn)
        top_row.addWidget(self.connect_btn)

        self.console = QTextEdit()
        self.console.setReadOnly(True)

        layout.addLayout(top_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.console)

        self.setLayout(layout)

    def update_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(f"{port.device} - {port.description}")

    def toggle_connection(self):
        if self.serial and self.serial.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        try:
            selected = self.port_combo.currentText().split(" - ")[0]
            baud = int(self.baud_combo.currentText())

            self.serial = Serial(selected, baudrate=baud, timeout=0.2)
            self.serial.reset_input_buffer()

            self.reader_thread = SerialReader(self.serial)
            self.reader_thread.data_received.connect(self.console.append)
            self.reader_thread.error_occurred.connect(self.handle_error)
            self.reader_thread.start()

            self.status_label.setText(f"Status: Conectado ({selected} @ {baud}bps)")
            self.connect_btn.setText("❌ Desconectar")
        except Exception as e:
            self.status_label.setText(f"Erro ao conectar: {e}")
            self.console.append(str(e))

    def disconnect_serial(self):
        try:
            if self.reader_thread and self.reader_thread.isRunning():
                self.reader_thread.stop()
                self.reader_thread = None

            if self.serial:
                if self.serial.is_open:
                    self.serial.close()
                self.serial = None

            self.status_label.setText("Status: Desconectado")
            self.connect_btn.setText("🔌 Conectar")
        except Exception as e:
            self.console.append(f"[Erro ao desconectar]: {e}")

    def handle_error(self, message):
        self.console.append(f"[ERRO]: {message}")
        self.disconnect_serial()
    


if __name__ == '__main__':
    app = QApplication(sys.argv)
    monitor = SerialMonitor()
    monitor.show()
    sys.exit(app.exec())
