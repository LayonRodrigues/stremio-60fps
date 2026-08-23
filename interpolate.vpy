# ---------------------------------------------------------------------------
# interpolate.vpy - motion interpolation for mpv (a free stand-in for SVP)
#
# ENGINE "mvtools": block-based motion estimation. Same technique SVP uses
#   underneath (svpflow grew out of MVTools). Runs on the CPU.
#
# ENGINE "rife": neural network on the GPU. Better quality, but measured on
#   a Radeon RX 5700 XT it only keeps up to 480p:
#       480p 4.7s | 720p 9.3s | 900p 13.3s | 1080p 19.5s   (budget: 8.0s)
#   Left ready for the day a stronger GPU shows up.
#
# Why SVP felt better: it offloads motion estimation to the GPU (OpenCL) and
# adapts quality on the fly, dropping detail before it stutters. MVTools is
# CPU-only, and here it shares the CPU with Stremio's torrent server.
#
# Current tuning, measured on the real case (HEVC 10-bit 1080p, Stremio
# running, 8 seconds of video, 8.0s budget):
#       old config (pel=2 blk=16, no bit conversion) ... 15.2s  stuttered
#       converting to 8-bit only ....................... 7.4s
#       + pel=1 blk=32 rfilter=2 (current) ............. 3.7s   52% headroom
#
# mpv injects these globals: video_in, container_fps, display_fps.
# ---------------------------------------------------------------------------

from fractions import Fraction

import vapoursynth as vs

core = vs.core

# ===================== SETTINGS ============================================

ENGINE = "mvtools"     # "mvtools" (recommended here) or "rife"

TARGET_FPS = 60        # only used if mpv doesn't report the monitor's rate
FPS_CEILING = 60       # safety cap: the CPU can't sustain more than this
MAX_INPUT_FPS = 32     # video above this passes through (already smooth)
# Cost scales with pixel count, not width. A 2.39:1 scope release at
# 2048x858 is 1.76 MP - cheaper than full 1080p at 2.07 MP - so a width
# limit would wrongly skip it. 4K (8.3 MP) is what we actually want out.
MAX_PIXELS = 1920 * 1080

# --- MVTools ---
# SMOOTHNESS "block": faster, blocky artefacts on strong motion.
#            "flow":  smoother transitions, ~35% more expensive. At 1080p it
#                     sits right at the real-time limit on this machine.
SMOOTHNESS = "block"
BLOCK = 32             # 16 = more precise and more expensive; 32 = cheaper
PRECISION = 1          # 1 = whole pixel (cheap), 2 = half pixel (better)
OVERLAP = 8            # 0 is much faster but makes blocking visible
REFINE = 2             # Super's rfilter: 2 is cheaper than 4

# --- RIFE (only used when ENGINE = "rife") ---
MODELS = r"G:\Tools\mpv-rife\vs\Lib\site-packages\vapoursynth\plugins\models"
MODEL = "rife-v4_ensembleFalse_fastTrue"   # fastest of the installed models
GPU_ID = 0
GPU_THREADS = 2        # measured: raising this doesn't help, the GPU saturates
SCENE_THRESHOLD = 0.10 # sensitivity of the scene-cut detector

# ===========================================================================


def _matrix_for(height):
    """Colour coefficients by height: SD uses BT.601, HD uses BT.709."""
    return "709" if height > 576 else "470bg"


clip = video_in

# Source frame rate: prefer what mpv reports from the container.
try:
    source_fps = float(container_fps)
except (NameError, TypeError, ValueError):
    source_fps = clip.fps_num / clip.fps_den if clip.fps_den else 0.0

worth_it = (
    0 < source_fps < MAX_INPUT_FPS
    and 0 < clip.width * clip.height <= MAX_PIXELS
)

if not worth_it:
    clip.set_output()

