import ctypes
import time
from ctypes import wintypes
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass

# --- 1. 加载 user32.dll ---
user32 = ctypes.WinDLL('user32', use_last_error=True)

# --- 2. 定义 WinAPI 函数签名 ---
# GetForegroundWindow() -> 返回 HWND
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND

# GetWindowTextW: 获取窗口标题
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

# GetClassNameW: 获取类名
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int

# GetWindowThreadProcessId: 获取窗口所属进程ID
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

# 加载 kernel32.dll
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# OpenProcess: 打开一个现有进程对象
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE

# GetModuleFileNameExW: 获取进程可执行模块的文件名
psapi = ctypes.WinDLL('psapi', use_last_error=True)
psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
psapi.GetModuleFileNameExW.restype = wintypes.DWORD

# CloseHandle: 关闭打开的句柄
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


@dataclass
class WindowInfo:
    """
    窗口信息数据类
    
    Attributes:
        hwnd: 窗口句柄
        title: 窗口标题
        class_name: 窗口类名
    """
    hwnd: wintypes.HWND
    title: str
    class_name: str


@dataclass
class ExecutableInfo(WindowInfo):
    """
    可执行文件信息数据类，继承自WindowInfo
    
    Attributes:
        hwnd: 窗口句柄
        title: 窗口标题
        class_name: 窗口类名
        exe_path: 可执行文件路径
        directory: 可执行文件所在目录
    """
    exe_path: str
    directory: str

def initialize_folders(folder_names: list[str]):
    for folder_name in folder_names:
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)


# --- 3. 主函数 ---
def get_foreground_window_info() -> Optional[WindowInfo]:
    """
    获取前台窗口信息
    
    Returns:
        WindowInfo: 包含窗口信息的数据类实例
        如果没有找到前台窗口则返回 None
    """
    # 获取最前窗口句柄
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    # 获取窗口标题（最多 256 字符）
    length = 256
    title = ctypes.create_unicode_buffer(length)
    user32.GetWindowTextW(hwnd, title, length)
    
    # 获取类名
    class_name = ctypes.create_unicode_buffer(length)
    user32.GetClassNameW(hwnd, class_name, length)

    return WindowInfo(
        hwnd=hwnd,
        title=title.value,
        class_name=class_name.value
    )


def get_process_executable_path(process_id: int) -> Optional[str]:
    """
    根据进程ID获取可执行程序的完整路径
    
    Args:
        process_id (int): 进程ID
        
    Returns:
        str: 可执行程序的完整路径，如果失败则返回None
    """
    # 打开进程
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    process_handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, process_id)
    
    if not process_handle:
        return None
    
    try:
        # 获取可执行文件路径
        length = 260
        filepath = ctypes.create_unicode_buffer(length)
        psapi.GetModuleFileNameExW(process_handle, None, filepath, length)
        
        return filepath.value
    finally:
        # 关闭进程句柄
        kernel32.CloseHandle(process_handle)


def get_foreground_window_executable_info() -> Optional[ExecutableInfo]:
    """
    获取前台窗口所属进程的可执行程序路径和目录位置
    
    Returns:
        ExecutableInfo: 包含窗口信息和可执行文件信息的数据类实例
        如果没有找到前台窗口或无法获取进程信息则返回 None
    """
    # 获取最前窗口句柄
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    # 获取进程ID
    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    
    if not process_id.value:
        return None
    
    # 获取可执行文件路径
    exe_path = get_process_executable_path(process_id.value)
    if not exe_path:
        return None
    
    # 获取目录位置
    directory = os.path.dirname(exe_path)
    
    # 获取窗口信息
    length = 256
    title = ctypes.create_unicode_buffer(length)
    user32.GetWindowTextW(hwnd, title, length)
    
    class_name = ctypes.create_unicode_buffer(length)
    user32.GetClassNameW(hwnd, class_name, length)

    return ExecutableInfo(
        hwnd=hwnd,
        title=title.value,
        class_name=class_name.value,
        exe_path=exe_path,
        directory=directory
    )
