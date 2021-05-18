class WriteInfo:
    def __init__(self, action_id=0, person_id=0):
        self.frames_color = []
        self.frames_depth = []
        self.action_id = action_id
        self.people_id = person_id

    def set_action_id(self, action_id):
        self.action_id = action_id

    def set_person_id(self, person_id):
        self.people_id = person_id
