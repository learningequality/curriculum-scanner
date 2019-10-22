#!/usr/bin/env bash

echo 'Deleting all PNG files from chunkedscans/ directory'
find chunkedscans/  -name '*png' -print0 | xargs -0 rm

echo 'Deleting all OCR output files from chunkedscans/ directory'
find chunkedscans/  -name '*_ocr.json' -print0 | xargs -0 rm
find chunkedscans/  -name '*_ocr.txt' -print0 | xargs -0 rm
find chunkedscans/  -name '*_combined.txt' -print0 | xargs -0 rm

echo 'Deleting .DS_Store junk files'
find chunkedscans/  -name '.DS_Store*' -print0 | xargs -0 rm
