import queue
import os
import cv2
import sys

isRecord = False
isSave = False
current_action = 0
current_person = 0
queue_save = queue.Queue()
queue_size = 0
log = []
path_base = ''


def deprecated(f):
    def wrap():
        print("Warning: function", f.__qualname__, "is deprecated", file=sys.stderr)
        return f()
    
    return wrap



@deprecated
def mkdir(path):
    is_exist = os.path.exists(path)
    if not is_exist:
        os.makedirs(path)


@deprecated
def writing_data():
    while True:
        writeInfo = queue_save.get()
        path_write = '{}Desktop/Dataset/A{:04d}P{:04d}'.format(path_base, writeInfo.actionID, writeInfo.peopleID)
        mkdir(path_write)
        dirs = os.listdir(path_write)
        path_write+='/S{:02d}'.format(len(dirs))
        mkdir(path_write+'/color')
        mkdir(path_write+'/depth')
        for i in range(len(writeInfo.frames_color)):
            cv2.imwrite('{}/color/{:06d}.png'.format(path_write, i), writeInfo.frames_color[i])
            cv2.imwrite('{}/depth/{:06d}.png'.format(path_write, i), writeInfo.frames_depth[i])

