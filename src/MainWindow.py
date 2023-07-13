import os

import PyQt5.QtWidgets as QtWidgets
from PyQt5 import QtGui, QtCore

__SCRIPT_PATH__, __SCRIPT_NAME__ = os.path.split(__file__)


def res(name):
    return os.path.join(__SCRIPT_PATH__, name)


class MainWindow(QtWidgets.QDialog):
    signal_queue_size = QtCore.pyqtSignal(int, name="queue_size")
    signal_id_update = QtCore.pyqtSignal(name="id_update")
    signal_status_update = QtCore.pyqtSignal(name="status_update")
    signal_color_image = QtCore.pyqtSignal(object, name="color_image")
    signal_event_snapshot = QtCore.pyqtSignal(object, name="event_snapshot")

    def __init__(self, args, controller, parent=None):
        super(MainWindow, self).__init__(parent)

        self.args = args

        self.controller = controller

        self.setWindowTitle("Sign Language Dataset Recorder")

        self.initUI()

        self.sig_queue_size = QtCore.pyqtSignal(int)
        self.signal_queue_size.connect(self.display_log)

        self.signal_id_update.connect(self.update_ids)
        self.signal_color_image.connect(self.display_realsense)
        self.signal_event_snapshot.connect(self.display_eventstream)
        self.signal_status_update.connect(self.update_status)

    def display_realsense(self, color_frame):
        self.rs_color_frame.setPixmap(QtGui.QPixmap.fromImage(color_frame))

    def display_eventstream(self, event_frame):
        self.event_frame.setPixmap(QtGui.QPixmap.fromImage(event_frame))

    def display_log(self, size):
        self.queue_state.setText("Write Queue Size = {}".format(size))

    def initUI(self, margin=30):
        self.rs_color_frame = QtWidgets.QLabel(self)

        self.event_frame = QtWidgets.QLabel(self)

        font = QtGui.QFont()
        font.setPointSize(18)

        if self.args.layout == "landscape":
            self.width = 860
            self.height = 640
            self.rs_color_frame.setGeometry(0, 0, 480, 270)
            self.event_frame.setGeometry(0, 320, 480, 300)
            self.setFixedSize(self.width, self.height)

            right_column_x = 480 + margin
        else:
            self.width = 1020
            self.height = 480
            self.rs_color_frame.setGeometry(0, 0, 270, 480)
            self.event_frame.setGeometry(320, 0, 300, 480)
            self.setFixedSize(self.width, self.height)

            right_column_x = 320 * 2 + margin

        self.status = QtWidgets.QLabel(self)
        self.status.setGeometry(right_column_x, 20, 250, 30)
        self.status.setText("Idle")
        self.status.setFont(font)

        self.queue_state = QtWidgets.QLabel(self)
        self.queue_state.setGeometry(right_column_x, 60, 300, 30)
        self.queue_state.setText("Write Queue Size = 0")
        self.queue_state.setFont(font)

        self.action_state = QtWidgets.QLabel(self)
        self.action_state.setGeometry(right_column_x, 100, 250, 30)
        self.action_state.setText("Current Action = 0")
        self.action_state.setFont(font)

        self.person_state = QtWidgets.QLabel(self)
        self.person_state.setGeometry(right_column_x, 140, 250, 30)
        self.person_state.setText("Current Person = 0")
        self.person_state.setFont(font)

        row_height = 80
        button_group_y = self.height - (3 * row_height) - 20
        button_width = (self.width - right_column_x - 2 * margin) // 2
        column_width = button_width + margin
        button_x = right_column_x

        self.btn_action_plus = QtWidgets.QPushButton(self)
        self.btn_action_plus.setText("A ++")
        self.btn_action_plus.setGeometry(button_x + column_width, button_group_y, button_width, 60)
        self.btn_action_plus.setFont(font)
        self.btn_action_plus.clicked.connect(self.btn_action_plus_click)

        self.btn_action_sub = QtWidgets.QPushButton(self)
        self.btn_action_sub.setText("A --")
        self.btn_action_sub.setGeometry(button_x, button_group_y, button_width, 60)
        self.btn_action_sub.setFont(font)
        self.btn_action_sub.clicked.connect(self.btn_action_sub_click)

        self.btn_person_plus = QtWidgets.QPushButton(self)
        self.btn_person_plus.setText("P ++")
        self.btn_person_plus.setGeometry(button_x + column_width, button_group_y + row_height, button_width, 60)
        self.btn_person_plus.setFont(font)
        self.btn_person_plus.clicked.connect(self.btn_person_plus_click)

        self.btn_person_sub = QtWidgets.QPushButton(self)
        self.btn_person_sub.setText("P --")
        self.btn_person_sub.setGeometry(button_x, button_group_y + row_height, button_width, 60)
        self.btn_person_sub.setFont(font)
        self.btn_person_sub.clicked.connect(self.btn_person_sub_click)

        self.btn_record = QtWidgets.QPushButton(self)
        self.btn_record.setText("Record")
        self.btn_record.setGeometry(button_x, button_group_y + row_height * 2, button_width, 60)
        self.btn_record.setFont(font)
        self.btn_record.clicked.connect(self.btn_record_click)

        self.btn_cancel = QtWidgets.QPushButton(self)
        self.btn_cancel.setText("Cancel")
        self.btn_cancel.setGeometry(
            QtCore.QRect(button_x + column_width, button_group_y + row_height * 2, button_width, 60))
        self.btn_cancel.setFont(font)
        self.btn_cancel.clicked.connect(self.btn_cancel_click)

        self.recording_indicator = QtWidgets.QPushButton(self)
        self.recording_indicator.setObjectName("recording_indicator")
        indicator_width = 256
        indicator_height = 64
        if self.args.layout == "landscape":
            self.recording_indicator.setGeometry((480 - indicator_width) // 2, (320 * 2 - indicator_height) // 2,
                                                 indicator_width, indicator_height)
        else:
            self.recording_indicator.setGeometry((320 * 2 - indicator_width) // 2, (480 - indicator_height) // 2,
                                                 indicator_width, indicator_height)
        self.recording_indicator.setIcon(QtGui.QIcon(res("recording.svg")))
        self.recording_indicator.setIconSize(self.recording_indicator.size())

        self.recording_indicator.hide()
        self.recording_indicator.setStyleSheet(
            "QPushButton#recording_indicator{"
            "   border-width: 0px;"
            "   border-style: none;"
            "   background-color: none;"
            "}")

        if not self.args.master:
            self.btn_action_plus.hide()
            self.btn_action_sub.hide()
            self.btn_person_plus.hide()
            self.btn_person_sub.hide()
            self.btn_record.hide()
            self.btn_cancel.hide()

    def btn_action_sub_click(self):
        if self.controller.aid < 1 or self.controller.is_recording:
            return

        self.controller.aid -= 1
        self.action_state.setText("Current Action = {}".format(self.controller.aid))

    def btn_action_plus_click(self):
        if self.controller.is_recording:
            return

        self.controller.aid += 1
        self.action_state.setText("Current Action = {}".format(self.controller.aid))

    def btn_person_sub_click(self):
        if self.controller.pid < 1 or self.controller.is_recording:
            return

        self.controller.pid -= 1
        self.person_state.setText("Current Person = {}".format(self.controller.pid))

    def btn_person_plus_click(self):
        if self.controller.is_recording:
            return

        self.controller.pid += 1
        self.person_state.setText("Current Person = {}".format(self.controller.pid))

    def btn_record_click(self):
        if self.controller.is_recording:
            print("=" * 20, "save button clicked")
            self.controller.set_stop()
            self.status.setText("Idle")
            self.btn_record.setText("Record")
        else:
            print("=" * 20, "record button clicked")
            self.controller.set_record()
            self.status.setText("Recording")
            self.btn_record.setText("Save")

    def update_ids(self):
        self.action_state.setText("Current Action = {}".format(self.controller.aid))
        self.person_state.setText("Current Person = {}".format(self.controller.pid))

    def update_status(self):
        if self.controller.is_recording:
            self.status.setText("Recording")
            self.recording_indicator.show()
        else:
            self.status.setText("Idle")
            self.recording_indicator.hide()

    def btn_cancel_click(self):
        if not self.controller.is_recording:
            return
        print("=" * 20, "cancel button clicked")
        self.controller.set_cancel()
        self.status.setText("Idle")
        self.btn_record.setText("Record")
