from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QApplication

from MainWindow import MainWindow
import sys

import threading
import argparse
import os
import abc
import time
import queue
import cv2
import netsync
import socket
import numpy as np
import shutil


from sensor import RealSense, RealSenseError
import pyCeleX5 as pycx


def parse_args():
    par = argparse.ArgumentParser('dataset capture tool')
    par.add_argument('--path', default='./dataset', help='the work folder for storing results')
    
    par.add_argument('-M', '--master', action='store_true', help='start the datset capture tool as master.')
    par.add_argument('--broadcast-addr', default='10.12.41.255', help='the broadcast address for network sync.')
    par.add_argument('--port', type=int, default=30728, help='communication port number for network sync.')

    par.add_argument('-a', "--aid", default=0, type=int)
    par.add_argument('-s', "--sid", default=0, type=int)
    par.add_argument('-p', "--pid", default=0, type=int)
    
    return par.parse_args()


def random_string():
    return "".join("{:02x}".format(x) for x in os.urandom(5))


class WriteInfo:
    def __init__(self, actionid=0, peopleid=0):
        self.frames_color = []
        self.frames_depth = []
        self.actionID = actionid
        self.peopleID = peopleid

    def setActionID(self, id):
        self.actionID = id

    def setPeopleID(self, id):
        self.peopleID = id


class Runnable(metaclass=abc.ABCMeta):
    def __init__(self, args):
        self.args = args
        self.working = False
        self.worker = None

    def start(self):
        if self.working or self.worker is not None:
            return
            
        self.working = True
        self.worker = threading.Thread(target=self.proc)
        self.worker.start()
        
    def stop(self):
        if not self.working or self.worker is None:
            return
        
        self.working = False
        self.worker.join()
        self.worker = None

    @abc.abstractmethod
    def proc(self):
        pass


class RecorderController(Runnable):
    def __init__(self, args):
        super(RecorderController, self).__init__(args)

        self.is_recording = False

        self._aid = 0
        self._pid = 0
        self._sid = 0

        if self.args.master:
            self.network_controller = netsync.SyncServer(self.args)
        else:
            self.network_controller = netsync.SyncClient(self.args)

        self.window = None
        self.readers = []

    def register_window(self, w):
        self.window = w
    
    def register_reader(self, reader):
        self.readers.append(reader)

    @property
    def aid(self):
        return self._aid
    
    @aid.setter
    def aid(self, value):
        self._aid = value

        if self.args.master:
            self.network_controller.set_record(aid=self._aid)
            self.network_controller.notify_update()

        if self.window:
            self.window.signal_id_update.emit()

    @property
    def pid(self):
        return self._pid
    
    @pid.setter
    def pid(self, value):
        self._pid = value

        if self.args.master:
            self.network_controller.set_record(pid=self._pid)
            self.network_controller.notify_update()

        if self.window:
            self.window.signal_id_update.emit()

    @property
    def sid(self):
        return self._sid

    @sid.setter
    def sid(self, value):
        self._sid = value
        if self.args.master:
            self.network_controller.set_record(sid=self._sid)
            self.network_controller.notify_update()

        if self.window:
            self.window.signal_id_update.emit()

    def listen_for_sync(self):
        while self.working:
            try:
                command = self.network_controller.wait(timeout=0.1)[0]
                ctrl = command.get("ctrl", None)
                if ctrl is None:
                    continue

                if ctrl == 'update':
                    self.aid = command.get('aid', 0)
                    self.pid = command.get('pid', 0)
                    self.sid = command.get('sid', 0)
                elif ctrl == 'record':
                    self.set_record()
                elif ctrl == 'stop':
                    self.set_stop()
                elif ctrl == 'cancel':
                    self.set_cancel()
            except socket.timeout:
                continue

    proc = listen_for_sync

    def set_record(self):
        if not self.is_recording:
            self.is_recording = True
    
            if self.args.master:
                self.network_controller.notify_start()

            for each in self.readers:
                each.notify_record()

            if self.window:
                self.window.signal_status_update.emit()

    def set_stop(self):
        if self.is_recording:
            self.is_recording = False

            if self.window:
                self.window.signal_status_update.emit()

            if self.args.master:
                self.network_controller.notify_stop()

            for each in self.readers:
                each.notify_save(self.aid, self.pid)

    def set_cancel(self):
        if self.is_recording:
            self.is_recording = False

            if self.args.master:
                self.network_controller.notify_cancel()
            
            for each in self.readers:
                each.notify_cancel()

            if self.window:
                self.window.signal_status_update.emit()


