import sys
from sensor import RealSense

from PyQt5 import QtGui, QtCore
import PyQt5.QtWidgets as QtWidgets
from PyQt5.QtWidgets import QApplication

import time
import threading
import os


class MainWindow(QtWidgets.QDialog):

    signal_queue_size = QtCore.pyqtSignal(int, name="queue_size")
    signal_id_update = QtCore.pyqtSignal(name="id_update")
    signal_status_update = QtCore.pyqtSignal(name="status_update")
    signal_color_image = QtCore.pyqtSignal(object, name="color_image")
    signal_event_snapshot = QtCore.pyqtSignal(object, name="event_snapshot")

    def __init__(self, args, controller, parent=None, width = 820, height=720):
        super(MainWindow, self).__init__(parent)
        
        self.args = args
        
        self.controller = controller

        self.setWindowTitle('Sign Language Dataset Recorder')
        self.width = width
        self.height = height
        self.setFixedSize(self.width, self.height)

        self.initUI()
        
        self.sig_queue_size = QtCore.pyqtSignal(int)
        self.signal_queue_size.connect(self.display_log)
        
        self.signal_id_update.connect(self.update_ids)
        self.signal_color_image.connect(self.display_realsense)
        self.signal_event_snapshot.connect(self.display_eventstream)
        self.signal_status_update.connect(self.update_status)

        self.rs_color_frame = None
        self.event_frame = None
        
    def display_realsense(self, color_frame):
        self.rs_color_frame.setPixmap(QtGui.QPixmap.fromImage(color_frame))

    def display_eventstream(self, event_frame):
        self.event_frame.setPixmap(QtGui.QPixmap.fromImage(event_frame))

    def display_log(self, size):
        self.queue_state.setText('Write Queue Size = {}'.format(size))

    def initUI(self, margin=100):
        self.rs_color_frame = QtWidgets.QLabel(self)
        self.rs_color_frame.setGeometry(0, 60, 320, 480)
        
        self.event_frame = QtWidgets.QLabel(self)
        self.event_frame.setGeometry(320, 60, 320, 480)

        font = QtGui.QFont()
        font.setPointSize(18)

        self.status = QtWidgets.QLabel(self)
        self.status.setGeometry(50,20,250,30)
        self.status.setText('Idle')
        self.status.setFont(font)

        self.queue_state = QtWidgets.QLabel(self)
        self.queue_state.setGeometry(450,20,250,30)
        self.queue_state.setText('Write Queue Size = 0')
        self.queue_state.setFont(font)

        self.action_state = QtWidgets.QLabel(self)
        self.action_state.setGeometry(450,60,250,30)
        self.action_state.setText('Current Action = 0')
        self.action_state.setFont(font)

        self.person_state = QtWidgets.QLabel(self)
        self.person_state.setGeometry(450,100,250,30)
        self.person_state.setText('Current Person = 0')
        self.person_state.setFont(font)

        self.btn_action_plus = QtWidgets.QPushButton(self)
        self.btn_action_plus.setText('A ++')
        self.btn_action_plus.setGeometry(QtCore.QRect(600, 200, 100, 60))
        self.btn_action_plus.setFont(font)
        self.btn_action_plus.clicked.connect(self.btn_action_plus_click)

        self.btn_action_sub = QtWidgets.QPushButton(self)
        self.btn_action_sub.setText('A --')
        self.btn_action_sub.setGeometry(QtCore.QRect(450, 200, 100, 60))
        self.btn_action_sub.setFont(font)
        self.btn_action_sub.clicked.connect(self.btn_action_sub_click)

        self.btn_person_plus = QtWidgets.QPushButton(self)
        self.btn_person_plus.setText('P ++')
        self.btn_person_plus.setGeometry(QtCore.QRect(600, 300, 100, 60))
        self.btn_person_plus.setFont(font)
        self.btn_person_plus.clicked.connect(self.btn_person_plus_click)

        self.btn_person_sub = QtWidgets.QPushButton(self)
        self.btn_person_sub.setText('P --')
        self.btn_person_sub.setGeometry(QtCore.QRect(450, 300, 100, 60))
        self.btn_person_sub.setFont(font)
        self.btn_person_sub.clicked.connect(self.btn_person_sub_click)

        self.btn_record = QtWidgets.QPushButton(self)
        self.btn_record.setText('Record')
        self.btn_record.setGeometry(QtCore.QRect(100, self.height-100, 300, 60))
        self.btn_record.setFont(font)
        self.btn_record.clicked.connect(self.btn_record_click)

        self.btn_cancel = QtWidgets.QPushButton(self)
        self.btn_cancel.setText('Cancel')
        self.btn_cancel.setGeometry(QtCore.QRect(self.width-300-margin, self.height-margin, 300, 60))
        self.btn_cancel.setFont(font)
        self.btn_cancel.clicked.connect(self.btn_cancel_click)

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
        self.action_state.setText('Current Action = {}'.format(self.controller.aid))

    def btn_action_plus_click(self):
        if self.controller.is_recording:
            return

        self.controller.aid += 1
        self.action_state.setText('Current Action = {}'.format(self.controller.aid))

    def btn_person_sub_click(self):
        if self.controller.pid < 1 or self.controller.is_recording:
            return

        self.controller.pid -= 1
        self.person_state.setText('Current Person = {}'.format(self.controller.pid))

    def btn_person_plus_click(self):
        if self.controller.is_recording:
            return
            
        self.controller.pid += 1
        self.person_state.setText('Current Person = {}'.format(self.controller.pid))

    def btn_record_click(self):
        if self.controller.is_recording:
            self.controller.set_stop()
            self.status.setText('Idle')
            self.btn_record.setText('Record')
        else:
            self.controller.set_record()
            self.status.setText('Recording')
            self.btn_record.setText('Save')

    def update_ids(self):
        self.action_state.setText('Current Action = {}'.format(self.controller.aid))
        self.person_state.setText('Current Person = {}'.format(self.controller.pid))
    
    def update_status(self):
        if self.controller.is_recording:
            self.status.setText('Recording')
        else:
            self.status.setText('Idle')

    def btn_cancel_click(self):
        if not self.controller.is_recording:
            return
        
        self.controller.set_cancel()
        self.status.setText('Idle')
        self.btn_record.setText('Record')



