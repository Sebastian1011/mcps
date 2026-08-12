#!/bin/bash

set -e

REPO="farion1231/cc-switch"
API_URL="https://api.github.com/repos/$REPO/releases/latest"
FORCE=false
RESTART=true

# Slack notification target. A bot token posts straight to $SLACK_CHANNEL; an
# incoming webhook posts to whatever channel it was created for.
SLACK_CHANNEL="${SLACK_CHANNEL:-C0BFQVD0MHS}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-${AGENT_SLACK_WEBHOOK_URL:-}}"

# Lines collected during the run and reported to Slack when the script exits
CLI_LINES=()
CC_LINES=()
ERROR_MSG=""

die() {
    ERROR_MSG="$1"
    echo "$1" >&2
    exit 1
}

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

json_escape() {
    if [ "$HAS_JQ" = true ]; then
        printf '%s' "$1" | jq -Rsa .
    else
        # Tabs become spaces and other control characters are dropped; JSON
        # forbids them unescaped and only newlines are worth keeping here.
        printf '"%s"' "$(printf '%s' "$1" |
            tr '\011' ' ' |
            tr -d '\000-\010\013-\037' |
            sed 's/\\/\\\\/g; s/"/\\"/g' |
            awk 'BEGIN{ORS=""} {print (NR>1 ? "\\n" : "") $0}')"
    fi
}

post_json() {
    local url="$1" payload="$2" auth_header="$3"

    if [ "$DOWNLOADER" = "curl" ]; then
        if [ -n "$auth_header" ]; then
            curl -fsS -X POST -H "Content-type: application/json" -H "$auth_header" --data "$payload" "$url"
        else
            curl -fsS -X POST -H "Content-type: application/json" --data "$payload" "$url"
        fi
    else
        if [ -n "$auth_header" ]; then
            wget -q -O - --header="Content-type: application/json" --header="$auth_header" --post-data "$payload" "$url"
        else
            wget -q -O - --header="Content-type: application/json" --post-data "$payload" "$url"
        fi
    fi
}

notify_slack() {
    local text="$1" payload

    if [ -n "${SLACK_BOT_TOKEN:-}" ]; then
        payload="{\"channel\":$(json_escape "$SLACK_CHANNEL"),\"text\":$(json_escape "$text")}"
        post_json "https://slack.com/api/chat.postMessage" "$payload" "Authorization: Bearer $SLACK_BOT_TOKEN" >/dev/null
    elif [ -n "$SLACK_WEBHOOK_URL" ]; then
        payload="{\"text\":$(json_escape "$text")}"
        post_json "$SLACK_WEBHOOK_URL" "$payload" "" >/dev/null
    else
        echo "ℹ️  Slack notification skipped (set SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL)" >&2
        return 0
    fi
}

send_report() {
    local exit_code="$1" text line

    if [ "$exit_code" -eq 0 ]; then
        text="*✅ cc-switch update finished* — $(hostname 2>/dev/null || uname -n)"
    else
        text="*❌ cc-switch update failed (exit $exit_code)* — $(hostname 2>/dev/null || uname -n)"
    fi

    text="$text"$'\n'"*AI CLIs*"
    if [ ${#CLI_LINES[@]} -gt 0 ]; then
        for line in "${CLI_LINES[@]}"; do text="$text"$'\n'"$line"; done
    else
        text="$text"$'\n'"• not reached"
    fi

    text="$text"$'\n'"*CC Switch*"
    if [ ${#CC_LINES[@]} -gt 0 ]; then
        for line in "${CC_LINES[@]}"; do text="$text"$'\n'"$line"; done
    else
        text="$text"$'\n'"• not reached"
    fi

    if [ -n "$ERROR_MSG" ]; then
        text="$text"$'\n'"\`\`\`$ERROR_MSG\`\`\`"
    fi

    notify_slack "$text" || echo "⚠️  Failed to send the Slack notification" >&2
}

finish() {
    local exit_code=$?
    if [ -n "${workdir:-}" ]; then
        rm -rf "$workdir"
    fi
    send_report "$exit_code"
}
trap finish EXIT

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

cli_version() {
    run_as_target "$1" --version 2>/dev/null | head -n1 || true
}

record_cli() {
    local command_name="$1" before="$2" after="$3"

    if [ "$before" = "$after" ]; then
        CLI_LINES+=("• $command_name — already up to date (${after:-unknown})")
    else
        CLI_LINES+=("• $command_name — ${before:-unknown} → ${after:-unknown}")
    fi
}

update_cli() {
    local command_name="$1"
    local npm_package="$2"
    local command_path npm_path npm_prefix before

    command_path=$(target_command_path "$command_name")
    if [ -z "$command_path" ]; then
        echo "⏭️  $command_name is not installed; skipping"
        CLI_LINES+=("• $command_name — not installed, skipped")
        return
    fi

    before=$(cli_version "$command_path")

    if { [ "$command_name" = "claude" ] || [ "$command_name" = "codex" ]; } &&
       [ "$(dirname "$command_path")" = "$target_home/.local/bin" ]; then
        echo "⬆️  Updating $command_name with '$command_name update'"
        run_as_target "$command_path" update
        record_cli "$command_name" "$before" "$(cli_version "$command_path")"
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
        record_cli "$command_name" "$before" "$(cli_version "$command_path")"
    else
        echo "⚠️  Cannot determine how $command_name was installed; skipping" >&2
        CLI_LINES+=("• $command_name — install method unknown, skipped")
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
    die "GitHub API rate limit exceeded. Try again later, or authenticate to raise the limit."
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
    die "Failed to get a valid release tag from the GitHub API (got unexpected content)."
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
    die "Asset $asset not found (or missing checksum) in the latest release of $REPO"
fi

# Record the installed version so the report can show the transition
installed_version=""
if command -v dpkg-query >/dev/null 2>&1; then
    installed_version=$(dpkg-query -W -f='${Version}' cc-switch 2>/dev/null || true)
fi

# Skip if the installed version is already up to date
if [ "$FORCE" = false ] && [ "$installed_version" = "${tag#v}" ]; then
    echo "cc-switch $installed_version is already up to date."
    CC_LINES+=("• already up to date ($tag)")
    exit 0
fi

# Determine how to gain root for installation
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        die "This script must be run as root, or with sudo installed"
    fi
fi

workdir=$(mktemp -d)

download_url="https://github.com/$REPO/releases/download/$tag/$asset"
deb_path="$workdir/$asset"

if ! download_file "$download_url" "$deb_path"; then
    die "Download failed: $download_url"
fi

# Pick the right checksum tool
actual=$(sha256sum "$deb_path" | cut -d' ' -f1)

if [ "$actual" != "$digest" ]; then
    die "Checksum verification failed for $asset (expected $digest, got $actual)"
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
CC_LINES+=("• ${installed_version:-not installed} → ${tag#v} installed")

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
        CC_LINES+=("• restarted (PID $running_pid → $new_pid)")

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
        CC_LINES+=("• ⚠️ could not confirm restart (was PID $running_pid)")
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
    CC_LINES+=("• fixed stale autostart entry")
fi
