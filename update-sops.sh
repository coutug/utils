#!/usr/bin/env bash

# Description: Refresh SOPS encryption keys for all *.enc and *.env files recursively.
# Functioning: Finds matching files, runs `sops updatekeys` on each, and returns to the starting directory.
# How to use: Run from the repository root; requires `sops` in the PATH.

DIR=$(pwd)
echo "running from $DIR"
shopt -s nullglob
find . -type f \( -name "*.enc" -o -name "*.env" \) | while read -r file; do
    echo "Updating: $file"
    cd $(dirname "$file")
    sops updatekeys $(basename "$file") -y
    cd $DIR
done