class ReaderCallback:

    def notify_record(self):
        pass

    def notify_save(self, aid, pid):
        pass

    def notify_cancel(self):
        pass


class WriteProcedure(Runnable, ReaderCallback):
    def __init__(self, args, controller: RecorderController):
        super(WriteProcedure, self).__init__(args)
        self.pending_jobs = queue.Queue()
        self.window = None
        self.readables = []
        controller.register_reader(self)
    
    def register_window(self, w):
        self.window = w

    def register_readable(self, r):
        self.readables.append(r)

    def notify_save(self, aid, pid):
        self.pending_jobs.put((aid, pid))

    def proc(self):
    
        while self.working:

            if not all(r.poll(timeout=0.1) for r in self.readables):
                time.sleep(0.1)
                continue
            
            multi_modal_stream = []
            for r in self.readables:
                multi_modal_stream.extend(r.read())

            aid, pid = self.pending_jobs.get()

            path_write = os.path.join(self.args.path, "A{:04d}P{:04d}".format(aid, pid))
            os.makedirs(path_write, exist_ok=True)
            
            root_path, sub_dirs, sub_files = next(os.walk(path_write))
            path_write = os.path.join(path_write, 'S{:02d}'.format(len(sub_dirs)))

            for each in multi_modal_stream:
                modal_name, f_save, modal_data = each
                modal_path = os.path.join(path_write, modal_name)
                os.makedirs(modal_path, exist_ok=True)
                f_save(modal_path, modal_data)

            if self.window:
                self.window.signal_queue_size.emit(self.q.qsize())


# class FakeRS():
#     import colorsys
#     def __init__(self):
#         self.fid = 0
#         pass
#
#     def get_frame(self):
#         t = time.time()
#
#         while time.time() - t < 1 / 60:
#             pass
#
#         r, g, b = colorsys.hsv_to_rgb(self.fid % 360 / 360, 0.8, 1)
#         r, g, b = map(int, (r * 256, g * 256, b * 256))
#
#         color = np.zeros([720, 1280, 3], dtype=np.uint8)
#         disp = np.zeros([320, 480, 3], dtype=np.uint8)
#
#         cv2.putText(disp, "{:04d}".format(self.fid), (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (r, g, b), 3, cv2.LINE_AA)
#         cv2.putText(color, "{:04d}".format(self.fid), (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (r, g, b), 3, cv2.LINE_AA)
#
#         self.fid += 1
#
#         return color, disp, np.zeros([720, 1280, 1], dtype=np.uint8)


class Readable:

    def poll(self):
        return False

    def read(self):
        return [None]


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
        self.is_recording = True

    def notify_save(self, aid, pid):
        self.is_recording = False
        self.save_signal = False

    def notify_cancel(self):
        self.is_recording = False
        self.save_signal = True

    def proc(self):
        writeInfo = WriteInfo(self.controller.aid, self.controller.pid)
        
        while self.working:
        
            rs_color_frame, rs_color_frame_show, rs_depth_frame = self.realsense.get_frame()
            rs_color_frame_show = cv2.rotate(rs_color_frame_show, cv2.ROTATE_90_CLOCKWISE)
            color_img = QtGui.QImage(rs_color_frame_show.data, rs_color_frame_show.shape[1],rs_color_frame_show.shape[0], QtGui.QImage.Format_RGB888)
            
            if self.window:
                self.window.signal_color_image.emit(color_img)

            if self.is_recording:
                writeInfo.frames_color.append(rs_color_frame.copy())
                writeInfo.frames_depth.append(rs_depth_frame.copy())
            else:
                if self.save_signal:
                    writeInfo.setActionID(self.controller.aid)
                    writeInfo.setPeopleID(self.controller.pid)
                    self.image_queue.put(writeInfo)
                    
                    if self.window:
                        self.window.signal_queue_size.emit(self.image_queue.qsize())
                    
                if self.save_signal or self.cancel_signal:
                    self.save_signal = False
                    self.cancel_signal = False
                    self.is_recording = False
                    writeInfo = WriteInfo(self.controller.aid, self.controller.pid)

    def poll(self):
        return not self.image_queue.empty()

    def read(self):
        job = self.image_queue.get(block=False)

        return [
            ("color", self.save_data, job.frames_color),
            ("depth", self.save_data, job.frames_depth)
        ]
    
    def save_data(self, modal_path, modal_data):
        for i in range(len(modal_data)):
            cv2.imwrite(os.path.join(path_write, '{:06d}.png'.format(i)), modal_data[i])


