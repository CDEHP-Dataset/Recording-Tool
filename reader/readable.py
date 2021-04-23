class Readable:

    def poll(self):
        raise NotImplementedError
        return False

    def read(self):
        raise NotImplementedError
