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
