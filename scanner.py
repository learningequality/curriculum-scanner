from enum import Enum
import json
import os
from fuzzywuzzy import fuzz
from process_scans import get_hash, process_scan
from PIL import Image, ImageDraw
from config import StructureType
from config import SEARCH_THRESHOLD, WRITE_DIRECTORY, BLOCK_BORDER_THICKNESS

# Google break type structures
class BreakType(Enum):
  SPACE = 1
  TAB = 2
  ALT_SPACE = 3
  NEWLINE = 5

BREAK_MAP = {
  BreakType.SPACE.value: ' ',
  BreakType.ALT_SPACE.value: ' ',
  BreakType.TAB.value: '\t',
  BreakType.NEWLINE.value: '\n'
}

BlockOrder = {
  TOPBOTTOM: 'TOPBOTTOM',
  BOTTOMTOP: 'BOTTOMTOP',
  LEFTRIGHT: 'LEFTRIGHT',
  RIGHTLEFT: 'RIGHTLEFT'
}


class CurriculumScanner(object):
  pages = None  # List of pages based on index.json


  def __init__(self, path):
    """
      Constructor for CurriculumScanner

      Args:
        path (str) to file to read from
    """
    self.path = path
    file_id = get_hash(path)
    filename, _ext = os.path.splitext(os.path.basename(self.path))
    self.directory = "{}-{}".format(filename, file_id)
    self.pages = self.load()

  @classmethod
  def process(self, path):
    """
      Runs Google Vision API code on file at given path
        Args: path (str) to file to read
        Returns None
    """
    process_scan(path)

  def load(self):
    """
      Reads index.json file
        Args: None
        Returns dict of index.json data
    """
    index_path = os.path.sep.join([WRITE_DIRECTORY, self.directory, 'index.json'])
    if not os.path.exists(index_path):
      raise RuntimeError('index.json file not found for {}. Please run CurriculumScanner.process(filepath) and try again'.format(self.path))
    with open(index_path, 'rb') as fobj:
      return json.load(fobj)

  def get_page_data(self, page_number):
    """
      Reads <file_id>-<page_number>.json file at a certain page number
        Args: page_number (int) page to read data from
        Returns dict of page data
    """
    with open(self.pages[page_number]['file'], 'rb') as fobj:
      return json.load(fobj)


  def get_next_page(self):
    """ Generator to iterate through pages """
    for page_number, page in self.pages:
      yield self.get_page_data(page_number)


  def get_blocks_by_order(self, page_number, order=BlockOrder.LEFTRIGHT):
    """
      Get the blocks according to a given order
        Args:
          page_number (int) page to get blocks from

    """
    if BlockOrder.get(order):
      raise RuntimeError("Unrecognized format {} (allowed orders: {})".format(order, [o.value for o in BlockOrder]))
    page_data = self.get_page_data(page_number)
    blocks = []

    for page in page_data['pages']:
      if order == 'topbottom':
        blocks.extend(sorted(page['blocks'], key=lambda b: min(v['y'] for v in b['bounding_box']['vertices'])))
      elif order == 'bottomtop':
        blocks.extend(sorted(page['blocks'], key=lambda b: max(v['y'] for v in b['bounding_box']['vertices']), reverse=True))
      elif order == 'rightleft'
        blocks.extend(sorted(page['blocks'], key=lambda b: max(v['x'] for v in b['bounding_box']['vertices']), reverse=True))
      elif order == 'leftright'
        blocks.extend(sorted(page['blocks'], key=lambda b: min(v['x'] for v in b['bounding_box']['vertices'])))
    return blocks

  def text_within(self, page_number, x0=0, y0=0, x1=None, y1=None):
    """
      Finds all text inside a given boundary
        Args:
          page_number (str) to find across pages
          x0 (float) leftmost point for bounds [default: 0]
          y0 (float) topmost point for bounds [default: 0]
          x1 (float) rightmost point for bounds [default: width of page]
          y1 (float) bottommost point for bounds [default: height of page]
        Returns list of all instances a match was found
    """

    # Load data
    page_data = self.get_page_data(page_number)
    x1 = x1 or page_data['pages'][0]['width']
    y1 = y1 or page_data['pages'][0]['height']

    # Get symbols that are inside the bounds
    text=""
    for page in page_data['pages']:
      for block in page['blocks']:
        for paragraph in block['paragraphs']:
          for word in paragraph['words']:
            for symbol in word['symbols']:
              min_x=min([v['x'] for v in symbol['bounding_box']['vertices']])
              max_x=max([v['x'] for v in symbol['bounding_box']['vertices']])
              min_y=min([v['y'] for v in symbol['bounding_box']['vertices']])
              max_y=max([v['y'] for v in symbol['bounding_box']['vertices']])
              if(min_x >= x0 and max_x <= x1 and min_y >= y0 and max_y <= y1):
                text += symbol['text'] + (BREAK_MAP.get(symbol['property']['detected_break']['type']) or '')
    return text

  def draw_box(self, image, bound, color="red", padding=0):
    """
      Draws a box given the bounding_box vertices
      Args:
        image (PIL.Image) image to draw on
        bound (dict) vertices of rectangle
        color (str) color of box [default: 'red']
        padding (int) padding for drawn box
      Returns None
    """
    draw = ImageDraw.Draw(image)
    block_padding = padding * BLOCK_BORDER_THICKNESS
    left_bottom_x = bound['vertices'][0]['x'] - block_padding
    left_bottom_y = bound['vertices'][0]['y'] - block_padding
    right_bottom_x =  bound['vertices'][1]['x'] + block_padding
    right_bottom_y = bound['vertices'][1]['y'] - block_padding
    right_top_x = bound['vertices'][2]['x'] + block_padding
    right_top_y = bound['vertices'][2]['y'] + block_padding
    left_top_x = bound['vertices'][3]['x'] - block_padding
    left_top_y = bound['vertices'][3]['y'] + block_padding

    draw.line([left_bottom_x, left_bottom_y, right_bottom_x, right_bottom_y, right_top_x, right_top_y,
              left_top_x, left_top_y, left_bottom_x, left_bottom_y], fill=color, width=BLOCK_BORDER_THICKNESS)
    return image


  def draw_boxes(self, page_number):
    """
      Draws boxes on blocks, paragraphs, and words
      Args:
        filepath (str) path to image
        directory (str) directory to save file under
        pages (google.cloud.vision.FullTextAnnotation) OCR data
      Returns str path to image with boxes on it

      Blocks = red
      Paragraphs = blue
      Words = yellow
    """
    filepath = self.pages[page_number]['image']
    page_data = self.get_page_data(page_number)
    image = Image.open(filepath)
    for page in page_data['pages']:
      for block in page['blocks']:
        for paragraph in block['paragraphs']:
          for word in paragraph['words']:
            # Draw words
            self.draw_box(image, word['bounding_box'], color="yellow")

          # Draw paragraphs
          self.draw_box(image, paragraph['bounding_box'], color="blue", padding=1)

        # Draw blocks
        self.draw_box(image, block['bounding_box'], padding=2)

    return image


  def find_text_matches(self, text):
    """
      Finds all fuzzy matches of text across pages (SEARCH_THRESHOLD can be updated in config.py)
        Args: text (str) to find across pages
        Returns list of all instances a match was found

      Sample data:
        [
          {
            "page": int,
            "block": int,
            "paragraph": int,
            "word": int,
            "bounds": [
              {"x": int, "y": int},
              ...
            ]
          }
        ]
    """

    # Go through all the pages in index.json
    results = []
    for page_number, _data in enumerate(self.pages):
      page_data = self.get_page_data(page_number)
      for _, page in enumerate(page_data['pages']):
        for block_index, block in enumerate(page['blocks']):
          for paragraph_index, paragraph in enumerate(block['paragraphs']):
            for word_index, word in enumerate(paragraph['words']):

              # Attempt to match word with given text
              ratio = fuzz.token_set_ratio(text, word['text'])
              if ratio > SEARCH_THRESHOLD:
                results.append({
                  "page": page_number,
                  "block": block_index,
                  "paragraph": paragraph_index,
                  "word": word_index,
                  "bounds": word['bounding_box']['vertices']
                })

    return results
