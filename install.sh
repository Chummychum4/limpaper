#!/usr/bin/env bash
# limpaper installer for Arch Linux and Debian/Ubuntu (and their derivatives).
#
#   curl -fsSL https://raw.githubusercontent.com/Chummychum4/limpaper/main/install.sh | bash
#
# Options (after `bash -s --` when piping):
#   --no-gui        skip the graphical app (PySide6)
#   --no-tui        skip the terminal app (Textual)
#   --no-mpvpaper   do not install or build mpvpaper
#   --ref REF       install a branch or tag instead of main
#   --uninstall     remove limpaper (your wallpapers are left alone)
#
# Everything goes into your home directory: a virtual environment in
# ~/.local/share/limpaper/venv, the `limpaper` command in ~/.local/bin and a
# desktop entry. System packages are installed with sudo.

set -euo pipefail

REPO="Chummychum4/limpaper"
REF="main"
WANT_GUI=1
WANT_TUI=1
WANT_MPVPAPER=1
UNINSTALL=0

DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
PREFIX="$DATA/limpaper"
VENV="$PREFIX/venv"
BIN="$HOME/.local/bin"

bold=$'\e[1m'; dim=$'\e[2m'; cyan=$'\e[36m'; yellow=$'\e[33m'; red=$'\e[31m'; reset=$'\e[0m'
step() { printf '\n%s==>%s %s%s%s\n' "$cyan" "$reset" "$bold" "$*" "$reset"; }
note() { printf '    %s%s%s\n' "$dim" "$*" "$reset"; }
warn() { printf '%s!!  %s%s\n' "$yellow" "$*" "$reset" >&2; }
die()  { printf '%sxx  %s%s\n' "$red" "$*" "$reset" >&2; exit 1; }

while (($#)); do
    case $1 in
        --no-gui) WANT_GUI=0 ;;
        --no-tui) WANT_TUI=0 ;;
        --no-mpvpaper) WANT_MPVPAPER=0 ;;
        --ref) REF=${2:?--ref needs a value}; shift ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help) sed -n '2,17p' "${BASH_SOURCE[0]:-}" 2>/dev/null || true; exit 0 ;;
        *) die "Unknown option: $1" ;;
    esac
    shift
done

[[ $EUID -eq 0 ]] && die "Run this as your normal user, not root; it uses sudo where needed."

if ((UNINSTALL)); then
    step "Removing limpaper"
    "$BIN/limpaper" stop >/dev/null 2>&1 || true
    rm -rf "$PREFIX"
    rm -f "$BIN/limpaper" "$DATA/applications/limpaper.desktop" \
          "$DATA/icons/hicolor/256x256/apps/limpaper.png" \
          "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/limpaper-restore.desktop"
    note "Settings in ~/.config/limpaper and your wallpaper folder were kept."
    exit 0
fi

SUDO=sudo
command -v sudo >/dev/null || die "sudo is required to install system packages."

# ── Distribution ─────────────────────────────────────────────────────────────
# shellcheck source=/dev/null
. /etc/os-release 2>/dev/null || die "Cannot read /etc/os-release."
family=""
for id in ${ID:-} ${ID_LIKE:-}; do
    case $id in
        arch|archarm|endeavouros|manjaro|cachyos|garuda) family=arch; break ;;
        debian|ubuntu|linuxmint|pop|raspbian|kali) family=debian; break ;;
    esac
done
[[ -n $family ]] || die "Unsupported distribution '${ID:-unknown}'. Arch and Debian/Ubuntu families are supported; see the README for manual steps."
step "Installing limpaper on ${PRETTY_NAME:-$ID} ($family family)"

