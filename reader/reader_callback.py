class ReaderCallback:

    def notify_record(self):
        print("default record callback handler called on", self)
        pass

    def notify_save(self, aid, pid):
        print("default save callback handler called on", self)
        pass

    def notify_cancel(self):
        print("default cancel callback handler called on", self)
        pass
