#!/usr/bin/env bash

set -euo pipefail

# Description: Perform an in-place search/replace on a remote file accessible via rclone.
# Functioning: Copies the remote file to a ott-mgt temp path, runs a sed substitution, then copies the result back to the remote.
# How to use: ./bash/search-replace-rclone.sh <remote_path> <search_value> <replace_value>

REMOTE_PATH="${1:?Missing remote path (e.g. remote:bucket/path/file.txt)}"
SEARCH_VALUE="${2:?Missing search value}"
REPLACE_VALUE="${3:?Missing replace value}"
FILE=$(basename $REMOTE_PATH)

rclone copy "${REMOTE_PATH}" "/tmp"
echo "copied ${REMOTE_PATH} to /tmp/$FILE"

sed -i "s/${SEARCH_VALUE}/${REPLACE_VALUE}/g" "/tmp/$FILE"
echo "replaced ${SEARCH_VALUE} to ${REPLACE_VALUE}"

rclone moveto "/tmp/$FILE" "${REMOTE_PATH}"
echo "copied back /tmp/$FILE to ${REMOTE_PATH}"
