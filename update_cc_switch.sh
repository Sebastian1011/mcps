#!/bin/bash

set -e

REPO="farion1231/cc-switch"
API_URL="https://api.github.com/repos/$REPO/releases/latest"
FORCE=false
RESTART=true

while [ $# -gt 0 ]; do
    case "$1" in
        --force) FORCE=true ;;
        --no-restart) RESTART=false ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done

# Check for required dependencies
DOWNLOADER=""
if command -v curl >/dev/null 2>&1; then
    DOWNLOADER="curl"
elif command -v wget >/dev/null 2>&1; then
    DOWNLOADER="wget"
else
    echo "Either curl or wget is required but neither is installed" >&2
    exit 1
fi

# Check if jq is available (optional)
HAS_JQ=false
if command -v jq >/dev/null 2>&1; then
    HAS_JQ=true
fi

# Download function that works with both curl and wget
download_file() {
    local url="$1"
    local output="$2"

    if [ "$DOWNLOADER" = "curl" ]; then
        if [ -n "$output" ]; then
            curl -fsSL -o "$output" "$url"
        else
            curl -fsSL "$url"
        fi
    elif [ "$DOWNLOADER" = "wget" ]; then
        if [ -n "$output" ]; then
            wget -q -O "$output" "$url"
        else
            wget -q -O - "$url"
        fi
    else
        return 1
    fi
}

# Detect platform (cc-switch only ships .deb packages for Linux)
case "$(uname -s)" in
    Linux) : ;;
    *) echo "This script only supports Linux (.deb packages). See https://github.com/$REPO/releases for other platforms." >&2; exit 1 ;;
esac

case "$(uname -m)" in
    x86_64|amd64) arch="x86_64" ;;
    aarch64|arm64) arch="arm64" ;;
    *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

# Determine which desktop user owns the CLI installations (handles sudo)
target_uid="${SUDO_UID:-$(id -u)}"
target_user=$(getent passwd "$target_uid" | cut -d: -f1)
target_home=$(getent passwd "$target_uid" | cut -d: -f6)

# Run a command as the target desktop user (handles the sudo case)
run_as_target() {
    if [ "$(id -u)" -eq 0 ] && [ "$target_uid" -ne 0 ]; then
        runuser -u "$target_user" -- "$@"
    else
        "$@"
    fi
}

target_command_path() {
    local command_name="$1"
    local command_path

    command_path=$(run_as_target sh -c 'command -v "$1"' sh "$command_name" 2>/dev/null || true)
    if [ -n "$command_path" ]; then
        echo "$command_path"
    elif [ -x "$target_home/.local/bin/$command_name" ]; then
        echo "$target_home/.local/bin/$command_name"
    fi
}

update_cli() {
    local command_name="$1"
    local npm_package="$2"
    local command_path npm_path npm_prefix

    command_path=$(target_command_path "$command_name")
    if [ -z "$command_path" ]; then
        echo "⏭️  $command_name is not installed; skipping"
        return
    fi

    if { [ "$command_name" = "claude" ] || [ "$command_name" = "codex" ]; } &&
       [ "$(dirname "$command_path")" = "$target_home/.local/bin" ]; then
        echo "⬆️  Updating $command_name with '$command_name update'"
        run_as_target "$command_path" update
        return
    fi

    npm_path=$(target_command_path npm)
    if [ -n "$npm_path" ]; then
        npm_prefix=$(run_as_target "$npm_path" prefix --global 2>/dev/null || true)
    fi

    if [ -n "$npm_prefix" ] &&
       [ "$command_path" = "$npm_prefix/bin/$command_name" ] &&
       run_as_target "$npm_path" list --global --depth=0 "$npm_package" >/dev/null 2>&1; then
        echo "⬆️  Updating $command_name with npm"
        run_as_target "$npm_path" update --global "$npm_package"
    else
        echo "⚠️  Cannot determine how $command_name was installed; skipping" >&2
    fi
}

echo "Updating AI CLIs..."
update_cli claude @anthropic-ai/claude-code
update_cli codex @openai/codex
update_cli gemini @google/gemini-cli
echo ""

# Fetch release metadata
release_json=$(download_file "$API_URL")

if echo "$release_json" | grep -q "API rate limit exceeded"; then
    echo "GitHub API rate limit exceeded. Try again later, or authenticate to raise the limit." >&2
    exit 1
fi

# Extract tag_name
if [ "$HAS_JQ" = true ]; then
    tag=$(echo "$release_json" | jq -r ".tag_name // empty")
