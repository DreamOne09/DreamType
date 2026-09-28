"""Windows child ownership. Linux workers install their own parent-death signal."""
import os


def attach(child):
    if os.name!='nt':return None
    import ctypes as c
    from ctypes import wintypes as w
    class Basic(c.Structure):
        _fields_=[('process_time',c.c_longlong),('job_time',c.c_longlong),('flags',w.DWORD),
                  ('min_working',c.c_size_t),('max_working',c.c_size_t),('active',w.DWORD),
                  ('affinity',c.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
    class IO(c.Structure):
        _fields_=[(name,c.c_ulonglong) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class Extended(c.Structure):
        _fields_=[('basic',Basic),('io',IO),('process_memory',c.c_size_t),('job_memory',c.c_size_t),
                  ('peak_process',c.c_size_t),('peak_job',c.c_size_t)]
    kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[c.c_void_p,w.LPCWSTR];kernel.CreateJobObjectW.restype=w.HANDLE
    kernel.SetInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD];kernel.SetInformationJobObject.restype=w.BOOL
    kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];kernel.AssignProcessToJobObject.restype=w.BOOL
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    handle=kernel.CreateJobObjectW(None,None)
    if not handle:raise c.WinError(c.get_last_error())
    try:
        info=Extended();info.basic.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(handle,9,c.byref(info),c.sizeof(info)):raise c.WinError(c.get_last_error())
        if not kernel.AssignProcessToJobObject(handle,w.HANDLE(int(child._handle))):raise c.WinError(c.get_last_error())
    except BaseException:
        kernel.CloseHandle(handle);raise
    return lambda:kernel.CloseHandle(handle)
