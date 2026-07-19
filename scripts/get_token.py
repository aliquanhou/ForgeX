"""Extract GitHub token from Windows Credential Manager using ctypes."""
import ctypes
import ctypes.wintypes
import re
import sys

advapi32 = ctypes.windll.advapi32
CRED_TYPE_GENERIC = 1


class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.wintypes.DWORD),
        ("Type", ctypes.wintypes.DWORD),
        ("TargetName", ctypes.wintypes.LPCWSTR),
        ("Comment", ctypes.wintypes.LPCWSTR),
        ("LastWritten", ctypes.wintypes.FILETIME),
        ("CredentialBlobSize", ctypes.wintypes.DWORD),
        ("CredentialBlob", ctypes.wintypes.LPBYTE),
        ("Persist", ctypes.wintypes.DWORD),
        ("AttributeCount", ctypes.wintypes.DWORD),
        ("Attributes", ctypes.wintypes.LPVOID),
        ("TargetAlias", ctypes.wintypes.LPCWSTR),
        ("UserName", ctypes.wintypes.LPCWSTR),
    ]


def get_token():
    target = "gh:github.com:aliquanhou"
    cred_ptr = ctypes.c_void_p()

    result = advapi32.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(cred_ptr))
    if result:
        try:
            cred = ctypes.cast(cred_ptr, ctypes.POINTER(CREDENTIAL)).contents
            print(f"DEBUG: blob_size={cred.CredentialBlobSize}", file=sys.stderr)
            if cred.CredentialBlobSize > 0:
                raw = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
                print(f"DEBUG: raw_hex={raw.hex()}", file=sys.stderr)
                text = raw.decode("utf-8", errors="replace")
                clean = re.sub(r'[^a-zA-Z0-9_\-]', '', text)
                return clean
        finally:
            advapi32.CredFree(cred_ptr)
    else:
        err = ctypes.windll.kernel32.GetLastError()
        print(f"DEBUG: CredRead failed with error {err}", file=sys.stderr)
    return None


if __name__ == "__main__":
    token = get_token()
    if token:
        print(token)
    else:
        print("NULL", file=sys.stderr)