else
    normalized=$(echo "$release_json" | tr -d '\n\r\t' | sed 's/ \+/ /g')
    if [[ $normalized =~ \"tag_name\"[[:space:]]*:[[:space:]]*\"([^\"]+)\" ]]; then
        tag="${BASH_REMATCH[1]}"
    fi
fi

# Reject non-version content (e.g. an HTML error page or unexpected schema)
if [[ ! "$tag" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+ ]]; then
    echo "Failed to get a valid release tag from the GitHub API (got unexpected content)." >&2
    exit 1
fi

asset="CC-Switch-${tag}-Linux-${arch}.deb"

# Extract the checksum (GitHub-provided digest) for our asset
if [ "$HAS_JQ" = true ]; then
    digest=$(echo "$release_json" | jq -r ".assets[] | select(.name == \"$asset\") | .digest // empty")
else
    normalized=$(echo "$release_json" | tr -d '\n\r\t' | sed 's/ \+/ /g')
    rest="${normalized#*\"name\": \"$asset\"}"
    if [ "$rest" = "$normalized" ]; then
        rest=""
    fi
    if [[ $rest =~ \"digest\"[[:space:]]*:[[:space:]]*\"sha256:([a-f0-9]{64})\" ]]; then
        digest="${BASH_REMATCH[1]}"
    fi
fi

# Strip the optional "sha256:" prefix if jq left it in
digest="${digest#sha256:}"

# Validate checksum format (SHA256 = 64 hex characters)
if [ -z "$digest" ] || [[ ! "$digest" =~ ^[a-f0-9]{64}$ ]]; then
    echo "Asset $asset not found (or missing checksum) in the latest release of $REPO" >&2
    exit 1
fi

# Skip if the installed version is already up to date
if [ "$FORCE" = false ] && command -v dpkg-query >/dev/null 2>&1; then
    installed_version=$(dpkg-query -W -f='${Version}' cc-switch 2>/dev/null || true)
    if [ "$installed_version" = "${tag#v}" ]; then
        echo "cc-switch $installed_version is already up to date."
        exit 0
    fi
fi

# Determine how to gain root for installation
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        echo "This script must be run as root, or with sudo installed" >&2
        exit 1
    fi
fi

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

download_url="https://github.com/$REPO/releases/download/$tag/$asset"
deb_path="$workdir/$asset"

if ! download_file "$download_url" "$deb_path"; then
    echo "Download failed" >&2
    exit 1
fi

# Pick the right checksum tool
actual=$(sha256sum "$deb_path" | cut -d' ' -f1)

if [ "$actual" != "$digest" ]; then
    echo "Checksum verification failed" >&2
    exit 1
fi

# Snapshot the running instance (if any) before installing, so we can restart it
# afterwards. Must happen before install/kill, since /proc/<pid> disappears once
# the process exits.
running_pid=""
launch_env=()
if [ "$RESTART" = true ]; then
    running_pid=$(pgrep -u "$target_uid" -x cc-switch | head -n1 || true)
    if [ -n "$running_pid" ]; then
        while IFS= read -r -d '' kv; do
            case "$kv" in
                DISPLAY=*|WAYLAND_DISPLAY=*|XDG_RUNTIME_DIR=*|DBUS_SESSION_BUS_ADDRESS=*|XAUTHORITY=*|XDG_SESSION_TYPE=*|HOME=*)
                    launch_env+=("$kv")
                    ;;
            esac
        done < "/proc/$running_pid/environ" 2>/dev/null || true
    fi
fi

# Install (prefer apt-get so dependencies are resolved)
if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get install -y "$deb_path"
else
    $SUDO dpkg -i "$deb_path"
fi

echo ""
echo "✅ Installed CC Switch $tag"
echo ""

# Restart cc-switch if it was running before the install (tauri-plugin-single-instance
# means we must wait for the old process to fully exit before launching the new binary)
if [ -n "$running_pid" ]; then
    kill -TERM "$running_pid" 2>/dev/null || true
    waited=0
    while kill -0 "$running_pid" 2>/dev/null && [ "$waited" -lt 10000 ]; do
        sleep 0.2
        waited=$((waited + 200))
    done
    if kill -0 "$running_pid" 2>/dev/null; then
        kill -KILL "$running_pid" 2>/dev/null || true
        sleep 2
    fi

    run_as_target setsid env -u DESKTOP_STARTUP_ID -u XDG_ACTIVATION_TOKEN "${launch_env[@]}" /usr/bin/cc-switch >/dev/null 2>&1 </dev/null &
    disown

    sleep 1
    new_pid=$(pgrep -u "$target_uid" -x cc-switch | head -n1 || true)
    if [ -n "$new_pid" ]; then
        echo "🔄 Restarted cc-switch (was PID $running_pid, now PID $new_pid)"

        # cc-switch defaults to a hidden main window on fresh launch (silentStartup).
        # Launching it again hands off to the running instance via tauri-plugin-single-instance,
        # which shows + focuses the main window. Wait for its DBus name so the second launch
        # doesn't race the first and become its own primary instance.
        if command -v gdbus >/dev/null 2>&1; then
            waited=0
            while [ "$waited" -lt 15000 ]; do
                if run_as_target env "${launch_env[@]}" gdbus call --session \
                      --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
                      --method org.freedesktop.DBus.NameHasOwner \
                      com.ccswitch.desktop.SingleInstance 2>/dev/null | grep -q true; then
                    break
                fi
                sleep 0.3
                waited=$((waited + 300))
            done
        else
            sleep 3
        fi

        run_as_target setsid env -u DESKTOP_STARTUP_ID -u XDG_ACTIVATION_TOKEN "${launch_env[@]}" /usr/bin/cc-switch >/dev/null 2>&1 </dev/null &
        disown
        echo "🪟 Requested main window to show"
    else
        echo "⚠️  Could not confirm cc-switch restarted (no GUI session? launch it manually)" >&2
    fi
    echo ""
fi

# Fix an autostart entry left pointing at a deleted inode by a previous in-place upgrade
autostart_desktop="$target_home/.config/autostart/CC Switch.desktop"
if [ -f "$autostart_desktop" ] && grep -q '^Exec=.*(deleted)' "$autostart_desktop" 2>/dev/null; then
    sed -i 's|^Exec=.*|Exec=/usr/bin/cc-switch|' "$autostart_desktop"
    if [ "$(id -u)" -eq 0 ] && [ "$target_uid" -ne 0 ]; then
        chown "$target_uid:$target_uid" "$autostart_desktop"
    fi
    echo "🛠️  Fixed stale autostart entry: $autostart_desktop"
    echo ""
fi
