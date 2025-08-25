#!/usr/bin/env bash

# Description: Rename all files and directories under ./the-graph to lowercase without overwriting existing entries.
# Functioning: Traverses the directory tree and renames each item to its lowercase counterpart if the destination does not exist.
# How to use: Run without arguments from the repository root; it operates on ./the-graph.
for SRC in $(find ./the-graph -depth); do
  DST=$(dirname "${SRC}")/$(basename "${SRC}" | tr '[A-Z]' '[a-z]')
  if [ "${SRC}" != "${DST}" ]; then
    [ ! -e "${DST}" ] && mv -T "${SRC}" "${DST}" || echo "${SRC} was not renamed"
  fi
done
