"""Windows HID access for DualSense / DualSense Edge via hid.dll + setupapi."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

from .protocol import (
    FEATURE_CALIBRATION,
    FEATURE_CALIBRATION_LEN,
    PID_DUALSENSE_EDGE,
    SONY_PIDS,
    SONY_VID,
)

setupapi = ctypes.WinDLL("setupapi")
hid = ctypes.WinDLL("hid")
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
ERROR_IO_PENDING = 997
ERROR_IO_INCOMPLETE = 996
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
INFINITE = 0xFFFFFFFF


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.POINTER(ctypes.c_ulong)),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.ULONG),
        ("VendorID", wintypes.USHORT),
        ("ProductID", wintypes.USHORT),
        ("VersionNumber", wintypes.USHORT),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wintypes.USHORT),
        ("UsagePage", wintypes.USHORT),
        ("InputReportByteLength", wintypes.USHORT),
        ("OutputReportByteLength", wintypes.USHORT),
        ("FeatureReportByteLength", wintypes.USHORT),
        ("Reserved", wintypes.USHORT * 17),
        ("NumberLinkCollectionNodes", wintypes.USHORT),
        ("NumberInputButtonCaps", wintypes.USHORT),
        ("NumberInputValueCaps", wintypes.USHORT),
        ("NumberInputDataIndices", wintypes.USHORT),
        ("NumberOutputButtonCaps", wintypes.USHORT),
        ("NumberOutputValueCaps", wintypes.USHORT),
        ("NumberOutputDataIndices", wintypes.USHORT),
        ("NumberFeatureButtonCaps", wintypes.USHORT),
        ("NumberFeatureValueCaps", wintypes.USHORT),
        ("NumberFeatureDataIndices", wintypes.USHORT),
    ]


class _OverlappedUnion(ctypes.Union):
    _fields_ = [
        ("Offset", wintypes.DWORD),
        ("Pointer", ctypes.c_void_p),
    ]


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("u", _OverlappedUnion),
        ("hEvent", wintypes.HANDLE),
    ]


hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = wintypes.BOOL
hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_GetPreparsedData.restype = wintypes.BOOL
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidD_FreePreparsedData.restype = wintypes.BOOL
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = ctypes.c_int
hid.HidD_GetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
hid.HidD_GetFeature.restype = wintypes.BOOL
hid.HidD_SetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
hid.HidD_SetFeature.restype = wintypes.BOOL
hid.HidD_SetOutputReport.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
hid.HidD_SetOutputReport.restype = wintypes.BOOL
hid.HidD_SetNumInputBuffers.argtypes = [wintypes.HANDLE, wintypes.ULONG]
hid.HidD_SetNumInputBuffers.restype = wintypes.BOOL

setupapi.SetupDiGetClassDevsW.argtypes = [
    ctypes.POINTER(GUID),
    wintypes.LPCWSTR,
    wintypes.HWND,
    wintypes.DWORD,
]
setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.POINTER(GUID),
    wintypes.DWORD,
    ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p,
]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.ReadFile.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(OVERLAPPED),
]
kernel32.ReadFile.restype = wintypes.BOOL
kernel32.WriteFile.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(OVERLAPPED),
]
kernel32.WriteFile.restype = wintypes.BOOL
kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.GetOverlappedResult.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(OVERLAPPED),
    ctypes.POINTER(wintypes.DWORD),
    wintypes.BOOL,
]
kernel32.GetOverlappedResult.restype = wintypes.BOOL
kernel32.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED)]
kernel32.CancelIoEx.restype = wintypes.BOOL
kernel32.ResetEvent.argtypes = [wintypes.HANDLE]
kernel32.ResetEvent.restype = wintypes.BOOL


@dataclass
class HidInfo:
    path: str
    vendor_id: int
    product_id: int
    version: int
    usage_page: int
    usage: int
    input_len: int
    output_len: int
    feature_len: int
    is_edge: bool

    @property
    def bluetooth(self) -> bool:
        # USB DualSense input report is 64. BT enhanced is 78. Audio ifaces differ.
        return self.input_len >= 78

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "vid": f"{self.vendor_id:04X}",
            "pid": f"{self.product_id:04X}",
            "version": self.version,
            "usage_page": self.usage_page,
            "usage": self.usage,
            "input_len": self.input_len,
            "output_len": self.output_len,
            "is_edge": self.is_edge,
            "link": "bluetooth" if self.bluetooth else "usb",
        }


def _hid_guid() -> GUID:
    g = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(g))
    return g


def _open_path(path: str, write: bool = True) -> int:
    access = GENERIC_READ | (GENERIC_WRITE if write else 0)
    handle = kernel32.CreateFileW(
        path,
        access,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_OVERLAPPED,
        None,
    )
    if handle == INVALID_HANDLE_VALUE or handle is None:
        return 0
    return handle


def _caps(handle: int) -> HIDP_CAPS | None:
    prep = ctypes.c_void_p()
    if not hid.HidD_GetPreparsedData(handle, ctypes.byref(prep)):
        return None
    try:
        caps = HIDP_CAPS()
        if hid.HidP_GetCaps(prep, ctypes.byref(caps)) != 0x00110000:  # HIDP_STATUS_SUCCESS
            # Some stacks still fill caps; accept if lengths look sane
            if caps.InputReportByteLength == 0:
                return None
        return caps
    finally:
        hid.HidD_FreePreparsedData(prep)


def enumerate_dualsense() -> list[HidInfo]:
    guid = _hid_guid()
    devs = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    )
    if devs == INVALID_HANDLE_VALUE:
        return []
    found: list[HidInfo] = []
    try:
        index = 0
        while True:
            iface = SP_DEVICE_INTERFACE_DATA()
            iface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(
                devs, None, ctypes.byref(guid), index, ctypes.byref(iface)
            ):
                break
            index += 1
            needed = wintypes.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(
                devs, ctypes.byref(iface), None, 0, ctypes.byref(needed), None
            )
            if needed.value == 0:
                continue
            buf = ctypes.create_string_buffer(needed.value)
            # SP_DEVICE_INTERFACE_DETAIL_DATA_W.cbSize is 8 on 64-bit Windows
            ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(
                devs, ctypes.byref(iface), buf, needed, None, None
            ):
                continue
            # DevicePath sits after cbSize. 64-bit Windows uses cbSize=8;
            # try offset 4 first, then 8 if the string looks wrong.
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
            if not path.startswith("\\\\"):
                path = ctypes.wstring_at(ctypes.addressof(buf) + 8)
            handle = _open_path(path, write=False)
            if not handle:
                continue
            try:
                attrs = HIDD_ATTRIBUTES()
                attrs.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
                if not hid.HidD_GetAttributes(handle, ctypes.byref(attrs)):
                    continue
                if attrs.VendorID != SONY_VID or attrs.ProductID not in SONY_PIDS:
                    continue
                caps = _caps(handle)
                if not caps:
                    continue
                # Gamepad collection: Generic Desktop (0x01) Gamepad (0x05)
                # Some firmware reports Joystick (0x04). Accept both, skip audio.
                if caps.UsagePage != 0x01 or caps.Usage not in (0x04, 0x05):
                    continue
                if caps.InputReportByteLength < 10:
                    continue
                found.append(
                    HidInfo(
                        path=path,
                        vendor_id=attrs.VendorID,
                        product_id=attrs.ProductID,
                        version=attrs.VersionNumber,
                        usage_page=caps.UsagePage,
                        usage=caps.Usage,
                        input_len=caps.InputReportByteLength,
                        output_len=caps.OutputReportByteLength,
                        feature_len=caps.FeatureReportByteLength,
                        is_edge=attrs.ProductID == PID_DUALSENSE_EDGE,
                    )
                )
            finally:
                kernel32.CloseHandle(handle)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(devs)
    # Prefer the interface with the largest input report (full BT / USB gamepad)
    found.sort(key=lambda d: (d.is_edge, d.input_len, d.output_len), reverse=True)
    return found


class DualSenseDevice:
    def __init__(self, info: HidInfo):
        self.info = info
        self.handle = 0
        self._read_event = 0
        self._write_event = 0
        self._read_ov = OVERLAPPED()
        self._write_ov = OVERLAPPED()
        self._inbuf = ctypes.create_string_buffer(max(info.input_len, 128))
        self.connected = False
        self._read_pending = False
        self._read_n = wintypes.DWORD(0)

    def open(self) -> None:
        self.close()
        handle = _open_path(self.info.path, write=True)
        if not handle:
            handle = _open_path(self.info.path, write=False)
        if not handle:
            raise OSError(f"Could not open {self.info.path}")
        self.handle = handle
        hid.HidD_SetNumInputBuffers(handle, 16)
        self._read_event = kernel32.CreateEventW(None, True, False, None)
        self._write_event = kernel32.CreateEventW(None, True, False, None)
        self.connected = True
        if self.info.bluetooth:
            self._enable_bt_full_report()

    def _enable_bt_full_report(self) -> None:
        """Reading feature 0x05 switches BT from tiny 0x01 reports to 0x31."""
        buf = ctypes.create_string_buffer(FEATURE_CALIBRATION_LEN)
        buf[0] = FEATURE_CALIBRATION
        hid.HidD_GetFeature(self.handle, buf, FEATURE_CALIBRATION_LEN)

    def close(self) -> None:
        self.connected = False
        self._read_pending = False
        if self.handle:
            try:
                kernel32.CancelIoEx(self.handle, None)
            except Exception:
                pass
            kernel32.CloseHandle(self.handle)
            self.handle = 0
        if self._read_event:
            kernel32.CloseHandle(self._read_event)
            self._read_event = 0
        if self._write_event:
            kernel32.CloseHandle(self._write_event)
            self._write_event = 0

    def _arm_read(self) -> bool:
        kernel32.ResetEvent(self._read_event)
        self._read_ov = OVERLAPPED()
        self._read_ov.hEvent = self._read_event
        self._read_n = wintypes.DWORD(0)
        ok = kernel32.ReadFile(
            self.handle,
            self._inbuf,
            self.info.input_len,
            ctypes.byref(self._read_n),
            ctypes.byref(self._read_ov),
        )
        if ok:
            self._read_pending = False
            return True
        err = ctypes.get_last_error()
        if err == ERROR_IO_PENDING:
            self._read_pending = True
            return True
        self.connected = False
        self._read_pending = False
        return False

    def read(self, timeout_ms: int = 4) -> bytes | None:
        if not self.handle:
            return None
        if not self._read_pending:
            if not self._arm_read():
                return None
            if not self._read_pending:
                n = self._read_n.value
                return bytes(self._inbuf.raw[:n]) if n else None
        wait = kernel32.WaitForSingleObject(self._read_event, timeout_ms)
        if wait == WAIT_TIMEOUT:
            return None
        n = wintypes.DWORD(0)
        if not kernel32.GetOverlappedResult(
            self.handle, ctypes.byref(self._read_ov), ctypes.byref(n), False
        ):
            self._read_pending = False
            return None
        self._read_pending = False
        if n.value <= 0:
            return None
        return bytes(self._inbuf.raw[: n.value])

    def write(self, report: bytes) -> bool:
        if not self.handle or not report:
            return False
        # Prefer WriteFile; fall back to HidD_SetOutputReport.
        kernel32.ResetEvent(self._write_event)
        ov = OVERLAPPED()
        ov.hEvent = self._write_event
        size = len(report)
        cap = self.info.output_len or 0
        if cap in (48, 64, 78) and cap > size:
            size = cap
        raw = bytes(report) + bytes(size - len(report))
        buf = ctypes.create_string_buffer(raw, size)
        n = wintypes.DWORD(0)
        ok = kernel32.WriteFile(self.handle, buf, size, ctypes.byref(n), ctypes.byref(ov))
        if not ok:
            err = ctypes.get_last_error()
            if err == ERROR_IO_PENDING:
                wait = kernel32.WaitForSingleObject(self._write_event, 4)
                if wait == WAIT_OBJECT_0 and kernel32.GetOverlappedResult(
                    self.handle, ctypes.byref(ov), ctypes.byref(n), False
                ):
                    return n.value > 0
            return bool(hid.HidD_SetOutputReport(self.handle, buf, size))
        return True

    def get_feature(self, report_id: int, length: int) -> bytes | None:
        if not self.handle:
            return None
        buf = ctypes.create_string_buffer(length)
        buf[0] = report_id
        if hid.HidD_GetFeature(self.handle, buf, length):
            return bytes(buf)
        return None
