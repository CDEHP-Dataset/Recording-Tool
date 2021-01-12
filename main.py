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


from sensor import RealSense, RealSenseError


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
        self.save = False
        self.canceled = False

        self._aid = 0
        self._pid = 0
        self._sid = 0

        if self.args.master:
            self.network_controller = netsync.SyncServer(self.args)
        else:
            self.network_controller = netsync.SyncClient(self.args)

        self.window = None

    def register_window(self, w):
        self.window = w

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
            self.save = False
            self.canceled = False
            
            if self.window:
                self.window.signal_status_update.emit()
                
            if self.args.master:
                self.network_controller.notify_start()

    def set_stop(self):
        if self.is_recording:
            self.is_recording = False
            self.save = True
            self.canceled = False
            
            if self.window:
                self.window.signal_status_update.emit()
                
            if self.args.master:
                self.network_controller.notify_stop()

    def set_cancel(self):
        if self.is_recording:
            self.is_recording = False
            self.canceled = True
            self.save = False
            
            if self.window:
                self.window.signal_status_update.emit()
                
            if self.args.master:
                self.network_controller.notify_cancel()


class WriteProcedure(Runnable):
    def __init__(self, args, q):
        super(WriteProcedure, self).__init__(args)
        self.q = q
        self.window = None
        
    def register_window(self, w):
        self.window = w

    def proc(self):
    
        while self.working:
        
            try:
                job = self.q.get(block=False)
            except queue.Empty:        
                time.sleep(0.1)
                continue

            path_write = os.path.join(self.args.path, "A{:04d}P{:04d}".format(job.actionID, job.peopleID))
            os.makedirs(path_write, exist_ok=True)
            
            root_path, sub_dirs, sub_files = next(os.walk(path_write))
            path_write = os.path.join(path_write, 'S{:02d}'.format(len(sub_dirs)))
            
            os.makedirs(os.path.join(path_write, "color"), exist_ok=True)
            os.makedirs(os.path.join(path_write, "depth"), exist_ok=True)

            for i in range(len(job.frames_color)):
                cv2.imwrite(os.path.join(path_write, "color", '{:06d}.png'.format(i)), job.frames_color[i])
                cv2.imwrite(os.path.join(path_write, "depth", '{:06d}.png'.format(i)), job.frames_depth[i])

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


class RealsenseReader(Runnable):
    
    def __init__(self, args, image_queue, controller: RecorderController):
        super(RealsenseReader, self).__init__(args)
        self.image_queue = image_queue
        self.realsense = RealSense()  # if self.args.master else FakeRS()
        
        self.controller = controller

        self.save_signal = False
        self.cancel_signal = False
        self.is_recording = False
        
        self.window = None
        
    def register_window(self, w):
        self.window = w

    def proc(self):
        writeInfo = WriteInfo(self.controller.aid, self.controller.pid)
        
        while self.working:
        
            rs_color_frame, rs_color_frame_show, rs_depth_frame = self.realsense.get_frame()
            rs_color_frame_show = cv2.rotate(rs_color_frame_show, cv2.ROTATE_90_CLOCKWISE)
            color_img = QtGui.QImage(rs_color_frame_show.data, rs_color_frame_show.shape[1],rs_color_frame_show.shape[0], QtGui.QImage.Format_RGB888)
            
            if self.window:
                self.window.signal_color_image.emit(color_img)

            if self.controller.is_recording:
                writeInfo.frames_color.append(rs_color_frame.copy())
                writeInfo.frames_depth.append(rs_depth_frame.copy())
            else:
                if self.controller.save:
                    writeInfo.setActionID(self.controller.aid)
                    writeInfo.setPeopleID(self.controller.pid)
                    self.image_queue.put(writeInfo)
                    
                    if self.window:
                        self.window.signal_queue_size.emit(self.image_queue.qsize())
                    
                if self.controller.save or self.controller.canceled:
                    self.controller.save = False
                    self.controller.canceled = False
                    self.controller.is_recording = False
                    writeInfo = WriteInfo(self.controller.aid, self.controller.pid)
        
        if self.controller.is_recording:
            # if still recording when quitting:
            # save the buffer into failsave location.
            
            writeInfo.setActionID(-1)
            writeInfo.setPeopleID(-1)
            self.image_queue.put(writeInfo)
            self.controller.save = False
            self.controller.canceled = False
            self.controller.is_recording = False


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

    app = QApplication([""])
    window = MainWindow(args, image_queue, controller)
    controller.register_window(window)
    window.show()

    writer = WriteProcedure(args, image_queue)
    writer.register_window(window)
    writer.start()
    
    try:
        print("[info] Waiting for sensor ...")
        rs_reader = RealsenseReader(args, image_queue, controller)
        print("[info] Realsense sensor opened.")
    except RealSenseError:
        writer.stop()
        controller.stop()
        exit(-1)

    rs_reader.register_window(window)
    rs_reader.start()

    while True:
        try:
            app.processEvents()
        
            if not window.isVisible():
                # Window closed.
                break
        
        except KeyboardInterrupt:
            break

    rs_reader.stop()
    writer.stop()
    controller.stop()

    sys.exit(0)


if __name__ == '__main__':
    main()

