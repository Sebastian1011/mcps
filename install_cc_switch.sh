#!/bin/bash

set -e

REPO="farion1231/cc-switch"
API_URL="https://api.github.com/repos/$REPO/releases/latest"
FORCE=false

if [ "$1" = "--force" ]; then
    FORCE=true
fi

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

# Install (prefer apt-get so dependencies are resolved)
if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get install -y "$deb_path"
else
    $SUDO dpkg -i "$deb_path"
fi

echo ""
echo "✅ Installed CC Switch $tag"
echo ""
