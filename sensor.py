import pyrealsense2 as rs
import numpy as np
import cv2
# from pylibfreenect2 import Freenect2, SyncMultiFrameListener
# from pylibfreenect2 import FrameType, Registration, Frame
# from pylibfreenect2 import OpenGLPacketPipeline
import sys


class Sensor:
    def __init__(self, have_realsense=True, have_kinect=True):
        pass


class RealSenseError(Exception):
    pass

class RealSenseDeviceException(RealSenseError):
    pass

class RealSenseIOException(RealSenseError):
    pass

class RealSense:
    def __init__(self):
        try:
            self.pipeline = rs.pipeline()
            self.pipeline.start()
        except RuntimeError:
            # self.pipeline.stop()
            print("FATAL: Failed to open Realsense device.", file=sys.stderr)
            raise RealSenseDeviceException from RuntimeError
        
        try:
            frame = self.pipeline.wait_for_frames()
        except RuntimeError:
            raise RealSenseIOException from RuntimeError

        color = frame.get_color_frame()
        self.height = color.get_height()
        self.width = color.get_width()

        # align the depth frame to color frame
        self.align = rs.align(rs.stream.color)

    def get_frame(self):
        while True:
            try:
                frames = self.pipeline.wait_for_frames()
            except RuntimeError:
                # frame timeout.
                print("[WARN] Frame rate dropping. (Frame didn't arrived within 5000)")
                continue
            frames = self.align.process(frames)
            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()
            if not depth_frame or not color_frame:
                continue
            break

        color_image = np.asanyarray(color_frame.get_data())
        color_image_show = cv2.resize(color_image, (480, 320))
        color_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
        depth_image = np.asanyarray(depth_frame.get_data())
        return color_image, color_image_show, depth_image


class Kinect:
    def __init__(self):
        try:
            self.pipeline = OpenGLPacketPipeline()
        except:
            print("FATAL: Failed to open Kinect device.", file=sys.stderr)
            sys.exit(1)

        fn = Freenect2()
        num_devices = fn.enumerateDevices()
        if num_devices == 0:
            print("FATAL: No Kinect device connected!", file=sys.stderr)
            sys.exit(1)

        serial = fn.getDeviceSerialNumber(0)
        device = fn.openDevice(serial, pipeline=self.pipeline)

        self.listener = SyncMultiFrameListener(FrameType.Color | FrameType.Ir | FrameType.Depth)
        device.setColorFrameListener(self.listener)
        device.setIrAndDepthFrameListener(self.listener)
        device.start()
        self.registration = Registration(device.getIrCameraParams(),
                                device.getColorCameraParams())
        self.undistorted = Frame(512, 424, 4)
        self.registered = Frame(512, 424, 4)


    def get_frame(self):
        frames = self.listener.waitForNewFrame()
        color = frames["color"]
        depth = frames["depth"]

        self.registration.apply(color, depth, self.undistorted, self.registered)

        return color

