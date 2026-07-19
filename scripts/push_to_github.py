"""
Push ForgeX to GitHub via API — reads token from Windows Credential Manager via PowerShell.
"""

import base64
import json
import re
import subprocess
import sys
from pathlib import Path

import httpx


def get_github_token():
    """Extract token via Python ctypes — direct Windows Credential Manager access."""
    import ctypes
    import ctypes.wintypes

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

    target = "gh:github.com:aliquanhou"
    cred_ptr = ctypes.c_void_p()

    if advapi32.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(cred_ptr)):
        try:
            cred = ctypes.cast(cred_ptr, ctypes.POINTER(CREDENTIAL)).contents
            if cred.CredentialBlobSize > 0:
                raw = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
                text = raw.decode("utf-8", errors="replace")
                return re.sub(r'[^a-zA-Z0-9_\-]', '', text)
        finally:
            advapi32.CredFree(cred_ptr)
    return None


def main():
    token = get_github_token()
    if not token or len(token) < 10:
        print(f"Failed to get token (len={len(token) if token else 0})")
        # Debug: show what was captured
        return

    print(f"Token OK: {token[:8]}...{token[-4:]} ({len(token)} chars)")

    repo_owner = "aliquanhou"
    repo_name = "ForgeX"
    api_base = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    project_root = Path(__file__).resolve().parent.parent

    with httpx.Client(headers=headers, timeout=120) as client:
        # Auth check
        resp = client.get(api_base)
        if resp.status_code != 200:
            print(f"Auth failed: {resp.status_code}")
            return
        print(f"Auth OK — repo exists")

        # Collect files
        files = []
        exclude_prefixes = {".git", "__pycache__", ".pytest_cache"}
        exclude_ext = {".pyc", ".pyo"}
        exclude_files = {".env"}  # Contains API keys
        exclude_dirs = {"scripts"}

        for f in sorted(project_root.rglob("*")):
            if not f.is_file():
                continue
            rel = str(f.relative_to(project_root)).replace("\\", "/")
            parts = rel.split("/")

            # Check exclusions
            if any(p in exclude_prefixes or p in exclude_dirs for p in parts):
                continue
            if parts[-1] in exclude_files:
                continue
            if f.suffix in exclude_ext:
                continue

            files.append((rel, f))

        print(f"Uploading {len(files)} files...")

        # Create blobs
        tree_items = []
        for idx, (rel_path, full_path) in enumerate(files):
            try:
                content = full_path.read_bytes()
            except Exception:
                continue

            try:
                text = content.decode("utf-8")
                blob_body = {"content": text, "encoding": "utf-8"}
            except UnicodeDecodeError:
                blob_body = {"content": base64.b64encode(content).decode(), "encoding": "base64"}

            resp = client.post(f"{api_base}/git/blobs", json=blob_body)
            if resp.status_code == 201:
                tree_items.append({
                    "path": rel_path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": resp.json()["sha"],
                })

            if (idx + 1) % 30 == 0:
                print(f"  blobs: {len(tree_items)}/{len(files)}")

        print(f"  Created {len(tree_items)}/{len(files)} blobs")

        # Create tree
        print("Creating tree...")
        resp = client.post(f"{api_base}/git/trees", json={"tree": tree_items})
        if resp.status_code != 201:
            print(f"Tree failed: {resp.status_code}")
            return
        tree_sha = resp.json()["sha"]

        # Create commit
        print("Creating commit...")
        resp = client.post(f"{api_base}/git/commits", json={
            "message": "ForgeX Agent OS v0.5 LTS\n\nRuntime-Driven Autonomous Engineering System\n15 modules 195 tests Apache 2.0\n\nA Runtime-Driven Autonomous Engineering System with World Model, Decision Engine, Memory Architecture, Live Execution, Human Collaboration, and Plugin SDK.",
            "tree": tree_sha,
            "parents": [],
        })
        if resp.status_code != 201:
            print(f"Commit failed: {resp.status_code} {resp.text[:200]}")
            return
        commit_sha = resp.json()["sha"]

        # Branch
        print("Updating master branch...")
        resp = client.patch(f"{api_base}/git/refs/heads/master", json={"sha": commit_sha})
        if resp.status_code == 200:
            print("Branch master updated")
        elif resp.status_code == 422:
            resp = client.post(f"{api_base}/git/refs", json={
                "ref": "refs/heads/master", "sha": commit_sha,
            })
            if resp.status_code == 201:
                print("Branch master created")
            else:
                print(f"Branch failed: {resp.status_code}")
                return
        else:
            print(f"Branch failed: {resp.status_code}")
            return

        print(f"\nForgeX v0.5 LTS pushed to GitHub!")
        print(f"https://github.com/{repo_owner}/{repo_name}")


if __name__ == "__main__":
    main()
