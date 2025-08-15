#!/bin/sh

DIR=$(pwd)
echo "running from $DIR"
shopt -s nullglob
find . -type f \( -name "*.enc" -o -name "*.env" \) | while read -r file; do
    echo "Updating: $file"
    cd $(dirname "$file")
    sops updatekeys $(basename "$file") -y
    cd $DIR
done