import os
import queue
import shutil
import time

import PyCeleX5
import cv2
import numpy
from PyQt5 import QtGui

from reader.readable import Readable
from reader.reader_callback import ReaderCallback
from reader.runnable import Runnable
from recorder_controller import RecorderController


def random_string(length: int):
    return "".join("{:02x}".format(x) for x in os.urandom(length))


class EventCameraError(Exception):
    pass


class EventReader(Runnable, ReaderCallback, Readable):

    def __init__(self, args, controller: RecorderController):
        super(EventReader, self).__init__(args)
        self.controller = controller
        self.queue = queue.Queue()
        try:
            self.device = PyCeleX5.PyCeleX5()
            self.device.openSensor(PyCeleX5.DeviceType.CeleX5_MIPI)
            self.device.isSensorReady()
            self.device.getClockRate()
            self.device.getEventFrameTime()
            self.device.getOpticalFlowFrameTime()
            self.device.getThreshold()
            self.device.getBrightness()
            self.device.getEventDataFormat()
            self.device.setRotateType(2)

            self.device.setThreshold(70)
            self.device.setSensorFixedMode(PyCeleX5.CeleX5Mode.Event_Off_Pixel_Timestamp_Mode)

            # self.event_dev.setPictureNumber(1, PyCeleX5.CeleX5Mode.Full_Picture_Mode)
            # self.event_dev.setEventDuration(20, PyCeleX5.CeleX5Mode.Event_Off_Pixel_Timestamp_Mode)
            # self.device.setSensorLoopMode(PyCeleX5.CeleX5Mode.Event_Off_Pixel_Timestamp_Mode, 1)
            # self.device.setSensorLoopMode(PyCeleX5.CeleX5Mode.Full_Picture_Mode, 2)
            # self.device.setSensorLoopMode(PyCeleX5.CeleX5Mode.Event_Off_Pixel_Timestamp_Mode, 3)
            # self.device.setLoopModeEnabled(True)

            self.device.setFpnFile("/home/event/Desktop/record_dataset_net/FPN_lab.txt")
        except Exception:
            raise EventCameraError
        self.window = None
        self.current_record = None
        self.is_recording = False
        self.controller.register_reader(self)

    def register_window(self, window):
        self.window = window

    def notify_record(self):
        if self.is_recording:
            print("EventReader: notified to recording, but it is recording already.")
            return
        print("EventReader: notified to recording")
        self.current_record = os.path.join(self.args.path, ".event_stream.{}".format(random_string(5)))
        self.is_recording = True
        self.device.startRecording(self.current_record)

    def notify_save(self, aid, pid):
        if not self.is_recording:
            print("EventReader: notified to saving, but it is not in recording mode.")
            return
        print("EventReader: notified to saving")
        self.is_recording = False
        self.device.stopRecording()
        self.queue.put(("event_stream", self.save_data, (self.current_record,)))
        self.current_record = None

    def notify_cancel(self):
        print("EventReader: notified to cancelling")
        if not self.is_recording:
            print("EventReader: notified to canceling, but it is not in recording mode.")
            return
        self.is_recording = False
        self.device.stopRecording()
        os.remove(self.current_record)
        self.current_record = None

    def proc(self):
        while self.working:
            if self.window and not self.is_recording:
                img = self.device.getEventPicBuffer(PyCeleX5.EventPicType.EventDenoisedBinaryPic)
                img = cv2.resize(img, (480, 300))
                if self.args.layout == "portrait":
                    img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                img = numpy.ascontiguousarray(img[:, ::-1])
                img_show = QtGui.QImage(img.data, img.shape[1], img.shape[0], QtGui.QImage.Format_Grayscale8)
                self.window.signal_event_snapshot.emit(img_show)
            time.sleep(0.01)

    def poll(self):
        return self.queue.qsize() > 0

    def read(self):
        print("EventReader: returning job ...")
        return [self.queue.get(block=False)]

    def save_data(self, modal_path, modal_data):
        print("EventReader: saving job ...", modal_path)
        shutil.move(modal_data[0], os.path.join(modal_path, "EventStream.bin"))
