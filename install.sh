#!/usr/bin/env bash
set -euo pipefail

# Run as the student user, not with sudo.
if [ "$(id -u)" -eq 0 ]; then
    echo "STOP: Run this installer as student, without sudo." >&2
    exit 1
fi
for command in git python3 install; do
    command -v "$command" >/dev/null || {
        echo "STOP: Required command is missing: $command" >&2
        exit 1
    }
done

repository='https://github.com/rzfeeser/labctl.git'
checkout="$HOME/labctl"
destination="$HOME/.local/share/labctl"
launcher="$HOME/.local/bin/labctl"

# When invoked inside a complete checkout, install those reviewed files.
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$script_dir/labctl.py" ] && [ -f "$script_dir/actions.json" ]; then
    source_dir="$script_dir"
elif [ -e "$checkout" ] || [ -L "$checkout" ]; then
    if [ -L "$checkout" ] || [ ! -d "$checkout/.git" ]; then
        echo "STOP: $checkout exists but is not a regular Git checkout." >&2
        exit 1
    fi
    remote="$(git -C "$checkout" remote get-url origin)"
    if [ "$remote" != "$repository" ] && [ "$remote" != 'https://github.com/rzfeeser/labctl' ]; then
        echo "STOP: Existing checkout has an unexpected origin: $remote" >&2
        exit 1
    fi
    source_dir="$checkout"
    echo "Using existing checkout. No automatic pull or reset is performed."
else
    git clone "$repository" "$checkout"
    source_dir="$checkout"
fi

for file in labctl.py actions.json; do
    [ -f "$source_dir/$file" ] || {
        echo "STOP: Missing source file: $source_dir/$file" >&2
        exit 1
    }
done

# Keep previous installed files and launcher recoverable.
if [ -L "$destination" ]; then
    echo "STOP: Installation directory is a symlink; inspect it first." >&2
    exit 1
fi
mkdir -p "$HOME/.local/share" "$HOME/.local/bin"
stamp="$(date +%Y%m%dT%H%M%S)-$$"
if [ -e "$destination" ]; then
    [ -d "$destination" ] || { echo "STOP: $destination is not a directory." >&2; exit 1; }
    cp -a "$destination" "$destination.backup-$stamp"
    echo "Saved previous installation: $destination.backup-$stamp"
fi
mkdir -p "$destination"
install -m 755 "$source_dir/labctl.py" "$destination/labctl.py"
install -m 644 "$source_dir/actions.json" "$destination/actions.json"

if [ -e "$launcher" ] || [ -L "$launcher" ]; then
    mv "$launcher" "$launcher.backup-$stamp"
    echo "Saved previous command: $launcher.backup-$stamp"
fi
ln -s "$destination/labctl.py" "$launcher"

path_line='export PATH="$HOME/.local/bin:$PATH"'
if ! grep -qxF "$path_line" "$HOME/.bashrc" 2>/dev/null; then
    printf '\n# Personal commands, including labctl\n%s\n' "$path_line" >> "$HOME/.bashrc"
fi

echo
echo "Installed labctl from: $source_dir"
echo "In your CURRENT terminal, run:"
echo '  export PATH="$HOME/.local/bin:$PATH"'
echo '  hash -r'
echo '  labctl help'
echo
echo "Future Bash terminals load the PATH setting from ~/.bashrc."
