#!/bin/bash

# We stop the installation as soon as a command reports a failure.
set -e

# We define terminal colors for the installation messages.
CYAN='\033[1;36m'
GREEN='\033[1;32m'
NC='\033[0m' # We reset the terminal formatting after colored output.

# We show the project banner before starting the download.
echo -e "${CYAN}"
cat << "EOF"
    _         _                  _              _           
   / \   ___ | |_  _ __    ___  | |_  _ __ __ _| |_  ___  ___ 
  / _ \ / __|| __|| '__|  / _ \ | __|| '__/ _` | __|/ _ \/ __|
 / ___ \\__ \| |_ | |    | (_) || |_ | | | (_| | |_ \__ \__ \
/_/   \_\|___/ \__||_|     \___/  \__||_|  \__,_|\__||___/___/
EOF
echo -e "${NC}"

echo -e "${GREEN}=== Starting PocketBase v0.42.2 Installation ===${NC}"

URL="https://ganigeorgiev.com/meta/pocketbase/pocketbase/download/v0.42.2/pocketbase_0.42.2_linux_amd64.zip"
ZIP_NAME="pocketbase_0.42.2_linux_amd64.zip"

# We use curl when it is available and fall back to wget otherwise.
if command -v curl &> /dev/null; then
    echo "Downloading PocketBase using curl..."
    curl -L -o "$ZIP_NAME" "$URL"
elif command -v wget &> /dev/null; then
    echo "Downloading PocketBase using wget..."
    wget -O "$ZIP_NAME" "$URL"
else
    echo "Error: Neither curl nor wget is installed. Please install one and try again." >&2
    exit 1
fi

# We check that we can extract the archive before continuing.
if ! command -v unzip &> /dev/null; then
    echo "Error: 'unzip' utility is not installed. Please install it (e.g., sudo apt install unzip) and try again." >&2
    rm -f "$ZIP_NAME"
    exit 1
fi

echo "Extracting PocketBase into the current directory..."
# We extract into the current working directory and then remove the archive.
unzip -o "$ZIP_NAME"
rm -f "$ZIP_NAME"

echo -e "${GREEN}=== Installation Complete! ===${NC}"
echo "You can now run PocketBase with:"
echo "  ./pocketbase serve"


# We use the PocketBase installer instead of promising account credentials
# that this script has not created.
echo "Create the first administrator using the installer link printed by PocketBase."

