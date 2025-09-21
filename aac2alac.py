#!/usr/bin/env python3
# aac2alac — CLI for Resolve pipeline
# Usage: aac2alac <input> <output>
# Policy: process ONLY if ALL audio tracks are AAC; video/other — copy; audio — ALAC; container MOV.
# Encodings: resilient to non-ASCII paths (UTF-8 in all subprocess calls).

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

EXIT_OK = 0
EXIT_ARGS = 1
EXIT_TOOLS = 2
EXIT_NOT_AAC = 3
EXIT_FFMPEG_FAIL = 4

def which_or(path: str | None, fallback: str) -> str | None:
    if path and os.path.isfile(path):
        return path
    return shutil.which(fallback)

def run(cmd, capture=False):
    return subprocess.run(
        cmd,
        check=False,
        stdout=(subprocess.PIPE if capture else None),
        stderr=(subprocess.PIPE if capture else None),
        text=True,
        encoding="utf-8",
        errors="replace",
    )

def shlex_join_safe(parts):
    try:
        from shlex import join as shlex_join
        return shlex_join(parts)
    except Exception:
        import shlex
        return " ".join(shlex.quote(p) for p in parts)

def ffprobe_streams(ffprobe_bin: str, infile: str):
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        infile,
    ]
    res = run(cmd, capture=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {res.stderr.strip()}")
    data = json.loads(res.stdout or "{}")
    return data.get("streams", []), data.get("format", {})

def build_ffmpeg_cmd(ffmpeg_bin: str, infile: str, outfile: str, threads: int | None, movflags: str | None):
    cmd = [ffmpeg_bin, "-y", "-hide_banner", "-nostdin"]
    if threads:
        cmd += ["-threads", str(threads)]
    cmd += ["-i", infile]

    # Mapping: don't combine anything — copy everything except audio (ALAC)
    cmd += ["-map", "0:v?", "-c:v", "copy"]
    cmd += ["-map", "0:a?", "-c:a", "alac"]
    cmd += ["-map", "0:s?", "-c:s", "copy"]
    cmd += ["-map", "0:d?", "-c:d", "copy"]
    cmd += ["-map", "0:t?", "-c:t", "copy"]

    if movflags is None:
        movflags = "+faststart"
    if movflags:
        cmd += ["-movflags", movflags]

    if not outfile.lower().endswith(".mov"):
        outfile = outfile + ".mov"

    cmd += [outfile]
    return cmd, outfile

def main():
    p = argparse.ArgumentParser(description="AAC→ALAC remuxer: video/other streams copy, audio → ALAC, container MOV.")
    p.add_argument("input", help="input video file (all audio must be AAC)")
    p.add_argument("output", help="output .mov")
    p.add_argument("--ffmpeg", help="path to ffmpeg")
    p.add_argument("--ffprobe", help="path to ffprobe")
    p.add_argument("--no-overwrite", action="store_true", help="forbid overwriting the output file")
    p.add_argument("--threads", type=int, help="number of ffmpeg threads")
    p.add_argument("--movflags", help="additional -movflags (defaults to +faststart)")
    args = p.parse_args()

    ffmpeg_bin = which_or(args.ffmpeg, "ffmpeg")
    ffprobe_bin = which_or(args.ffprobe, "ffprobe")
    if not ffmpeg_bin or not ffprobe_bin:
        print("Error: ffmpeg/ffprobe not found.", file=sys.stderr)
        return EXIT_TOOLS

    infile = args.input
    outfile = args.output

    if not os.path.isfile(infile):
        print(f"Error: input file not found: {infile}", file=sys.stderr)
        return EXIT_ARGS
    if args.no_overwrite and os.path.exists(outfile):
        print(f"Error: output file already exists: {outfile}", file=sys.stderr)
        return EXIT_ARGS

    try:
        streams, _fmt = ffprobe_streams(ffprobe_bin, infile)
    except Exception as e:
        print(f"ffprobe error: {e}", file=sys.stderr)
        return EXIT_TOOLS

    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    if not audio_streams:
        print("Error: no audio tracks found.", file=sys.stderr)
        return EXIT_NOT_AAC

    non_aac = [s for s in audio_streams if (s.get("codec_name") or "").lower() != "aac"]
    if non_aac:
        found = ", ".join(sorted(set((s.get("codec_name") or "?") for s in non_aac)))
        print(f"Rejected: non-AAC audio tracks are present ({found}).", file=sys.stderr)
        return EXIT_NOT_AAC

    cmd, real_out = build_ffmpeg_cmd(ffmpeg_bin, infile, outfile, args.threads, args.movflags)

    # Write to a temporary file first, then move atomically
    tmp_dir = tempfile.mkdtemp(prefix="aac2alac_")
    tmp_out = os.path.join(tmp_dir, os.path.basename(real_out))
    cmd = cmd[:-1] + [tmp_out]

    print(">>", shlex_join_safe(cmd))
    proc = run(cmd, capture=True)
    if proc.returncode != 0:
        if proc.stdout:
            print(proc.stdout, file=sys.stderr, end="")
        if proc.stderr:
            print(proc.stderr, file=sys.stderr, end="")
        return EXIT_FFMPEG_FAIL

    os.makedirs(os.path.dirname(real_out) or ".", exist_ok=True)
    try:
        if os.path.exists(real_out):
            os.remove(real_out)
        shutil.move(tmp_out, real_out)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    v_count = sum(1 for s in streams if s.get("codec_type") == "video")
    a_count = len(audio_streams)
    print(f"Done: {os.path.basename(real_out)}  |  video: {v_count} (copy), audio: {a_count} (ALAC)")
    return EXIT_OK

if __name__ == "__main__":
    sys.exit(main())