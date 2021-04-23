import os
import queue
import time

from reader.reader_callback import ReaderCallback
from reader.runnable import Runnable
from recorder_controller import RecorderController


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
        print("writer: registering readable:", r)
        self.readables.append(r)

    def notify_save(self, aid, pid):
        print("writer notified to saving")
        self.pending_jobs.put((aid, pid))

    def proc(self):

        while self.working:

            if len(self.readables) <= 0 or not all([r.poll() for r in self.readables]):
                time.sleep(0.1)
                continue

            print("writer: exit from poll loop")
            multi_modal_stream = []
            for r in self.readables:
                print("writer: reading from:", r, "...")
                multi_modal_stream.extend(r.read())

            aid, pid = self.pending_jobs.get()
            print("Writer: start saving:", aid, pid)
            path_write = os.path.join(self.args.path, "A{:04d}P{:04d}".format(aid, pid))
            os.makedirs(path_write, exist_ok=True)

            root_path, sub_dirs, sub_files = next(os.walk(path_write))
            path_write = os.path.join(path_write, 'S{:02d}'.format(len(sub_dirs)))

            print("number of modals:", len(multi_modal_stream))

            for each in multi_modal_stream:
                modal_name, f_save, modal_data = each
                modal_path = os.path.join(path_write, modal_name)
                os.makedirs(modal_path, exist_ok=True)
                print("calling save function:", modal_path)
                f_save(modal_path, modal_data)

            if self.window:
                self.window.signal_queue_size.emit(self.pending_jobs.qsize())
