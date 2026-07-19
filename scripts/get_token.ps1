Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Explicit, CharSet = CharSet.Unicode)]
struct CRED {
    [FieldOffset(0)] public int Flags;
    [FieldOffset(4)] public int Type;
    [FieldOffset(8)] public IntPtr TargetName;
    [FieldOffset(16)] public IntPtr Comment;
    [FieldOffset(24)] public long LastWritten;
    [FieldOffset(32)] public int CredentialBlobSize;
    [FieldOffset(40)] public IntPtr CredentialBlob;
    [FieldOffset(48)] public int Persist;
    [FieldOffset(52)] public int AttributeCount;
    [FieldOffset(56)] public IntPtr Attributes;
    [FieldOffset(64)] public IntPtr TargetAlias;
    [FieldOffset(72)] public IntPtr UserName;
}

public class CredWin {
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode)]
    public static extern bool CredRead(string target, int type, int reserved, out IntPtr credential);
    [DllImport("advapi32.dll")]
    public static extern bool CredFree(IntPtr cred);

    public static string Read(string target) {
        IntPtr p;
        if (CredRead(target, 1, 0, out p)) {
            try {
                CRED c = (CRED)Marshal.PtrToStructure(p, typeof(CRED));
                if (c.CredentialBlobSize > 0 && c.CredentialBlob != IntPtr.Zero) {
                    byte[] bytes = new byte[c.CredentialBlobSize];
                    Marshal.Copy(c.CredentialBlob, bytes, 0, c.CredentialBlobSize);
                    return System.Text.Encoding.UTF8.GetString(bytes).TrimEnd(new char[] {'\0', '\r', '\n', ' '});
                }
            } finally { CredFree(p); }
        }
        return null;
    }
}
"@

$token = [CredWin]::Read("gh:github.com:aliquanhou")
if ($token) {
    $clean = [regex]::Replace($token, '[^a-zA-Z0-9_\-]', '')
    Write-Host $clean
}
