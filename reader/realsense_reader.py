import os
import queue

import cv2
import numpy as np
import pyrealsense2 as rs
from PyQt5 import QtGui

from reader.readable import Readable
from reader.reader_callback import ReaderCallback
from reader.runnable import Runnable
from reader.write_info import WriteInfo
from recorder_controller import RecorderController


class RealSenseError(Exception):
    pass


class RealsenseReader(Runnable, ReaderCallback, Readable):

    def __init__(self, args, controller: RecorderController):
        super(RealsenseReader, self).__init__(args)
        self.controller = controller
        self.queue = queue.Queue()
        try:
            self.device = rs.pipeline()
            config = rs.config()
            config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, 30)
            config.enable_stream(rs.stream.depth, 1280, 720, rs.format.z16, 30)
            self.profile = self.device.start(config)
            self.align = rs.align(rs.stream.color)
            self.device.wait_for_frames()
        except RuntimeError:
            raise RealSenseError
        self.window = None
        self.is_recording = False
        self.save_signal = False
        self.cancel_signal = False
        self.controller.register_reader(self)

    def register_window(self, window):
        self.window = window

    def notify_record(self):
        print("RealsenseReader: notified to recording")
        self.is_recording = True
        self.save_signal = False
        self.cancel_signal = False

    def notify_save(self, aid, pid):
        print("RealsenseReader: notified to saving")
        self.is_recording = False
        self.save_signal = True
        self.cancel_signal = False

    def notify_cancel(self):
        print("RealsenseReader: notified to cancelling")
        self.is_recording = False
        self.save_signal = False
        self.cancel_signal = True

    def proc(self):
        write_info = WriteInfo(self.controller.aid, self.controller.pid)

        while self.working:
            color_frame = None
            depth_frame = None
            while True:
                try:
                    frames = self.device.wait_for_frames()
                except RuntimeError:
                    print("[WARN] Frame rate dropping. (Frame didn't arrived within 5000)")
                    continue
                frames = self.align.process(frames)
                color_frame = frames.get_color_frame()
                depth_frame = frames.get_depth_frame()
                if depth_frame and color_frame:
                    break

            color_image = np.asanyarray(color_frame.get_data())
            color_image_show = cv2.resize(color_image, (480, 270))
            color_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
            depth_image = np.asanyarray(depth_frame.get_data())

            if self.is_recording:
                write_info.frames_color.append(color_image.copy())
                write_info.frames_depth.append(depth_image.copy())
            else:
                if self.args.layout == "portrait":
                    color_image_show = cv2.rotate(color_image_show, cv2.ROTATE_90_COUNTERCLOCKWISE)
                color_img = QtGui.QImage(color_image_show.data, color_image_show.shape[1],
                                         color_image_show.shape[0], QtGui.QImage.Format_RGB888)
                if self.window:
                    self.window.signal_color_image.emit(color_img)
                if self.save_signal:
                    write_info.set_action_id(self.controller.aid)
                    write_info.set_person_id(self.controller.pid)
                    print("RealsenseReader: a writeInfo is pushed into image_queue")
                    self.queue.put(write_info)
                    if self.window:
                        self.window.signal_queue_size.emit(self.queue.qsize())
                if self.save_signal or self.cancel_signal:
                    self.is_recording = False
                    self.save_signal = False
                    self.cancel_signal = False
                    write_info = WriteInfo(self.controller.aid, self.controller.pid)

    def poll(self):
        return self.queue.qsize() > 0

    def read(self):
        job = self.queue.get(block=False)
        print("RealsenseReader: returning save job ", len(job.frames_color), len(job.frames_depth))
        return [
            ("color", self.save_data, job.frames_color),
            # ("depth", self.save_data, job.frames_depth),
            ("depth_raw", self.save_data, job.frames_depth)
        ]

    def save_data(self, modal_path, modal_data):
        print("RealsenseReader: saving job ...", modal_path)
        for i in range(len(modal_data)):
            if modal_path.endswith("depth_raw"):
                np.save(os.path.join(modal_path, "{:06d}".format(i)), modal_data[i])
            else:
                cv2.imwrite(os.path.join(modal_path, "{:06d}.png".format(i)), modal_data[i])
