import os
import queue

import cv2
from PyQt5 import QtGui

from reader.readable import Readable
from reader.reader_callback import ReaderCallback
from reader.runnable import Runnable
from reader.write_info import WriteInfo
from recorder_controller import RecorderController
from sensor import RealSense


class RealsenseReader(Runnable, ReaderCallback, Readable):

    def __init__(self, args, controller: RecorderController):
        super(RealsenseReader, self).__init__(args)
        self.image_queue = queue.Queue()
        self.realsense = RealSense()  # if self.args.master else FakeRS()

        self.controller = controller

        self.save_signal = False
        self.cancel_signal = False
        self.is_recording = False

        self.window = None
        controller.register_reader(self)

    def register_window(self, w):
        self.window = w

    def notify_record(self):
        print("rs_reader notified to recording")
        self.is_recording = True

    def notify_save(self, aid, pid):
        print("rs_reader notified to saving")
        self.is_recording = False
        self.save_signal = True
        self.cancel_signal = False

    def notify_cancel(self):
        print("rs_reader notified to cancelling")
        self.is_recording = False
        self.save_signal = False
        self.cancel_signal = True

    def proc(self):
        writeInfo = WriteInfo(self.controller.aid, self.controller.pid)

        while self.working:
            rs_color_frame, rs_color_frame_show, rs_depth_frame = self.realsense.get_frame()

            if self.is_recording:
                writeInfo.frames_color.append(rs_color_frame.copy())
                writeInfo.frames_depth.append(rs_depth_frame.copy())
            else:
                if self.args.layout == "portrait":
                    rs_color_frame_show = cv2.rotate(rs_color_frame_show, cv2.ROTATE_90_COUNTERCLOCKWISE)

                color_img = QtGui.QImage(rs_color_frame_show.data, rs_color_frame_show.shape[1],
                                         rs_color_frame_show.shape[0], QtGui.QImage.Format_RGB888)

                if self.window:
                    self.window.signal_color_image.emit(color_img)

                if self.save_signal:
                    writeInfo.setActionID(self.controller.aid)
                    writeInfo.setPeopleID(self.controller.pid)
                    print("rs_reader: a writeInfo is pushed into image_queue")
                    self.image_queue.put(writeInfo)

                    if self.window:
                        self.window.signal_queue_size.emit(self.image_queue.qsize())

                if self.save_signal or self.cancel_signal:
                    self.save_signal = False
                    self.cancel_signal = False
                    self.is_recording = False
                    writeInfo = WriteInfo(self.controller.aid, self.controller.pid)

    def poll(self):
        v = self.image_queue.qsize() > 0
        return v

    def read(self):
        job = self.image_queue.get(block=False)
        print("realsense reader: returning save job:", len(job.frames_color), len(job.frames_depth))
        return [
            ("color", self.save_data, job.frames_color),
            ("depth", self.save_data, job.frames_depth)
        ]

    def save_data(self, modal_path, modal_data):
        print("realsense reader: saving job ...", modal_path)
        for i in range(len(modal_data)):
            cv2.imwrite(os.path.join(modal_path, '{:06d}.png'.format(i)), modal_data[i])
