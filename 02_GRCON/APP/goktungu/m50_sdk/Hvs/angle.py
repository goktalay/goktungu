from ctypes import *
from Hvs.datdefs import *

# 角度回传事件
Angle_event = CFUNCTYPE(None, c_void_p, c_double, c_double)


# 水平角度定位
def PositionX(device, angle, speed) -> c_bool:
    """
    :param device:  设备句柄
    :param angle:   水平角度
    :param speed:   角度定位速度, speed范围：0~63
    :return:        成功或失败
    """
    func = prefix + "PositionX"
    return eval(func)(device, angle, speed)


# 俯仰角度定位
def PositionY(device, angle, speed) -> c_bool:
    """
    :param device:  设备句柄
    :param angle:   俯仰角度
    :param speed:   角度定位速度, speed范围：0~63
    :return:        成功或失败
    """
    func = prefix + "PositionY"
    return eval(func)(device, angle, speed)


# 水平俯仰角度定位
def PositionXY(device, angle_x, angle_y, speed) -> c_bool:
    """
    :param device:  设备句柄
    :param angle_x: 水平角度
    :param angle_y: 俯仰角度
    :param speed:   角度定位速度, speed范围：0~63
    :return:        成功或失败
    """
    func = prefix + "PositionXY"
    return eval(func)(device, c_double(angle_x), c_double(angle_y), speed)


# 获取水平角度
def GetAngleX(device, angle) -> c_bool:
    """
    :param device:  设备句柄
    :param angle:   水平角度
    :return:        成功或失败
    """
    func = prefix + "GetAngleX"
    return eval(func)(device, byref(angle))


# 获取水平角度
def GetAngleY(device, angle) -> c_bool:
    """
    :param device:  设备句柄
    :param angle:   俯仰角度
    :return:        成功或失败
    """
    func = prefix + "GetAngleY"
    return eval(func)(device, byref(angle))


# 角度回传注册事件
def RegAngleEvent(device, event, this) -> c_bool:
    """
    :param this:
    :param device:  设备句柄
    :param event:   角度回传事件
    :return:        成功或失败
    """
    func = prefix + "RegAngleEvent"
    return eval(func)(device, event, c_void_p(id(this)))
