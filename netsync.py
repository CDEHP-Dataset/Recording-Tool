import argparse
import socket
import struct
import time
import json
import threading


SO_TIMESTAMPING = 37
SO_TIMESTAMPNS = 35
SOF_TIMESTAMPING_TX_HARDWARE = (1 << 0)
SOF_TIMESTAMPING_TX_SOFTWARE = (1 << 1)
SOF_TIMESTAMPING_RX_HARDWARE = (1 << 2)
SOF_TIMESTAMPING_RX_SOFTWARE = (1 << 3)
SOF_TIMESTAMPING_SOFTWARE = (1 << 4)
SOF_TIMESTAMPING_SYS_HARDWARE = (1 << 5)
SOF_TIMESTAMPING_RAW_HARDWARE = (1 << 6)
SOF_TIMESTAMPING_OPT_ID = (1 << 7)
SOF_TIMESTAMPING_TX_SCHED = (1 << 8)
SOF_TIMESTAMPING_TX_ACK = (1 << 9)
SOF_TIMESTAMPING_OPT_CMSG = (1 << 10)
SOF_TIMESTAMPING_OPT_TSONLY = (1 << 11)


def parse_args():
    par = argparse.ArgumentParser()
    par.add_argument("--host", default=False, action="store_true", help="run as host node.")
    par.add_argument("-p", "--port", default=30728, type=int)

    par.add_argument("-b", "--broadcast-addr", default="10.12.41.255", help="broadcast address")

    args = par.parse_args()
    return args


class SyncServer:

    def __init__(self, args):
        self.args = args
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, SO_TIMESTAMPNS, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, SO_TIMESTAMPING, SOF_TIMESTAMPING_RX_HARDWARE | SOF_TIMESTAMPING_TX_HARDWARE | SOF_TIMESTAMPING_RAW_HARDWARE)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(("0.0.0.0", self.args.port))

        self.pid = 0  # person id
        self.aid = 0  # action id
        self.sid = 0  # shot id

    def set_record(self, pid=None, aid=None, sid=None):
        self.pid = pid if pid is not None else self.pid
        self.aid = aid if aid is not None else self.aid
        self.sid = sid if sid is not None else self.sid

    def broadcast(self, data):
        self.sock.sendto(json.dumps(data).encode("utf8"), (self.args.broadcast_addr, self.args.port))

    def notify_update(self):
        d = {
            "t": time.time(),
            "ctrl": "update",
            "aid": self.aid,
            "pid": self.pid,
            "sid": self.sid,
        }

        self.broadcast(d)

    def notify_start(self):
        d = {
            "t": time.time(),
            "ctrl": "record",
            "aid": self.aid,
            "pid": self.pid,
            "sid": self.sid,
        }

        self.broadcast(d)

    def notify_stop(self):
        d = {
            "t": time.time(),
            "ctrl": "stop",
            "aid": self.aid,
            "pid": self.pid,
            "sid": self.sid,
        }

        self.broadcast(d)

    def notify_cancel(self):
        d = {
            "t": time.time(),
            "ctrl": "cancel",
            "aid": self.aid,
            "pid": self.pid,
            "sid": self.sid,
        }

        self.broadcast(d)


class SyncClient:
    def __init__(self, args):
        self.args = args
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

        self.conn.setsockopt(socket.SOL_SOCKET, SO_TIMESTAMPNS, 1)
        self.conn.setsockopt(socket.SOL_SOCKET, SO_TIMESTAMPING, SOF_TIMESTAMPING_RX_HARDWARE | SOF_TIMESTAMPING_RAW_HARDWARE | SOF_TIMESTAMPING_SYS_HARDWARE | SOF_TIMESTAMPING_SOFTWARE)
        self.conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.conn.settimeout(0.1)
        self.conn.bind(("0.0.0.0", self.args.port))

        self.host = None

    def wait(self, timeout=None):
        enter_time = time.time()
        last_time = enter_time

        while timeout is None or last_time - enter_time < timeout:
            try:
                raw_data, ancdata, flags, address = self.conn.recvmsg(65535, 1024)
            except socket.timeout:
                last_time = time.time()
                continue

            client_side_ts = time.time()
            timestamp = 0

            if len(ancdata) > 0:

                for i in ancdata:
                    cmsg_level, cmsg_type, cmsg_data = i
                    if cmsg_level != socket.SOL_SOCKET:
                        continue

                    if cmsg_type == SO_TIMESTAMPNS:
                        tmp = (struct.unpack("iiii", i[2]))
                        timestamp = tmp[0] + tmp[2] * 1e-9
                        print("SCM_TIMESTAMPNS,", tmp, ", timestamp =", timestamp)
                        break

            if self.host is None or self.host == address:
                if self.host is None:
                    self.host = address
                    print("Now receiving sync signal from", self.host)

                try:
                    d = json.loads(raw_data.decode("utf8"))
                    return d, {"nic-rx": timestamp, "client": client_side_ts}
                except json.JSONDecodeError:
                    print("IGN: (str)", raw_data.decode("utf8"))
                except UnicodeDecodeError:
                    print("IGN: (raw)", raw_data.decode("utf8"))

        raise socket.timeout

def proc_server(args):
    s = SyncServer(args)
    x = 0

    while True:
        s.set_record(pid=0)
        s.notify_start()
        time.sleep(2)

        if x % 2 == 0:
            s.notify_stop()
        else:
            s.notify_cancel()
        x += 1

def proc_client(args):
    c = SyncClient(args)

    while True:
        print(c.wait())


def main():
    args = parse_args()
    if args.host:
        print("server mode")
        proc_server(args)
    else:
        print("client mode")
        proc_client(args)


if __name__ == "__main__":
    main()

