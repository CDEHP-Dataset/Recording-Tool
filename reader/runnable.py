import abc
import threading


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
