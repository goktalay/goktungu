from ctypes import *

from Hvs.datdefs import *


RealData_event = CFUNCTYPE(None, c_void_p, c_int, c_int, POINTER(c_ubyte), c_ulong)


# 播放实时视频
def PlayVideo(device, window, video_type, stream, port, play_id) -> c_bool:
    """
    :param device:      设备句柄
    :param window:      视频显示窗口句柄
    :param video_type:  视频类型
    :param stream:      视频流
    :param port:        端口号，0 使用SDK播放视频，非0 使用Hik组件播放视频
    :param play_id:     返回视频播放ID，全局唯一
    :return:            成功返回true，失败返回false
    """
    func = prefix + "PlayVideo"
    return eval(func)(device, window, video_type, stream, port, play_id)


def StopVideoPlay(device, play_id) -> c_bool:
    """
    :param device:   设备句柄
    :param play_id:  视频播放ID
    :return:         成功返回true，失败返回false
    """
    func = prefix + "StopVideoPlay"
    return eval(func)(device, play_id)


def RegRealDataEvent(device, event, this) -> c_bool:
    """
    :param this:
    :param device:  设备句柄
    :param event:   实时视频流数据事件
    :return:        成功或失败
    """
    func = prefix + "RegDataEvent"
    return eval(func)(device, event, c_void_p(id(this)))