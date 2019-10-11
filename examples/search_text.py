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
