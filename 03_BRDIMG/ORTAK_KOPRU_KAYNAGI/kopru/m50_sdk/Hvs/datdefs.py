import os
from enum import Enum
from ctypes import CDLL

# DUZELTME (GOKTUNGU): uretici demo kodu `os.getcwd() + r'\..\bin'`
# kullaniyordu -- yalniz kendi demo klasor duzeninde (calisma dizini
# DemoPy/ iken bin/ onun bir ustunun kardesi) dogru sonuc verir. GRCOFF
# Merkez ve GOKTUNGU Kopru surecleri BASKA bir dizinden calistigi icin
# bu, yanlis yola (ornegin `...\Merkez\..\bin`) cikip "WinError 2"
# aratiyordu. Bunun yerine bu dosyanin KENDI konumundan (Hvs/'in bir
# ust dizini olan m50_sdk/bin) hesaplanir -- calisma dizininden bagimsiz.
dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bin')
try:
    os.add_dll_directory(dir)
except (AttributeError, FileNotFoundError, OSError):
    # `_sdk_yukle()` (m50_hvs.py) zaten dogru dizini eklemis olabilir;
    # burada ikinci kez eklemenin basarisiz olmasi ölümcül degildir.
    pass
sdk = CDLL(r'HVideoSdk.dll')

prefix = "sdk.HVS_"


# 设备类型
class DeviceType_e(Enum):
    DEVICE_HIK  = 0     # 海康协议
    DEVICE_DH   = 1     # 大华协议
    DEVICE_HPWS = 6     # 和普协议
    DEVICE_GB   = 8     # 国标协议


# 视频类型
class VideoType_e(Enum):
    VT_IRD   = 1    # 热成像
    VT_LIGHT = 0    # 可见光


# 云台控制类型
class PtzControlType_e(Enum):
    PCT_STATIC     = 0    # 云台静止
    PCT_UP         = 1    # 云台上仰
    PCT_DOWN       = 2    # 云台下俯
    PCT_LEFT       = 3    # 云台左转
    PCT_RIGHT      = 4    # 云台右转
    PCT_LEFT_UP    = 5    # 云台上仰和左转
    PCT_RIGHT_UP   = 6    # 云台上仰和右转
    PCT_LEFT_DOWN  = 7    # 云台下俯和左转
    PCT_RIGHT_DOWN = 8    # 云台下俯和右转
    PCT_AUTO       = 9    # 云台以SS的速度左右自动扫描


# 转台电机类型
class PtzType_t(Enum):
    PT_PtzV = 0  # 俯仰电机
    PT_PtzH = 1  # 水平电机


# 云台镜头控制类型
class CameraType_e(Enum):
    CCT_ZOOM_IN     = 1	  # 焦距以速度SS变大(倍率变大)
    CCT_ZOOM_OUT    = 2   # 焦距以速度SS变小(倍率变小)
    CCT_FOCUS_NEAR  = 3   # 焦点以速度SS前调
    CCT_FOCUS_FAR   = 4	  # 焦点以速度SS后调
    CCT_IRIS_OPEN   = 5   # 光圈以速度SS扩大
    CCT_IRIS_CLOSE	= 6   # 光圈以速度SS缩小


# 跟踪模式
class TrackMode_e(Enum):
    TRACK_AIR_SEMIAUTO     = 0    # 对空半自动
    TRACK_AIR_AUTO         = 1    # 对空自动
    TRACK_GROUND_MANUAL    = 2    # 对地手动
    TRACK_GROUND_SEMIAUTO  = 3    # 对地半自动
    TRACK_GROUND_AUTO      = 4    # 对地自动


# 扫描类型
class ScanType_e(Enum):
    SCAN_TYPE_NONE       = 0  # 无扫描
    SCAN_TYPE_PRESET     = 1  # 预置位扫描
    SCAN_TYPE_HORIZONTAL = 2  # 水平扫描
    SCAN_TYPE_PANORAMA   = 3  # 全景扫描
    SCAN_TYPE_FAN        = 4  # 苹果皮扫描, 扇扫
    SCAN_TYPE_FRAME      = 5  # 帧扫描
    SCAN_TYPE_PATTERN    = 6  # 花样扫描
    SCAN_TYPE_VERTICAL   = 7  # 垂直扫描


# 扫描控制类型
class ScanCtrlType_e(Enum):
    SCT_START     = 0  # 开始
    SCT_STOP      = 1  # 停止
    SCT_PAUSE     = 2  # 暂停
    SCT_CONTINUE  = 3  # 继续
