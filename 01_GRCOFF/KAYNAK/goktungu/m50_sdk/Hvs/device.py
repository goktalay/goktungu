from ctypes import *
from Hvs.datdefs import *

# 连接异步结果回调
Connect_cb = CFUNCTYPE(None, c_void_p, c_int)


# 创建设备句柄
def CreateDevice(device, length, error) -> c_void_p:
    """
    :param device:  设备类型
    :param length:  错误信息缓冲区大小
    :param error:   失败时返回错误信息
    :return:        返回设备句柄
    """
    func = prefix + "CreateDevice"
    return eval(func)(device, length, error)


# 释放设备句柄
def ReleaseDevice(handle) -> c_bool:
    """
    :param handle:  设备句柄
    :return:        成功返回 true, 失败返回 false
    """
    func = prefix + "ReleaseDevice"
    return eval(func)(byref(c_int(handle)))


# 同步连接设备
def Connect(handle, ip, port, uid, pwd, timeout) -> c_bool:
    """
    :param handle:  设备句柄
    :param ip:      设备IP
    :param port:    设备端口
    :param uid:     设备帐号
    :param pwd:     设备密码
    :param timeout: 连接超时时间
    :return:        成功返回 true, 失败返回 false
    """
    func = prefix + "Connect"
    return eval(func)(handle, ip, port, uid, pwd, timeout)


# 导步连接设备
def ConnectEx(handle, ip, port, uid, pwd, timeout, callback) -> c_bool:
    """
    :param handle:      设备句柄
    :param ip:          设备IP
    :param port:        设备端口
    :param uid:         设备帐号
    :param pwd:         设备密码
    :param timeout:     连接超时时间
    :param callback:    异步结果回调函数
    :return:            成功返回 true, 失败返回 false
    """
    func = prefix + "ConnectEx"
    return eval(func)(handle, ip, port, uid, pwd, timeout, callback, None)


# 断开连接
def DisConnect(handle) -> c_bool:
    """
    :param handle:  设备句柄
    :return:        成功返回 true, 失败返回 false
    """
    func = prefix + "DisConnect"
    return eval(func)(handle)


# 是否连接
def IsConnected(handle) -> c_bool:
    """
    :param handle:  设备句柄
    :return:        成功返回 true, 失败返回 false
    """
    func = prefix + "IsConnected"
    return eval(func)(handle)


# 获取错误
def GetLastErrMsg(handle) -> c_char_p:
    """
    :param handle:  设备句柄
    :return:        错误信息
    """
    func = prefix + "GetLastErrMsg"
    return eval(func)(handle)


# 获取错误句柄
def PGetLastErrCode(handle) -> c_int:
    """
    :param handle:  设备句柄
    :return:        错误ID
    """
    func = prefix + "PGetLastErrMsg"
    return eval(func)(handle)


# GOKTUNGU eklentisi: cevre birimi (pusula/GPS/hava) verisi.
# HVS_GetExternDeviceInfo(DevHandle h, ExternDevice_e type, ExternData_CB cb, PVoid user)
# ExternData_CB: void STDCALL (PVoid user, ExternDevice_e type, PVoid data, int size)
# v2.4.216 (GOKTUNGU): STDCALL yalniz Windows'ta anlamlidir; Linux'ta cdecl.
import sys as _sys
ExternData_CB = (WINFUNCTYPE if _sys.platform.startswith("win") else CFUNCTYPE)(None, c_void_p, c_int, c_void_p, c_int)


class GPSData_t(Structure):
    _fields_ = [("lon", c_double), ("lat", c_double), ("alt", c_double)]


class CompassData_t(Structure):
    _fields_ = [("angleX", c_double), ("angleY", c_double), ("angleZ", c_double)]


def GetExternDeviceInfo(handle, ext_type, cb, user) -> c_bool:
    """
    :param handle:    设备句柄
    :param ext_type:  0 pusula, 1 GPS, 2 hava
    :param cb:        ExternData_CB ornegi (cagiran taraf referansi tutmali)
    :param user:      c_void_p
    """
    func = prefix + "GetExternDeviceInfo"
    return eval(func)(handle, ext_type, cb, user)


# 设置超时时间
def SetRequestTimeout(handle, timeout) -> c_bool:
    """
    :param handle:      设备句柄
    :param timeout:     超时时间
    :return:            成功返回 true, 失败返回 false
    """
    func = prefix + "SetRequestTimeout"
    return eval(func)(handle, timeout)
