from ctypes import *
from Hvs.datdefs import *


# 转台控制
def ControlMove(device, ptz_type, move, speed, speedV, video_type) -> c_bool:
    """
    :param device:      设备句柄
    :param ptz_type:    控制类型
    :param move:        是否转动
    :param speed:       取值范围：1-63
    :param speedV:      俯仰速度：1-63
    :param video_type:  VT_IRD:热像  VT_LIGHT：可见光(单IP设备使用)
    :return:            成功或失败
    """
    func = prefix + "ControlMove"
    return eval(func)(device, ptz_type, move, speed, speedV, video_type)


# 镜头控制
def CameraMove(device, camera_type, move, video_type) -> c_bool:
    """
    :param device:      设备句柄
    :param camera_type: 控制类型
    :param move:        是否转动
    :param video_type:  VT_IRD:热像  VT_LIGHT：可见光(单IP设备使用)
    :return:            成功或失败
    """
    func = prefix + "CameraMove"
    return eval(func)(device, camera_type, move, video_type)
