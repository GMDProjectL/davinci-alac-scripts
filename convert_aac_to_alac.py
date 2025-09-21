#!/usr/bin/env python3
# Workspace → Scripts → Utility → convert_aac_to_alac
# Takes selected clips, runs the "second script" (aac2alac),
# then: if RELINK is successful — we DO NOT import and DO NOT create a bin.
# If RELINK is disabled/unsuccessful — we import into "ALAC Converted" (created lazily).

import os
import sys
import shlex
import shutil
import subprocess
from datetime import datetime

if "/opt/resolve/Developer/Scripting/Modules" not in sys.path:
    sys.path.append("/opt/resolve/Developer/Scripting/Modules")

import DaVinciResolveScript as dvr # have fun lol


CONVERTER_BIN = "/usr/bin/aac2alac"
TARGET_BIN_NAME = "ALAC Converted" 
SUFFIX = "_alac"                   
RELINK_ORIGINAL = True             
RELINK_MODE = "replace"            
STRICT_PRECHECK_AAC = False        


EXIT_OK = 0
EXIT_NOT_AAC = 3

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[ALAC {ts}] {msg}")

def get_resolve():
    try:
        return dvr.scriptapp("Resolve")
    except Exception:
        return None


def normalize_iter(x):
    if not x:
        return []
    if isinstance(x, dict):
        return list(x.values())
    if isinstance(x, (list, tuple)):
        return list(x)
    try:
        return list(x)
    except TypeError:
        return []

def subfolders(folder):
    try:
        return [f for f in normalize_iter(folder.GetSubFolders()) if hasattr(f, "GetName")]
    except Exception:
        return []

def ensure_bin(media_pool, name: str):
    """Lazily finds/creates a bin ONLY when an import is actually needed."""
    root = media_pool.GetRootFolder()

    queue = [root]
    while queue:
        cur = queue.pop(0)
        try:
            if cur.GetName() == name:
                return cur
        except Exception:
            pass
        queue.extend(subfolders(cur))

    return media_pool.AddSubFolder(root, name)

def build_output_path(src_path: str, suffix: str = SUFFIX) -> str:
    base, _ = os.path.splitext(src_path)
    return f"{base}{suffix}.mov"

def normalize_selection(sel):
    items = normalize_iter(sel)
    return [c for c in items if c and hasattr(c, "GetClipProperty")]

def has_aac_audio_quick(clip) -> bool:
    props = clip.GetClipProperty() or {}
    for k in ("Audio Codec", "Audio Codec Type"):
        if "AAC" in (props.get(k) or "").upper():
            return True
    return False

def find_converter() -> str | None:
    p = os.environ.get("AAC2ALAC_BIN") or CONVERTER_BIN
    if not os.path.isabs(p):
        found = shutil.which(p)
        if found:
            p = found
    if p and os.path.isfile(p) and os.access(p, os.X_OK):
        return p
    return None

def relink_replaceclip(clip, new_path: str) -> bool:
    try:
        return bool(clip.ReplaceClip(os.path.abspath(new_path)))
    except Exception:
        return False

def relink_folder(media_pool, clip, new_path: str) -> bool:
    try:
        folder = os.path.abspath(os.path.dirname(new_path))
        return bool(media_pool.RelinkClips([clip], folder))
    except Exception:
        return False

def main():
    resolve = get_resolve()
    if not resolve:
        print("Failed to get Resolve API. Run from Workspace → Scripts.")
        return

    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject() if pm else None
    if not project:
        print("No project is open.")
        return

    media_pool = project.GetMediaPool()
    if not media_pool:
        print("Failed to get Media Pool.")
        return

    selection = normalize_selection(media_pool.GetSelectedClips())
    if not selection:
        print("Nothing is selected in the Media Pool. Select clips and run again.")
        return

    converter = find_converter()
    if not converter:
        print(f"The second script (aac2alac) was not found. Check AAC2ALAC_BIN/CONVERTER_BIN. Current: {CONVERTER_BIN}")
        return

    current_folder = media_pool.GetCurrentFolder()
    converted = skipped = failed = relinked = imported = 0

    for clip in selection:
        src = clip.GetClipProperty("File Path")
        if not src or not os.path.exists(src):
            log("Skipping: clip file not found")
            skipped += 1
            continue

        if STRICT_PRECHECK_AAC and not has_aac_audio_quick(clip):
            log(f"Skipping (quick properties check shows not AAC): {os.path.basename(src)}")
            skipped += 1
            continue

        out_path = build_output_path(src)

        if not os.path.exists(out_path):
            cmd = [converter, src, out_path]
            log("Converting: " + " ".join(shlex.quote(c) for c in cmd))
            try:
                proc = subprocess.run(
                    cmd,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                if proc.returncode != EXIT_OK:
                    if proc.returncode == EXIT_NOT_AAC:
                        log(f"Rejected (not AAC): {os.path.basename(src)}")
                        if proc.stderr:
                            print(proc.stderr.strip())
                        skipped += 1
                        continue
                    else:
                        log(f"Converter error (code {proc.returncode}): {os.path.basename(src)}")
                        if proc.stdout:
                            print(proc.stdout.strip())
                        if proc.stderr:
                            print(proc.stderr.strip())
                        failed += 1
                        continue
            except Exception as e:
                log(f"Converter launch failed: {e}")
                failed += 1
                continue
        else:
            log(f"File already exists, skipping conversion: {os.path.basename(out_path)}")

        if not os.path.exists(out_path):
            log("Resulting file not found after conversion")
            failed += 1
            continue

        did_relink = False
        if RELINK_ORIGINAL:
            if RELINK_MODE == "replace":
                did_relink = relink_replaceclip(clip, out_path)
            elif RELINK_MODE == "relink-folder":
                did_relink = relink_folder(media_pool, clip, out_path)

            if did_relink:
                relinked += 1
                converted += 1
                log(f"Relink/Replace successful: {os.path.basename(out_path)}")
                continue
            else:
                log("Relink failed — importing into a separate bin.")

        try:
            target_bin = ensure_bin(media_pool, TARGET_BIN_NAME)
            media_pool.SetCurrentFolder(target_bin)
            ok = media_pool.ImportMedia([out_path])
            if ok:
                imported += 1
                converted += 1
                log(f"Imported: {os.path.basename(out_path)}")
            else:
                failed += 1
                log(f"Failed to import: {out_path}")
        finally:
            if current_folder:
                media_pool.SetCurrentFolder(current_folder)

    print("\n=== Summary ===")
    print(f"Done: {converted} | skipped: {skipped} | errors: {failed} | relinked: {relinked} | imports: {imported}")

if __name__ == "__main__":
    main()