else:
    # mpv hands over the clip with no declared frame rate, because it
    # supports variable frame rate content. The filters demand a valid rate,
    # so we rebuild it as an exact fraction (24000/1001 for cinema's 23.976).
    rate = Fraction(source_fps).limit_denominator(1001)
    clip = core.std.AssumeFPS(
        clip, fpsnum=rate.numerator, fpsden=rate.denominator
    )

    # The output must match the MONITOR's rate, not a round number. On a
    # 60.000 Hz display, generating 59.94 leaves a spare refresh every ~16
    # seconds: mpv repeats a frame and you get a periodic hitch. mpv reports
    # the measured refresh rate in display_fps.
    try:
        target = float(display_fps)
    except (NameError, TypeError, ValueError):
        target = float(TARGET_FPS)
    if not (24.0 <= target <= 144.0):    # nonsense value: fall back
        target = float(TARGET_FPS)
    if target > FPS_CEILING:             # monitor too fast for this CPU
        target = float(FPS_CEILING)
    output_rate = Fraction(target).limit_denominator(1001)

    matrix = _matrix_for(clip.height)
    is_rgb = clip.format.color_family == vs.RGB

    if ENGINE == "rife":
        # 1) Mark the scene cuts. Without this RIFE invents a smeared
        #    transition across every cut, the ugliest artefact of all.
        if is_rgb:
            ref = core.resize.Bicubic(clip, format=vs.GRAY8, matrix_s=matrix)
        else:
            ref = core.resize.Bicubic(clip, format=vs.GRAY8)
        ref = core.misc.SCDetect(ref, threshold=SCENE_THRESHOLD)

        # 2) RIFE only accepts 32-bit float RGB.
        if is_rgb:
            rgb = core.resize.Bicubic(clip, format=vs.RGBS)
        else:
            rgb = core.resize.Bicubic(clip, format=vs.RGBS, matrix_in_s=matrix)
        rgb = core.std.CopyFrameProps(
            rgb, ref, props=["_SceneChangeNext", "_SceneChangePrev"]
        )

        out = core.rife.RIFE(
            rgb,
            model_path=f"{MODELS}\\{MODEL}",
            fps_num=output_rate.numerator, fps_den=output_rate.denominator,
            gpu_id=GPU_ID, gpu_thread=GPU_THREADS,
            sc=True,
        )
        out = core.resize.Bicubic(out, format=vs.YUV420P8, matrix_s=matrix)

    else:
        # MVTools works in YUV. On top of that it only has optimised (SIMD)
        # paths for 8-bit: with 10-bit video it falls off a cliff. Converting
        # first halved the time on HEVC 10-bit, and the precision loss is
        # invisible on an SDR display.
        if is_rgb:
            src = core.resize.Bicubic(clip, format=vs.YUV420P8, matrix_s=matrix)
        elif clip.format.bits_per_sample > 8:
            src = core.resize.Bicubic(clip, format=vs.YUV420P8)
        else:
            src = clip

        # Super builds the multi-scale pyramid used by the motion search.
        sup = core.mv.Super(src, pel=PRECISION, sharp=1, rfilter=REFINE)

        # Analyse estimates the backward and forward vectors.
        search = dict(
            blksize=BLOCK, overlap=OVERLAP, search=3, searchparam=2,
            truemotion=True, chroma=False,
        )
        backward = core.mv.Analyse(sup, isb=True, **search)
        forward = core.mv.Analyse(sup, isb=False, **search)

        # thscd1/thscd2 handle scene cuts: past the threshold the filter
        # repeats a frame instead of inventing a transition that never was.
        common = dict(num=output_rate.numerator, den=output_rate.denominator,
                      thscd1=400, thscd2=80)
        if SMOOTHNESS == "flow":
            out = core.mv.FlowFPS(src, sup, backward, forward, mask=2, **common)
        else:
            out = core.mv.BlockFPS(src, sup, backward, forward, mode=3, **common)

    out.set_output()
