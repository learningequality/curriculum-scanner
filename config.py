##################################################
# MIT License
#
# Copyright (c) 2019 Learning Equality
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
##################################################

import os

from enum import Enum

###############################################################################
#
# Google Vision API Structures
#
###############################################################################

SYMBOL_STRUCTURE = {
    "name": "symbols",
    "fields": ["confidence", "text"],
    "objects": ["bounding_box", "property"],
}

WORD_STRUCTURE = {
    "name": "words",
    "fields": ["confidence"],
    "objects": ["bounding_box", "property"],
    "list": SYMBOL_STRUCTURE,
}

PARAGRAPH_STRUCTURE = {
    "name": "paragraphs",
    "fields": ["confidence"],
    "objects": ["bounding_box", "property"],
    "list": WORD_STRUCTURE,
}

BLOCK_STRUCTURE = {
    "name": "blocks",
    "fields": ["block_type", "confidence"],
    "objects": ["bounding_box", "property"],
    "list": PARAGRAPH_STRUCTURE,
}

PAGE_STRUCTURE = {
    "name": "pages",
    "fields": ["confidence", "height", "width"],
    "objects": ["property"],
    "list": BLOCK_STRUCTURE,
}

STRUCTURE = {
    "name": "overall",
    "fields": ["text"],
    "objects": [],
    "list": PAGE_STRUCTURE,
}


class StructureType(Enum):
    PAGE = 1
    BLOCK = 2
    PARA = 3
    WORD = 4
    SYMBOL = 5


###############################################################################
#
# Configurations
#
###############################################################################

# Directory to write json and image files to
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Directory containing curriculum PDF source files to be scanned.
INPUT_DIRECTORY = os.path.join(BASE_DIR, "inputs")

VISION_RESPONSE_DIRECTORY = os.path.join(BASE_DIR, 'vision')
if not os.path.exists(VISION_RESPONSE_DIRECTORY):
  os.makedirs(VISION_RESPONSE_DIRECTORY)

# Director where structued OCR outputs are stored.
WRITE_DIRECTORY = "scans"

# Allowed formats for processing
ALLOWED_FORMATS = [".pdf", ".png", ".jpg", ".jpeg"]

# Path to credentials json for Google Vision API
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials", "client_secret.json")

# Minimum number of characters to use to determine text orientation
#  - Higher = better chance of correct orientation detection
#  - Lower = better chance of finding a string longer than this length
ORIENTATION_DETECTION_THRESHOLD = 10

# Buffer space between columns
#  - Higher = more tolerant column width detection
#  - Lower = stricter column width detection
COLUMN_DETECTION_THRESHOLD = 50

# Resolution to save PDF images in
#  - Higher = better text recognition
#  - Lower = better memory usage
PAGE_RESOLUTION = 1200

# The line width for block borders
BLOCK_BORDER_THICKNESS = 2

# Image contrast enhancement level
#  - Higher = text may be clearer
#  - Lower = less chance of text blurring with background
IMAGE_CONTRAST = 2

# % matching characters to be included in the search results
SEARCH_THRESHOLD = 90

# Multiplier for how big a space should be to be considered a bullet
# (bullet detected if space > average character size * threshold)
BULLET_THRESHOLD = 2