# ── System packages ──────────────────────────────────────────────────────────
install_arch() {
    local pkgs=(python python-pip mpv ffmpeg python-pillow) extra=()
    ((WANT_GUI)) && extra+=(pyside6 qt6-multimedia-ffmpeg)
    ((WANT_TUI)) && extra+=(python-textual)
    step "pacman: ${pkgs[*]} ${extra[*]}"
    $SUDO pacman -S --needed --noconfirm "${pkgs[@]}"
    # Optional: anything that fails here is fetched with pip further down
    if ((${#extra[@]})); then
        $SUDO pacman -S --needed --noconfirm "${extra[@]}" ||
            warn "Could not install ${extra[*]} with pacman; pip will provide them."
    fi

    ((WANT_MPVPAPER)) || return 0
    command -v mpvpaper >/dev/null && { note "mpvpaper already installed"; return 0; }
    step "mpvpaper"
    if pacman -Si mpvpaper >/dev/null 2>&1; then
        $SUDO pacman -S --needed --noconfirm mpvpaper
    elif command -v yay >/dev/null; then
        yay -S --needed --noconfirm mpvpaper
    elif command -v paru >/dev/null; then
        paru -S --needed --noconfirm mpvpaper
    else
        note "No AUR helper found; building mpvpaper from the AUR with makepkg"
        $SUDO pacman -S --needed --noconfirm base-devel git
        local tmp; tmp=$(mktemp -d)
        git clone --depth 1 https://aur.archlinux.org/mpvpaper.git "$tmp/mpvpaper"
        (cd "$tmp/mpvpaper" && makepkg -si --noconfirm)
        rm -rf "$tmp"
    fi
}

install_debian() {
    local pkgs=(python3 python3-venv python3-pip mpv ffmpeg python3-pil curl ca-certificates) extra=()
    # Runtime libraries the PySide6 wheels expect on a desktop system
    ((WANT_GUI)) && extra+=(libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0
                           libfontconfig1 libdbus-1-3)
    step "apt: ${pkgs[*]}"
    $SUDO apt-get update -q
    $SUDO apt-get install -y -q "${pkgs[@]}"
    if ((${#extra[@]})); then
        # One at a time: names drift between releases and none of them is fatal
        local p
        for p in "${extra[@]}"; do
            $SUDO apt-get install -y -q "$p" >/dev/null 2>&1 || warn "Skipped $p (not available here)."
        done
    fi

    ((WANT_MPVPAPER)) || return 0
    command -v mpvpaper >/dev/null && { note "mpvpaper already installed"; return 0; }
    step "mpvpaper"
    if apt-cache show mpvpaper >/dev/null 2>&1; then
        $SUDO apt-get install -y -q mpvpaper
        return 0
    fi
    note "mpvpaper is not packaged here; building it from source"
    $SUDO apt-get install -y -q build-essential meson ninja-build pkg-config git \
        libmpv-dev libwayland-dev libwayland-bin wayland-protocols libegl-dev
    local tmp; tmp=$(mktemp -d)
    git clone --depth 1 https://github.com/GhostNaN/mpvpaper.git "$tmp/mpvpaper"
    (cd "$tmp/mpvpaper" && meson setup build --buildtype=release && ninja -C build && $SUDO ninja -C build install)
    rm -rf "$tmp"
}

"install_$family"

# ── limpaper itself ──────────────────────────────────────────────────────────
step "Creating the virtual environment in $VENV"
mkdir -p "$PREFIX" "$BIN"
# System site-packages let Arch reuse its PySide6/Textual instead of downloading them
python3 -m venv --system-site-packages --clear "$VENV"
"$VENV/bin/python" -m pip install -q --upgrade pip

# Run from a checkout (./install.sh)? Install that. Piped from curl? Download.
here=""
[[ -f ${BASH_SOURCE[0]:-} ]] && here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [[ -n $here && -f $here/pyproject.toml && -d $here/src/limpaper ]]; then
    src=$here
    note "installing from this checkout: $src"
else
    src="https://github.com/$REPO/archive/$REF.tar.gz"
    note "installing $REPO@$REF"
fi

step "Installing limpaper"
"$VENV/bin/python" -m pip install -q --upgrade --no-deps "$src"

# Pull in whatever the distribution did not provide
missing=()
if ((WANT_TUI)) && ! "$VENV/bin/python" -c 'import textual' 2>/dev/null; then
    missing+=("textual>=0.47")
fi
if ((WANT_GUI)) && ! "$VENV/bin/python" -c 'import PySide6.QtWidgets' 2>/dev/null; then
    missing+=("PySide6-Essentials>=6.5" "PySide6-Addons>=6.5")
fi
if ((${#missing[@]})); then
    step "pip: ${missing[*]}"
    "$VENV/bin/python" -m pip install -q "${missing[@]}"
fi

ln -sf "$VENV/bin/limpaper" "$BIN/limpaper"

if ((WANT_GUI)); then
    step "Adding the desktop entry"
    icon_src=$("$VENV/bin/python" -c 'import limpaper, pathlib; print(pathlib.Path(limpaper.__file__).parent / "assets" / "icon.png")')
    install -Dm644 "$icon_src" "$DATA/icons/hicolor/256x256/apps/limpaper.png"
    mkdir -p "$DATA/applications"
    cat > "$DATA/applications/limpaper.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=limpaper
GenericName=Live wallpapers
Comment=Browse, download and play animated wallpapers
Exec=$BIN/limpaper gui
Icon=limpaper
Terminal=false
Categories=Utility;Settings;DesktopSettings;
Keywords=wallpaper;live;animated;video;background;
EOF
    command -v update-desktop-database >/dev/null && update-desktop-database "$DATA/applications" 2>/dev/null || true
fi

mkdir -p "$HOME/wallpapers/animated"

step "Done"
"$BIN/limpaper" doctor || true
cat <<EOF

  ${bold}limpaper${reset}          TUI in a terminal, GUI from your app launcher
  ${bold}limpaper gui${reset}      the graphical app
  ${bold}limpaper tui${reset}      the terminal app
  ${bold}limpaper --help${reset}   every command

EOF
case ":$PATH:" in
    *":$BIN:"*) ;;
    *) warn "$BIN is not on your PATH yet. Open a new shell, or add: export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac
[[ -n ${WAYLAND_DISPLAY:-} ]] || warn "Playback needs a wlroots Wayland compositor (Hyprland, Sway, river, ...)."
