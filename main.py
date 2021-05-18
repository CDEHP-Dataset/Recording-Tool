#!/usr/bin/env python3
# coding=utf-8

import argparse
import os
import queue
import sys

from PyQt5.QtWidgets import QApplication

from MainWindow import MainWindow
from reader.event_reader import EventReader, EventCameraError
from reader.realsense_reader import RealsenseReader
from recorder_controller import RecorderController
from sensor import RealSenseError
from write_procedure import WriteProcedure


class Layouts:
    alias = {
        "portrait": {"p", "v", "vertical"},
        "landscape": {"l", "h", "horizontal"}
    }

    def __getitem__(self, item):
        for k in self.alias:
            if item.lower() == k:
                return k

            if item.lower() in self.alias[k]:
                return k

    def __contains__(self, item):
        return any((item.lower() == k or item.lower() in self.alias[k]) for k in self.alias)

    def __iter__(self):
        for k in self.alias:
            yield k
            for v in self.alias[k]:
                yield v


def parse_args():
    par = argparse.ArgumentParser("dataset capture tool")
    par.add_argument("--path", default="./dataset", help="the work folder for storing results")

    par.add_argument("-M", "--master", action="store_true", help="start the datset capture tool as master.")
    par.add_argument("--broadcast-addr", default="10.12.41.255", help="the broadcast address for network sync.")
    par.add_argument("--port", type=int, default=30728, help="communication port number for network sync.")

    par.add_argument("-a", "--aid", default=0, type=int)
    par.add_argument("-s", "--sid", default=0, type=int)
    par.add_argument("-p", "--pid", default=0, type=int)

    layouts = Layouts()
    par.add_argument("-L", "--layout", default="portrait", choices=layouts, type=lambda x: layouts[x])

    return par.parse_args()


def main():
    args = parse_args()

    path_base = args.path

    if not os.path.exists(path_base):
        os.makedirs(path_base)

    if not os.path.isdir(path_base):
        print("Path is invalid")
        sys.exit()

    image_queue = queue.Queue()
    controller = RecorderController(args)

    if not args.master:
        controller.start()

    writer = WriteProcedure(args, controller)
    writer.start()

    app = QApplication([""])
    window = MainWindow(args, controller)

    writer.register_window(window)
    controller.register_window(window)

    window.show()

    try:
        print("[info] Waiting for sensor ...")
        realsense_reader = RealsenseReader(args, controller)
        print("[info] Realsense sensor opened.")
    except RealSenseError:
        writer.stop()
        controller.stop()
        print("Failed to open Realsense Camera.")
        exit(-1)

    try:
        print("")
        event_reader = EventReader(args, controller)
        print("[info] Event camera opened.")
    except EventCameraError:
        realsense_reader.stop()
        writer.stop()
        controller.stop()
        print("Failed to open Event Camera.")
        exit(-2)

    realsense_reader.register_window(window)
    realsense_reader.start()
    writer.register_readable(realsense_reader)

    event_reader.register_window(window)
    event_reader.start()
    writer.register_readable(event_reader)

    while True:
        try:
            app.processEvents()

            if not window.isVisible():
                # Window closed.
                break

        except KeyboardInterrupt:
            break

    realsense_reader.stop()
    event_reader.stop()
    writer.stop()
    controller.stop()

    sys.exit(0)


if __name__ == "__main__":
    main()
