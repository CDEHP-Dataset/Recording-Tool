class Readable:

    def poll(self):
        raise NotImplementedError

    def read(self):
        raise NotImplementedError
