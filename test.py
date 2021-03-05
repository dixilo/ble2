#!/usr/bin/env python3
import serial

from datetime import datetime, timezone, timedelta
from time import sleep
from om_comm import MOVE_FWD, MOVE_BKW, STATUS, INIT_CMD, STOP
import numpy as np


DEV_NAME = 'COM3'
JST = timezone(timedelta(hours=+9), 'JST')

def calc_parity(data):
    return np.bitwise_xor.reduce([i for i in data])


class OMHacker:
    def __init__(self):
        self._ser = serial.Serial(DEV_NAME, 9600, timeout=0.1)
        self._packet_index = 0
        self._start_dt = None
        self._connected = False

    def __w(self, data):
        self._ser.write(data)
    
    def __r(self, len):
        return self._ser.read(len)

    def connect(self):
        self.__w(b'\x06')
        ret = self.__r(1)
        if ret[0] != 0x86:
            raise Exception('Not connected. Abort.')
        self._connected = True
        self._start_dt = datetime.now(tz=JST)

    def wr(self, data):
        assert self._connected
        assert len(data) == 35
        tmpdt = datetime.now(tz=JST)
        ds = tmpdt - self._start_dt
        ds_int = int((ds.total_seconds()*1e3)%65536)
        ds_b = ds_int.to_bytes(2, 'little')
        pi_b = (self._packet_index % 256).to_bytes(1, 'little')

        pkt_pre = b'\xff' + data + ds_b + pi_b
        parity = calc_parity(pkt_pre)
        pkt = pkt_pre + int(parity).to_bytes(1, 'little')

        self.__w(pkt)
        self._packet_index += 1

        return self.__r(40)

    def set_op_number(self, num):
        assert (0 <= num) and (num < 16)
        mark_0 = (((0b110 << 4) + num) << 5).to_bytes(2, 'little')
        mark_1 = (((num+4)%8) << 5) + (5 - int(num/8))
        data = bytearray([0x03, 0x00, 0x01, 0x0a, 0x00, 0x86, 0x01]) + mark_0
        data += bytearray([0x04, 0x00, 0x00, mark_1]) + bytearray([0]*22)
        return self.wr(data)

    def set_speed(self, speed):
        assert (50 <= speed) and (speed <= 3000)
        data = bytearray([0x03, 0x00, 0x01, 0x0c, 0x00, 0x81, 0x00, 0xc4, 0x01])
        data += speed.to_bytes(2, 'little')
        data += bytearray([0]*3)
        p_check = calc_parity(data[3:])
        data += bytearray([p_check] + [0]*20)
        return self.wr(data)

    def set_accl_time(self, sec, accl=True):
        assert (0.5 <= sec) and (sec <= 15.0)
        data = bytearray([0x03, 0x00, 0x01, 0x0c, 0x00, 0x81, 0x00, 0xc5 if accl else 0xc6, 0x01])
        data += int(sec*10).to_bytes(1, 'little')
        data += bytearray([0]*4)
        p_check = calc_parity(data[3:])
        data += bytearray([p_check] + [0]*20)
        return self.wr(data)

def rep(b):
    return ' '.join([f'{i:02x}' for i in b])

def status_print(pack):
    print(f'{int.from_bytes(pack[7:11], "little", signed=True):5d}',
          '##',
          f'{int.from_bytes(pack[11:15], "little", signed=True):5d}',
          '##',
          ' '.join([f'{d:02d}' for d in pack[15:]]))
    #print(' '.join([f'{d:02d}' for d in pack]))

def main():
    omh = OMHacker()
    omh.connect()
    for i, cmd in enumerate(INIT_CMD):
        d = omh.wr(cmd)

    d = omh.wr(STATUS)
    #d = omh.set_op_number(1)
    #d = omh.wr(STATUS)
    omh.set_speed(1500)
    omh.set_accl_time(15, False)
    omh.set_accl_time(15, True)

    print('MOVING FORWARD')
    omh.wr(MOVE_FWD)
    for i in range(200):
        status_print(omh.wr(STATUS))
        sleep(0.1)

    print('STOPPED')
    omh.wr(STOP)
    for i in range(10):
        status_print(omh.wr(STATUS))
        sleep(0.1)

    print('MOVING BACKWARD')
    omh.wr(MOVE_BKW)
    for i in range(200):
        status_print(omh.wr(STATUS))
        sleep(0.1)
        
    print('STOPPED')
    omh.wr(STOP)
    for i in range(10):
        status_print(omh.wr(STATUS))
        sleep(0.1)


if __name__ == '__main__':
    main()
