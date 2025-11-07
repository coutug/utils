#!/usr/bin/env bash

set -euo pipefail

# Usage : ./script.sh <remote_path> <tmp_filename> <search_value> <replace_value>

REMOTE_PATH="${1:?Missing remote path (e.g. remote:bucket/path/file.txt)}"
TMP_FILENAME="${2:?Missing tmp filename (e.g. /tmp/file.txt)}"
SEARCH_VALUE="${3:?Missing search value}"
REPLACE_VALUE="${4:?Missing replace value}"

rclone copy "${REMOTE_PATH}" "${TMP_FILENAME}"
echo "copied ${REMOTE_PATH} to ${TMP_FILENAME}"

sed -i "s/${SEARCH_VALUE}/${REPLACE_VALUE}/g" "${TMP_FILENAME}"
echo "replaced ${SEARCH_VALUE} to ${REPLACE_VALUE}"

rclone copy "${TMP_FILENAME}" "${REMOTE_PATH}"
echo "copied back ${TMP_FILENAME} to ${REMOTE_PATH}"
