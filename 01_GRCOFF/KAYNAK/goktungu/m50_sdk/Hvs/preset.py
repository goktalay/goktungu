import ctypes
from ctypes import *

from Hvs.datdefs import *


class PresetInfo_t(ctypes.Structure):
    _fields_ = [
        ("preset", ctypes.c_int),
        ("name", ctypes.c_char * 100)
    ]


# 设置预置位
def SetPreset(device, preset, name, speed) -> c_bool:
    """
    :param device:  设备句柄
    :param preset:  预置位编号
    :param name:    预置位名称
    :param speed:   预置位速度
    :return:        成功或失败
    """
    func = prefix + "SetPreset"
    return eval(func)(device, preset, c_char_p(name), speed)


# 调用预置位
def CallPreset(device, preset) -> c_bool:
    """
    :param device:   设备句柄
    :param preset:   预置位编号
    :return:         成功或失败
    """
    func = prefix + "CallPreset"
    return eval(func)(device, preset)


# 清除预置位
def ClearPreset(device, preset) -> c_bool:
    """
    :param device:   设备句柄
    :param preset:   预置位编号
    :return:         成功或失败
    """
    func = prefix + "ClearPreset"
    return eval(func)(device, preset)


# 清除所有预置位
def ClearAllPreset(device) -> c_bool:
    """
    :param device:   设备句柄
    :return:         成功或失败
    """
    func = prefix + "ClearAllPreset"
    return eval(func)(device)


# 获取所有预置位
def GetPresets(device, info, count) -> c_bool:
    """
    :param device:  设备句柄
    :param info:    预置位信息列表
    :param count:   预置位数量
    :return:        成功或失败
    """
    func = prefix + "GetPresets"
    return eval(func)(device, byref(info), byref(count))


# 释放获取的预置位信息
def FreePresets(device, info, count) -> c_bool:
    """
    :param device:  设备句柄
    :param info:    预置位信息列表
    :param count:   预置位数量
    :return:        成功或失败
    """
    func = prefix + "FreePresets"
    return eval(func)(device, byref(info), count)
