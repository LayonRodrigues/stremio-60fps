-- ---------------------------------------------------------------------------
-- interpolation.lua - keyboard controls for the interpolation filter
--
-- The original plan was on-screen clickable buttons. It can't be done:
-- Stremio's UI (WebView2) sits on top of the mpv window, so nothing mpv
-- draws ever becomes visible - not buttons, not OSD messages. Confirmed in
-- the log: the overlay enters the libplacebo pipeline
-- ("[vo/gpu-next/libplacebo] // overlay") but stays covered.
--
-- Keyboard input does reach mpv, so shortcuts are what we get:
--   CTRL+I  toggle interpolation
--   CTRL+D  write diagnostics to mpv.log (an on-screen message would be
--           invisible inside Stremio)
--
-- In standalone mpv the messages display normally.
-- ---------------------------------------------------------------------------

local mp = require 'mp'
local msg = require 'mp.msg'

-- Must be identical to the vf line in mpv.conf, otherwise "toggle" won't
-- find the filter and will add a second one instead of removing it.
local FILTER =
  "vapoursynth=file=%33%G:/Tools/mpv-rife/interpolate.vpy:buffered-frames=2"

local interpolating = true

local function toggle_interpolation()
  mp.commandv("vf", "toggle", FILTER)
  interpolating = not interpolating
  local state = interpolating and "ON" or "OFF"
  mp.osd_message("Interpolation " .. state, 2)   -- visible in standalone mpv
  msg.info("INTERPOLATION " .. state)
end

-- Writes metrics to the log. Inside Stremio this is the only way to find out
-- whether the CPU is keeping up.
local function log_diagnostics()
  local dropped = mp.get_property_number("frame-drop-count", 0)
  local vo_dropped = mp.get_property_number("vo-drop-frames", 0)
  local fps = mp.get_property_osd("estimated-vf-fps") or "?"
  local delay = mp.get_property_osd("audio-delay") or "0"
  local width = mp.get_property_number("width", 0)
  local height = mp.get_property_number("height", 0)
  local source_fps = mp.get_property_osd("container-fps") or "?"
  local codec = mp.get_property_osd("video-format") or "?"
  local pixfmt = mp.get_property_osd("video-params/pixelformat") or "?"

  local line = string.format(
    "DIAGNOSTICS | source: %s %dx%d %s fps, %s | output: %s fps | " ..
    "dropped: %d (vo: %d) | audio delay: %s | interpolating: %s",
    codec, width, height, source_fps, pixfmt, fps, dropped, vo_dropped,
    delay, tostring(interpolating))

  msg.info(line)
  mp.osd_message(line, 5)   -- visible in standalone mpv

  if dropped > 0 or vo_dropped > 0 then
    msg.info("DIAGNOSTICS: frames are being dropped - the CPU can't keep up")
  else
    msg.info("DIAGNOSTICS: no dropped frames - keeping up fine")
  end
end

-- Logs by itself 30s into every video, so there is always a snapshot in the
-- log even when nobody pressed anything.
mp.register_event("file-loaded", function()
  mp.add_timeout(30, log_diagnostics)
end)

mp.add_key_binding("CTRL+i", "toggle_interpolation", toggle_interpolation)
mp.add_key_binding("CTRL+d", "log_diagnostics", log_diagnostics)

msg.info("interpolation.lua loaded (CTRL+I toggles, CTRL+D logs diagnostics)")
