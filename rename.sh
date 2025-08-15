#!/usr/bin/env bash

# Rename every file and directory under ./the-graph to lowercase while
# preserving the directory structure. Existing lowercase targets are skipped to
# avoid overwriting.
for SRC in $(find ./the-graph -depth)
do
    DST=$(dirname "${SRC}")/$(basename "${SRC}" | tr '[A-Z]' '[a-z]')
    if [ "${SRC}" != "${DST}" ]
    then
        [ ! -e "${DST}" ] && mv -T "${SRC}" "${DST}" || echo "${SRC} was not renamed"
    fi
done

