# limpaper

A terminal picker for animated wallpapers on Wayland. Browse your video
wallpapers by category, pick one, and it plays as your desktop background via
[mpvpaper](https://github.com/GhostNaN/mpvpaper).

Optionally it also recolours your desktop to match the wallpaper, by handing the
wallpaper's first frame to [caelestia](https://github.com/caelestia-dots)'s
dynamic colour scheme.

```
  ┬  ┬┌┬┐┌─┐┌─┐┌─┐┌─┐┬─┐
  │  │││││├─┘├─┤├─┘├┤ ├┬┘
  ┴─┘┴┴ ┴┴  ┴ ┴┴  └─┘┴└─
  current: cyberpunk nissan r31

  Categories (5)

    1  abstract    (2)
    2  cars        (12)
    3  characters  (23)
    4  misc        (9)
    5  scenery     (21)

   r   rescan folders
   s   stop wallpaper
   q   quit

  Select category >
```

## Requirements

- `mpvpaper` — plays the wallpaper
- `bash`, `awk`, `find` (GNU), `sha256sum`
- `ffmpeg` — only for theming, to extract a frame
- `python3` with Pillow — only for theming, to detect fade-in-from-black frames
- `caelestia-cli` — only for theming

Without ffmpeg or caelestia, limpaper still works as a plain wallpaper picker.

## Install

```sh
install -Dm755 limpaper ~/.local/bin/limpaper
```

Then put your videos in category folders:

```
~/wallpapers/animated/
├── abstract/
├── cars/
├── characters/
├── misc/
└── scenery/
```

Any folder you create becomes a category automatically — there is nothing to
register. New folders and files are picked up on every menu redraw, so you can
add wallpapers while limpaper is open.

Recognised formats: `mp4 mkv webm gif mov avi m4v`

## Usage

```
limpaper              interactive picker
limpaper -l           print every category and wallpaper found
limpaper -r           re-apply the last used wallpaper
limpaper -R           apply a random wallpaper from any category
limpaper -s           stop the wallpaper and restore the baseline colours
limpaper -c           print the path of the current wallpaper
limpaper -h           help
```

To bring your wallpaper back after a reboot, add `-r` to your compositor's
autostart. For Hyprland:

```
exec-once = ~/.local/bin/limpaper -r
```

### A keybind

Hyprland's `PATH` does not include `~/.local/bin`, so use a full path:

```
bind = SUPER, G, exec, foot ~/.local/bin/limpaper
```

Or, if you use caelestia's Lua config, in `~/.config/caelestia/hypr-user.lua`:

```lua
local bin = os.getenv("HOME") .. "/.local/bin"
hl.bind("SUPER + G", hl.dsp.exec_cmd("foot " .. bin .. "/limpaper"))
```

## Theming

When a wallpaper is selected, limpaper extracts its first frame, hands the still
to `caelestia wallpaper -f`, and switches the scheme to `dynamic`. caelestia
then derives a Material You palette from the frame and applies it to your
terminals, bar, GTK, Qt, fuzzel and btop. Open terminals recolour immediately —
caelestia writes the escape sequences to their PTYs. Light/dark mode and the
scheme variant are chosen from the frame too, so a bright wallpaper flips you to
light mode.

Nothing is written by hand: caelestia's own scheme system stays the single
source of truth, so limpaper's colours are the same ones you would get from
`caelestia wallpaper -f` on a still image.

### Going back

The first time limpaper changes your colours it records your current scheme in
`~/.local/state/limpaper/baseline`. `limpaper -s` restores it — scheme first,
then the wallpaper, because once the scheme is no longer `dynamic` restoring the
still cannot pull the palette back off the image.

The baseline is written once and never overwritten, so it can never end up
recording `dynamic` as the thing to return to. If you want to reset it, delete
the file while your preferred scheme is active and it will be recaptured on the
next selection.

### When the colours look wrong

The palette is derived from a small thumbnail of the frame, and Material You's
scoring weights saturation heavily, so a small vivid highlight can outweigh the
dominant colour. A forest scene with sunlight through the trees may come out
warm rather than green.

If a wallpaper's first frame is not representative, sample further in:

```sh
LIMPAPER_FRAME_AT=3 limpaper
```

Frames whose first frame is essentially black — videos that fade in — are
detected and re-sampled from 15% into the video automatically.

## Environment

| Variable | Default | Meaning |
| --- | --- | --- |
| `LIMPAPER_DIR` | `~/wallpapers/animated` | wallpaper root |
| `LIMPAPER_OUTPUT` | `*` | mpvpaper output, e.g. `DP-1` |
| `LIMPAPER_THEME` | `1` | `0` leaves colours alone entirely |
| `LIMPAPER_FRAME_AT` | *(first frame)* | seconds into the video to sample |

mpv options are set by `MPV_OPTS` at the top of the script, and default to
`no-audio loop panscan=1.0 hwdec=auto`. `panscan=1.0` fills the screen instead
of letterboxing.

## Files

| Path | Contents |
| --- | --- |
| `~/.local/state/limpaper/current` | path of the last selected wallpaper |
| `~/.local/state/limpaper/baseline` | scheme to restore when no wallpaper is active |
| `~/.cache/limpaper/frames/` | extracted stills, keyed by path + mtime |

The cache is safe to delete at any time.

## Limitations

- One wallpaper across all outputs. `pkill -x mpvpaper` stops every instance, so
  per-monitor wallpapers would need per-output tracking.
- Sub-folders inside a category are flattened into its listing with a heading
  rather than being their own menu level, which keeps selection to a single
  number but gets long if you nest deeply.
- Theming assumes caelestia. The rest of the script does not.

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).