class EventCameraError(Exception): pass


class EventReader(Runnable, ReaderCallback, Readable):
    
    def __init__(self, args, controller: RecorderController):
        super(EventReader, self).__init__(args)
        self.controller = controller

        self.evnet_queue = queue.Queue()
        try:
            self.event_dev = pycx.pyCeleX5()
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
            return
        self.current_record = os.path.join(self.args.path, ".event_stream.{}".format(random_string(5)))
        self.event_dev.startRecording(self.current_record)

    def notify_save(self, aid, pid):
        if not self.is_recording:
            return

        self.event_dev.stopRecording()
        self.event_queue.put((
            "event_stream", 
            self.save_event, 
            (self.current_record,)
        ))
        self.current_record = None

    def notify_cancel(self):
        if not self.is_recording:
            return

        self.event_dev.stopRecording()
        os.remove(self.current_record)
        self.current_record = None

    def proc(self):
        while self.working:
            if self.window:
                EVENT_BINARY_PIC = 0
                img = self.event_dev.getEventPicBuffer(EVENT_BINARY_PIC)
                color_img = QtGui.QImage(img.data, img.shape[1],img.shape[0], QtGui.QImage.Format_Grayscale8)

                self.window.signal_event_snapshot.emit(color_img)
                
            time.sleep(0.01)

    def poll(self):
        return not self.event_queue.empty()

    def read(self):
        job = [self.image_queue.get(block=False)]

    def save_event(self, modal_path, modal_data):
        shutil.move(modal_data[0], os.path.join(modal_path, "EventStream.bin"))


def main():

    args = parse_args()
    
    path_base = args.path
    
    if not os.path.exists(path_base):
        os.makedirs(path_base)
        
    if not os.path.isdir(path_base):
        print('Path is invalid')
        sys.exit()
    
    image_queue = queue.Queue()
    controller = RecorderController(args)

    if not args.master:
        controller.start()

    writer = WriteProcedure(args, controller)
    writer.start()

    app = QApplication([""])
    window = MainWindow(args, controller)
    
    writer.register_window(window)
    controller.register_window(window)
    
    window.show()

    try:
        print("[info] Waiting for sensor ...")
        rs_reader = RealsenseReader(args, controller)
        print("[info] Realsense sensor opened.")
    except RealSenseError:
        writer.stop()
        controller.stop()
        print("Failed to open Realsense Camera.")
        exit(-1)
	
    try:
        print("")
        event_reader = EventReader(args, controller)
        print("[info] Event camera opened.")
    except EventCameraError:
        rs_reader.stop()
        writer.stop()
        controller.stop()
        print("Failed to open Event Camera.")
        exit(-2)

    rs_reader.register_window(window)
    rs_reader.start()
    
    event_reader.register_window(window)
    event_reader.start()
    
    while True:
        try:
            app.processEvents()
        
            if not window.isVisible():
                # Window closed.
                break
        
        except KeyboardInterrupt:
            break

    rs_reader.stop()
    event_reader.stop()
    writer.stop()
    controller.stop()

    sys.exit(0)


if __name__ == '__main__':
    main()

