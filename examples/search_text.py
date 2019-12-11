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

import sys
import os.path
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))

from scanner import CurriculumScanner
from PIL import Image, ImageDraw


if __name__ == '__main__':

  # Make sure file path is provided
  if not len(sys.argv) > 2:
    raise RuntimeError('Usage: examples/search_text.py <filepath> <search text>')

  # Process args
  path = sys.argv[1]
  text = sys.argv[2]

  # Find text matches
  scanner = CurriculumScanner(path)
  results = scanner.find_text_matches(text)

  # Draw a border around all of the results
  images = {}
  for result in results:
    if not images.get(result['page']):
      images[result['page']] = Image.open(scanner.data[result['page']]['image'])

    image = images[result['page']]
    draw = ImageDraw.Draw(image)
    bounds = result['bounds']
    draw.line([bounds[0]['x'], bounds[0]['y'],
              bounds[1]['x'], bounds[1]['y'],
              bounds[2]['x'], bounds[2]['y'],
              bounds[3]['x'], bounds[3]['y'],
              bounds[0]['x'], bounds[0]['y']], fill='yellow', width=3)

  # Show the images
  for _k, image in images.items():
    image.show()
