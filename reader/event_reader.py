import os
import queue
import shutil
import time

import cv2
import numpy
import PyCeleX5
from PyQt5 import QtGui

from reader.readable import Readable
from reader.reader_callback import ReaderCallback
from reader.runnable import Runnable
from recorder_controller import RecorderController


def random_string(l):
    return "".join("{:02x}".format(x) for x in os.urandom(l))


class EventCameraError(Exception):
    pass


class EventReader(Runnable, ReaderCallback, Readable):

    def __init__(self, args, controller: RecorderController):
        super(EventReader, self).__init__(args)
        self.controller = controller

        self.event_queue = queue.Queue()
        try:
            self.event_dev = PyCeleX5.PyCeleX5()
            self.event_dev.openSensor(PyCeleX5.DeviceType.CeleX5_MIPI)
            self.event_dev.setFpnFile("/home/event/Desktop/record_dataset_net/FPN_lab.txt")
            self.event_dev.setRotateType(2)
        except Exception:
            raise EventCameraError

        self.current_record = None

        self.is_recording = False
        self.save_signal = False
        self.cancel_signal = False
        self.controller.register_reader(self)

    def register_window(self, w):
        self.window = w

    def notify_record(self):
        if self.is_recording:
            print("event_reader notified to recording, but it is recording already.")
            return
        print("event_reader notified to recording")
        self.current_record = os.path.join(self.args.path, ".event_stream.{}".format(random_string(5)))
        self.event_dev.setLoopModeEnabled(True)
        self.event_dev.setSensorLoopMode(PyCeleX5.CeleX5Mode.Event_Off_Pixel_Timestamp_Mode, 1)
        self.event_dev.setSensorLoopMode(PyCeleX5.CeleX5Mode.Full_Picture_Mode, 2)
        self.event_dev.setSensorLoopMode(PyCeleX5.CeleX5Mode.Event_Off_Pixel_Timestamp_Mode, 3)
        # self.event_dev.setPictureNumber(1, PyCeleX5.CeleX5Mode.Full_Picture_Mode)
        # self.event_dev.setEventDuration(20, PyCeleX5.CeleX5Mode.Event_Off_Pixel_Timestamp_Mode)
        self.event_dev.startRecording(self.current_record)
        self.is_recording = True

    def notify_save(self, aid, pid):
        if not self.is_recording:
            print("event_reader notified to saving, but it is not in recording mode.")
            return

        print("event_reader notified to saving")
        self.event_dev.stopRecording()
        self.event_queue.put((
            "event_stream",
            self.save_event,
            (self.current_record,)
        ))
        self.is_recording = False
        self.current_record = None

    def notify_cancel(self):
        print("event_reader notified to cancelling")
        if not self.is_recording:
            print("event_reader notified to saving, but it is not in recording mode.")
            return

        self.event_dev.stopRecording()
        os.remove(self.current_record)
        self.is_recording = False
        self.current_record = None

    def proc(self):
        while self.working:
            if self.window and not self.is_recording:
                img = self.event_dev.getEventPicBuffer(PyCeleX5.EventPicType.EventBinaryPic)
                if self.args.layout == "portrait":
                    img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                    img = cv2.resize(img, (300, 480))
                else:
                    img = cv2.resize(img, (480, 300))
                img = numpy.ascontiguousarray(img[:, ::-1])
                color_img = QtGui.QImage(img.data, img.shape[1], img.shape[0], QtGui.QImage.Format_Grayscale8)

                self.window.signal_event_snapshot.emit(color_img)

            time.sleep(0.01)

    def poll(self):
        v = self.event_queue.qsize() > 0
        return v

    def read(self):
        print("event reader: returning job ...")
        job = [self.event_queue.get(block=False)]
        return job

    def save_event(self, modal_path, modal_data):
        print("event reader: saving job ...", modal_path)
        shutil.move(modal_data[0], os.path.join(modal_path, "EventStream.bin"))
