import socket

import netsync
from reader.runnable import Runnable


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

    def register_window(self, window):
        self.window = window

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

                if ctrl == "update":
                    self.aid = command.get("aid", 0)
                    self.pid = command.get("pid", 0)
                    self.sid = command.get("sid", 0)
                elif ctrl == "record":
                    self.set_record()
                elif ctrl == "stop":
                    self.set_stop()
                elif ctrl == "cancel":
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
