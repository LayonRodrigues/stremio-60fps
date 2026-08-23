# stremio-60fps

Motion interpolation (SVP-style "60fps" effect) inside Stremio, using only
free software.

24fps film gets interpolated to your monitor's refresh rate. The player
synthesises the in-between frames that don't exist in the file — the same
thing SVP does, and the same thing TVs call "motion smoothing".

SVP's engine (`svpflow`) is closed source, but it grew out of **MVTools**,
which is GPL and does the same job. That's what this uses.

**This repo is configuration and scripts, not a fork of Stremio.** No Stremio
source code is modified. Binaries are linked, never redistributed.

---

## Does this work on my machine?

Everything below was measured on:

| | |
|---|---|
| CPU | Ryzen 5 3500X (6 cores, no SMT) |
| GPU | Radeon RX 5700 XT |
| Display | 4K @ 60 Hz |

The benchmark: process 8 seconds of video as fast as possible. **Under 8.0s
means it can keep up in real time.** All numbers were taken with Stremio
running, because its torrent server competes for the same CPU.

| Content | MVTools (this setup) |
|---|---|
| 720p | 2.5s |
| 900p | 5.0s |
| 1080p 8-bit | 5.6s |
| 1080p 10-bit | 3.7s |

MVTools runs on the **CPU**. If yours is much weaker than a 3500X, expect to
lower quality settings (there's a measured table below).

---

## Why not RIFE (the neural network one)?

RIFE looks better. It's installed and one constant away in `interpolate.vpy`.
It just doesn't fit on a 2019 GPU:

| Resolution | RIFE v4.0-fast |
|---|---|
| 480p | 4.7s |
| 720p | 9.3s |
| 900p | 13.3s |
| 1080p | 19.5s |

Only 480p keeps up, which is useless in practice. And it isn't a tuning
problem — every lever was tried on 1080p:

| Attempt | Time |
|---|---|
| default | 24.2s |
| cheap conversion (`resize.Point`) | 26.9s |
| `uhd` mode (lower internal flow scale) | 22.6s |
| `uhd` + 4 GPU threads | 21.9s |
| `lite` model | 26.9s |

Nothing moves the number. The bottleneck is raw GPU compute. Set
`ENGINE = "rife"` if you have a modern card.

---

## Requirements

Download these yourself — this repo ships no binaries.

1. **[Stremio Community](https://github.com/Loukious/stremio-shell-ng/releases)**
   — grab `StremioRPCPortable_x64.zip`.
   The **official** Stremio will not work; see [Why the fork](#why-the-fork-is-required).
2. **[mpv](https://github.com/shinchiro/mpv-winbuild-cmake/releases)** —
   `mpv-x86_64-*.7z` (use `-v3` if your CPU has AVX2). Only needed to play
   local files; Stremio has its own libmpv.
3. **[VapourSynth](https://github.com/vapoursynth/vapoursynth/releases)** —
   `Install-Portable-VapourSynth-R*.ps1`, run with
   `-TargetFolder <path>\vs -PythonVersionMinor 12 -Unattended`.
4. **[MVTools](https://github.com/dubhatervapoursynth/vapoursynth-mvtools/releases)**
   — `vapoursynth-mvtools-v24-win64.7z`, the `win64` DLL.
5. Optional, for the RIFE path:
   [RIFE ncnn Vulkan](https://github.com/styler00dollar/VapourSynth-RIFE-ncnn-Vulkan/releases)
   plus model folders from that repo's `models/`, and
   [MiscFilters](https://github.com/vapoursynth/vs-miscfilters-obsolete/releases)
   for scene detection.

Put the VapourSynth plugin DLLs in
`<engine>\vs\Lib\site-packages\vapoursynth\plugins\`.

Then register VapourSynth so mpv can find it:

```
<engine>\vs\python.exe -m vapoursynth register-install
```

---

## Install

Layout used by the configurator (any paths work, just be consistent):

```
G:\Tools\mpv-rife\            <- "engine"
    interpolate.vpy
    mpv\                      (optional standalone mpv)
    vs\                       (VapourSynth portable)
G:\Tools\stremio-community\   <- Stremio Community portable
```

1. Copy `interpolate.vpy` into the engine folder.
2. Run the configurator — it writes every config file with the right paths:

```powershell
.\tools\configure.ps1 -Engine "G:\Tools\mpv-rife" -Stremio "G:\Tools\stremio-community"
```

3. **The portable Stremio zip is incomplete.** It ships the shell and libmpv
   but not the server. Copy these from an official Stremio install:

```
stremio-runtime.exe   server.js
ffmpeg.exe  ffprobe.exe
avcodec-58.dll  avdevice-58.dll  avfilter-7.dll  avformat-58.dll
avutil-56.dll   postproc-55.dll  swresample-3.dll  swscale-5.dll
vcruntime140.dll  vcruntime140_1.dll
```

Without them it opens with *"Cannot execute stremio-runtime"*.
Do **not** overwrite `libmpv-2.dll` — the fork's build is the one with
VapourSynth compiled in.

4. Open Stremio through **`Stremio-60fps.bat`**, never the `.exe` directly.

---

## Controls

| Key | Action |
|---|---|
| `CTRL+I` | toggle interpolation |
| `CTRL+D` | write diagnostics to `mpv.log` |
| `ALT+RIGHT` / `ALT+LEFT` | shift audio by ±20 ms |
| `ALT+DOWN` | reset audio offset |

Stremio's UI is drawn on top of the video, so **nothing mpv draws is
visible** — no OSD, no on-screen buttons. That's why `CTRL+D` writes to the
log instead. In standalone mpv the messages show normally.

---

## Tuning

All settings live at the top of `interpolate.vpy`. Measured on 1080p 10-bit
with Stremio running:

| Settings | Time | Headroom |
|---|---|---|
| `BLOCK=32 PRECISION=1 OVERLAP=8 REFINE=2` (default) | 3.7s | 52% |
| `BLOCK=32 PRECISION=1 OVERLAP=16 REFINE=4` | 4.2s | 47% |
| `BLOCK=16 PRECISION=1 OVERLAP=8 REFINE=4` | 6.5s | 19% |
| `BLOCK=16 PRECISION=2 OVERLAP=8 REFINE=4` | 7.4s | 8% |

Move up the table for quality, down for headroom. `OVERLAP=0` drops to
~2.6s but makes blocking visible during fast motion.

`SMOOTHNESS="flow"` is smoother than `"block"` and costs ~35% more.

---

## Traps this took hours to find

The actual value of this repo.

### Why the fork is required

Official Stremio's shell **never enables mpv's `config` option**, so libmpv
defaults to `config=no` and ignores any `mpv.conf` you write. It also rewrites
`vf` from a polling thread every 500 ms.

The Loukious fork sets `set_property!("config", "yes")` and manipulates filters
by *label* (`vf add` / `vf remove @stremio-gpu-processing`), which leaves a
user filter alone.

### 10-bit video halves your performance

MVTools only has SIMD paths for 8-bit. Modern HEVC releases are 10-bit, and it
falls off a cliff:

| 1080p 10-bit | Time |
|---|---|
| straight through | 15.2s (stutters, audio desyncs) |
| converted to 8-bit first | 7.4s |
| plus the other tuning | 3.7s |

`interpolate.vpy` converts to 8-bit before filtering. On an SDR display the
precision loss is invisible.

### Match the monitor, not a round number

Generating 59,940 fps on a 60,000 Hz monitor leaves a spare refresh every ~16
seconds — mpv repeats a frame and you get a **periodic hitch**. The script asks
mpv for the measured `display_fps` and targets exactly that.

(`BlockFPS` preserves total clip duration, so a non-multiple output rate does
*not* cause audio drift. Don't "fix" a problem that isn't there — that's how
the hitch got introduced in the first place.)

### Audio plays but no video

The filter failed to load. `mpv.log` will say
`Failed to load VapourSynth VSScript library`.

Two causes, both handled by the launcher:
- `VSSCRIPT_PATH` must be set. `register-install` writes it to the registry,
  but processes started before that won't see it.
- `vsscript.dll` needs `python312.dll`, which lives one folder up. Both
  directories must be on `PATH` or Windows can't resolve the dependency.

### A path with `:` breaks `--vf`

mpv treats `:` as its option separator, so `G:/...` silently fails to build the
filter. The fix is mpv's length-prefixed escape:

```
vf=vapoursynth=file=%32%G:/Tools/mpv-rife/interpolate.vpy
```

`32` is the exact character count of the path. Get it wrong and the filter
just doesn't load. `tools\configure.ps1` computes it.

### The filter's sub-options

They are `buffered-frames` and `concurrent-frames` — not `concurrent-requests`,
which is only what the log calls them. `buffered-frames` sets pipeline latency
(default 4 ≈ 67 ms at 60fps); lowering it to 2 measured free.

### mpv hands VapourSynth a clip with no frame rate

mpv supports variable frame rate, so it declares none. MVTools and RIFE both
refuse to work without one. The script rebuilds it from `container_fps` via
`AssumeFPS` as an exact fraction (24000/1001 for 23,976).

---

## Honest limitations

- **Handheld / shaky-cam footage looks worse.** At 24fps, judder and motion
  blur hide camera shake. At 60fps every jolt is legible. The interpolation
  didn't add the shake — it removed what was hiding it. Use `CTRL+I` for those
  films. SVP has the identical problem; it's inherent to the technique.
- **No GPU acceleration.** SVP offloads to OpenCL and adapts quality on the
  fly. MVTools is CPU-only and here it shares the CPU with Stremio's torrent
  server. Expect tight moments SVP wouldn't have.
- **4K is skipped** (`MAX_WIDTH`). It doesn't fit in real time.
- **MVTools v24 uses VapourSynth's deprecated API3.** It loads on R79 and may
  stop working on a future release.
- The Stremio fork is a release candidate maintained by a third party. Keeping
  it portable means deleting the folder undoes everything.

---

## License

MIT — see [LICENSE](LICENSE).

This covers the scripts and configuration in this repo. The software it drives
has its own terms: MVTools and mpv are GPL, VapourSynth is LGPL, the RIFE ncnn
plugin is MIT. None of it is redistributed here.
