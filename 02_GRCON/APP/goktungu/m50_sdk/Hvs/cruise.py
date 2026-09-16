from ctypes import *

from Hvs.datdefs import *


# 扫描控制
def ControlScan(device, scan_type, ctrl_type, path) -> c_bool:
    """
    :param device:      设备句柄
    :param scan_type:   扫描类型
    :param ctrl_type:   控制类型
    :param path:        第x条扫描线
    :return:            成功或失败
    """
    func = prefix + "ControlScan"
    return eval(func)(device, scan_type, ctrl_type, path)


# 获取扫描状态
def GetScanState(device, state) -> c_bool:
    """
    :param device:      设备句柄
    :param state:       扫描状态
    :return:            成功或失败
    """
    func = prefix + "GetScanState"
    return eval(func)(device, state)


# 设置巡航路径预置位信息
def SetCruisePath(device, path, presets, count) -> c_bool:
    """
    :param device:      设备句柄
    :param path:        第x条扫描线
    :param presets:     巡航路径预置位信息
    :param count:       巡航路径预置位数量
    :return:            成功或失败
    """
    func = prefix + "SetCruisePath"
    return eval(func)(device, path, presets, count)
