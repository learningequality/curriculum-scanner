#!/usr/bin/env bash

echo 'Deleting .DS_Store junk files'
find chunkedscans/  -name '.DS_Store*' -print0 | xargs -0 rm

