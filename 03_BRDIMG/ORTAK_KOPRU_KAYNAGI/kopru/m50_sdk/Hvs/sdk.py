from ctypes import c_bool, create_string_buffer

import Hvs.ptz as ptz
import Hvs.angle as angle
import Hvs.track as track
import Hvs.device as device
import Hvs.preset as preset
import Hvs.video as video
import Hvs.cruise as cruise


class IPC_device(object):
    __handle__ = None
    __error__ = None
    __length__ = None

    def __init__(self, dev):
        self.__length__ = 1024
        self.__handle__ = device.CreateDevice(dev.value, self.__length__, self.__error__)
        pass

    def __del__(self):
        if device.IsConnected(self.__handle__):
            device.DisConnect(self.__handle__)
        device.ReleaseDevice(self.__handle__)

    def Connect(self, ip, port, uid, pwd, timeout) -> c_bool:
        return device.Connect(self.__handle__, ip, port, uid, pwd, timeout)

    def ConnectEx(self, ip, port, uid, pwd, timeout, cb) -> c_bool:
        return device.ConnectEx(self.__handle__, ip, port, uid, pwd, timeout, cb)

    def GetAngleX(self, x):
        return angle.GetAngleX(self.__handle__, x)

    def GetAngleY(self, y):
        return angle.GetAngleY(self.__handle__, y)

    def DisConnect(self):
        return device.DisConnect(self.__handle__)

    def IsConnected(self):
        return device.IsConnected(self.__handle__)

    def ControlMove(self, ptz_type, move, speed, speedV):
        return ptz.ControlMove(self.__handle__, ptz_type.value, move, speed, speedV, None)

    def CameraMove(self, camera_type, move, video_type):
        return ptz.CameraMove(self.__handle__, camera_type.value, move, video_type.value)

    def PositionXY(self, angle_x, angle_y, speed):
        return angle.PositionXY(self.__handle__, angle_x, angle_y, speed)

    def RegAngleEvent(self, event, this):
        return angle.RegAngleEvent(self.__handle__, event, this)

    def StartTrack(self, video_type):
        return track.StartTrack(self.__handle__, video_type.value)

    def StopTrack(self, video_type):
        return track.StopTrack(self.__handle__, video_type.value)

    def SelectRectTrack(self, video_type, video_rect, select_rect) -> c_bool:
        return track.SelectRectTrack(self.__handle__, video_type.value, video_rect, select_rect)

    def GetTrackMode(self, video_type, mode):
        return track.GetTrackMode(self.__handle__, video_type.value, mode.value)

    def SetTrackMode(self, video_type, mode):
        return track.SetTrackMode(self.__handle__, video_type.value, mode.value)

    def GetTrackAbilityState(self, video_type, enable):
        return track.GetTrackAbilityState(self.__handle__, video_type.value, enable)

    def EnableTrackAbility(self, video_type, enable):
        return track.EnableTrackAbility(self.__handle__, video_type.value, enable)

    def GetPresets(self, info, count):
        return preset.GetPresets(self.__handle__, info, count)

    def FreePresets(self, info, count):
        return preset.FreePresets(self.__handle__, info, count)

    def SetPreset(self, preset_number, name, speed):
        return preset.SetPreset(self.__handle__, preset_number, name, speed)

    def CallPreset(self, preset_number):
        return preset.CallPreset(self.__handle__, preset_number)

    def ClearPreset(self, preset_number):
        return preset.ClearPreset(self.__handle__, preset_number)

    def ClearAllPreset(self):
        return preset.ClearAllPreset(self.__handle__)

    def PlayVideo(self, window, video_type, stream, port, play_id):
        return video.PlayVideo(self.__handle__, window, video_type.value, stream, port, play_id)

    def StopVideoPlay(self, play_id):
        return video.StopVideoPlay(self.__handle__, play_id)

    def RegRealDataEvent(self, event, this):
        return video.RegRealDataEvent(self.__handle__, event, this)

    def GetRtspUrl(self, video_type, stream=0):
        """GOKTUNGU eklentisi: cihazin kendi yayinladigi RTSP adresini
        SDK'dan okur (operator elle girmek zorunda kalmaz). Basarisizsa
        None doner; cagiran yer eski (elle girilen) adrese duser."""
        boyut = 256
        arabellek = create_string_buffer(boyut)
        basarili = video.GetRtspUrl(self.__handle__, video_type.value, stream,
                                    boyut, arabellek)
        if not basarili:
            return None
        try:
            return arabellek.value.decode("utf-8", errors="replace").strip() or None
        except Exception:
            return None

    def ControlScan(self, scan_type, ctrl_type, path):
        return cruise.ControlScan(self.__handle__, scan_type.value, ctrl_type.value, path)