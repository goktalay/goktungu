import ctypes
from ctypes import *

from Hvs.datdefs import *


class Rect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]


# 开始跟踪
def StartTrack(device, video_type) -> c_bool:
    """
    :param device:      设备句柄
    :param video_type:  视频类型
    :return:            成功或失败
    """
    func = prefix + "StartTrack"
    return eval(func)(device, video_type)


# 停止跟踪
def StopTrack(device, video_type) -> c_bool:
    """
    :param device:      设备句柄
    :param video_type:  视频类型
    :return:            成功或失败
    """
    func = prefix + "StopTrack"
    return eval(func)(device, video_type)


# 硬件框选跟踪
def SelectRectTrack(device, video_type, video_rect, select_rect) -> c_bool:
    """
    :param device:      设备句柄
    :param video_type:  视频类型
    :param video_rect:  视频窗口大小
    :param select_rect: 目标框选窗口大小
    :return:            成功或失败
    """
    func = prefix + "SelectRectTrack"
    return eval(func)(device, video_type, video_rect, select_rect)


# 启用/禁用通道的跟踪能力
def EnableTrackAbility(device, video_type, enable) -> c_bool:
    """
    :param device:      设备句柄
    :param video_type:  视频类型
    :param enable:      是否启用跟踪功能
    :return:            成功或失败
    """
    func = prefix + "EnableTrackAbility"
    return eval(func)(device, video_type, enable)


# 获取跟踪能力状态
def GetTrackAbilityState(device, video_type, enable) -> c_bool:
    """
    :param device:
    :param video_type:
    :param enable:
    :return:
    """
    func = prefix + "GetTrackAbilityState"
    return eval(func)(device, video_type, enable)


# 获取跟踪模式
def GetTrackMode(device, video_type, mode) -> c_bool:
    """
    :param device:      设备句柄
    :param video_type:  视频类型
    :param mode:        跟踪模式
    :return:            成功或失败
    """
    func = prefix + "GetTrackMode"
    return eval(func)(device, video_type, mode)


# 设置跟踪模式
def SetTrackMode(device, video_type, mode) -> c_bool:
    """
    :param device:      设备句柄
    :param video_type:  视频类型
    :param mode:        跟踪模式
    :return:            成功或失败
    """
    func = prefix + "SetTrackMode"
    return eval(func)(device, video_type, mode)
