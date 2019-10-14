from collections.abc import Iterable
from enum import Enum
import hashlib
import io
import itertools
import json
import os
import pickle
import shutil
import sys

# Imports the Google Cloud client library
from google.cloud import vision
from google.cloud.vision import types
from google.oauth2 import service_account

# External library imports
from progress.bar import Bar
import numpy as np
from PIL import Image, ImageDraw
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


# Project imports
from pdf_reader import PDFParser
from config import ALLOWED_FORMATS
from config import CREDENTIALS_PATH
from config import COLUMN_DETECTION_THRESHOLD
from config import ORIENTATION_DETECTION_THRESHOLD
from config import STRUCTURE
from config import WRITE_DIRECTORY

# Instantiates a Google Vision API client to be used for text detection
credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)
CLIENT = vision.ImageAnnotatorClient(credentials=credentials)

VISION_RESPONSE_DIRECTORY = 'vision'
if not os.path.exists(VISION_RESPONSE_DIRECTORY):
  os.makedirs(VISION_RESPONSE_DIRECTORY)

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


###############################################################################
#
# Step 1: Set up file path to write to
#
###############################################################################

def get_hash(filepath):
  """
    Generates unique ID based on hash of the file
      Args: filepath (str) path to file to read
      Returns hash of file
  """
  filehash = hashlib.md5()

  with open(filepath, 'rb') as fobj:
    for chunk in iter(lambda: fobj.read(2097152), b""):
      filehash.update(chunk)

  return filehash.hexdigest()


###############################################################################
#
# Step 2: Convert each pdf page to an image
#
###############################################################################

def generate_images_from_pdf(filepath, file_id, directory):
  """
    Reads the pdf and creates an image of each page
      Args:
        filepath (str) path to pdf
        file_id (str) unique id to use in image filename (<file_id>-<page number>.png)
        directory (str) directory to save generated images under
      Returns list of image paths to the newly generated image files
  """
  images = []
  with PDFParser(filepath) as parser:
    bar = Bar('Converting pages to images', max=parser.get_num_pages())
    for index, image in enumerate(parser.get_next_page()):

      # Generate filepath and save the image if it doesn't exist yet
      image_path = get_path(directory, index, "{}-{}.png".format(file_id, index))
      if not os.path.exists(image_path):
        image.save(image_path)

      images.append(image_path)
      bar.next()
    bar.finish()
  return images


###############################################################################
#
# Step 3: Auto-rotate images based on detected orientation
#
###############################################################################

def get_text_detection(filepath, filename, suffix=""):
  """
    Runs Google Vision API text_detection and returns result
    Args:
      filepath (str) path to file to use in detection
      filename (str) unique id of file
      suffix (str) extra string to use to save data
    Returns google.cloud.vision.Response object
  """

  # See if the data has already be generated
  pickle_path = '{}/{}{}.pickle'.format(VISION_RESPONSE_DIRECTORY, filename, '-' + suffix if suffix else '')
  if os.path.exists(pickle_path):
    with open(pickle_path, 'rb') as token:
      return pickle.load(token)

  # Read the file and run vision api on its text to get bounding polygons
  with io.open(filepath, 'rb') as image_file:
    content = image_file.read()
  vision_image = types.Image(content=content)
  response = CLIENT.document_text_detection(image=vision_image)

  # Write to pickle file
  with open(pickle_path, 'wb') as token:
    pickle.dump(response, token)

  return response


def detect_orientation(text_annotations):
  """
    Detects the rotation of the text
      Args: text_annotations (google.cloud.vision.TextAnnotations) annotations from Vision API
      Returns degrees of rotation (int)

    Logic:
      Using a test point (P), determine how the text is rotated
      based on its orientation to the center of the bounding polygon

      P -------- #    # -------- P    # -------- #    # -------- #
      |    0°    |    |    90°   |    |   180°   |    |   270°   |
      # -------- #    # -------- #    # -------- P    P -------- #
  """


  # Find the first description that is longer than the threshold
  # (Skip first item as it contains the whole sentence)
  for annotation in text_annotations[1:]:
    if len(annotation.description) > ORIENTATION_DETECTION_THRESHOLD:
      break;

  # Determine the center of the text
  center_x = np.mean([v.x for v in annotation.bounding_poly.vertices])
  center_y = np.mean([v.y for v in annotation.bounding_poly.vertices])

  # Select a test point
  first_point = annotation.bounding_poly.vertices[0]

  # Determine the text's orientation
  if first_point.x < center_x:
    if first_point.y < center_y:
      return 0
    else:
      return 270
  else:
    if first_point.y < center_y:
      return 90
    else:
      return 180


def autocorrect_image(filepath):
  """
    Rotates image based on its detected orientation
      Args: filepath (str) path to image
      Returns degrees of rotation (int)
  """
  filename, _ext = os.path.splitext(os.path.basename(filepath))
  image = Image.open(filepath)

  # Get Vision API data
  response = get_text_detection(filepath, filename, suffix="original")

  # Rotate and save the image if it's not properly oriented
  orientation = detect_orientation(response.text_annotations)
  if orientation != 0:
    rotated = image.rotate(orientation, expand=1)

    # Straighten image
    (w,h) = rotated.size
    rotated = rotated.transform(rotated.size, Image.QUAD, (0,0,0,h,w,h,w,0))

    rotated.save(filepath)

  return orientation


###############################################################################
#
# Step 4: Write blocks data to json files and save bounding box images
#
###############################################################################

def draw_bounding_box(image, bound, color="red"):
  """
    Draws a box given the bounding_box.vertices
    Args:
      image (PIL.Image) image to draw on
      bound (google.cloud.vision bounding_box) vertices of rectangle
      color (str) color of box [default: 'red']
    Returns None
  """
  draw = ImageDraw.Draw(image)
  draw.line([bound.vertices[0].x, bound.vertices[0].y,
            bound.vertices[1].x, bound.vertices[1].y,
            bound.vertices[2].x, bound.vertices[2].y,
            bound.vertices[3].x, bound.vertices[3].y,
            bound.vertices[0].x, bound.vertices[0].y], fill=color, width=4)


def draw_boxes_on_image(filepath, directory, pages):
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
  save_to_path = '{}_boxes.png'.format(directory)
  image = Image.open(filepath)
  for page in pages:
    for block in page.blocks:
      for paragraph in block.paragraphs:
        for word in paragraph.words:
          # Draw words
          draw_bounding_box(image, word.bounding_box, color="yellow")

        # Draw paragraphs
        draw_bounding_box(image, paragraph.bounding_box, color="blue")

      # Draw blocks
      draw_bounding_box(image, block.bounding_box)
  image.save(save_to_path)
  return save_to_path


def convert_object_to_dict(obj):
  """
    Read the fields for the object and convert it to a dict
    Args: obj (object) to write dict from
    Returns dict of object fields and values
  """
  data = {}

  # Read through all the fields on the object
  for field in dir(obj):
    try:
      value = getattr(obj, field)
      # Don't process hidden fields, camel case field, or functions
      if field.islower() and not field.startswith('_') and not callable(value):
        json.dumps(value)  # Check if this is serializable
        data[field] = value
    except AttributeError:
      continue
    except:
      try:
        # If the field value is a list, go through and convert list items to objects
        if isinstance(value, Iterable):
          data[field] = []
          for item in value:
            data[field].append(convert_object_to_dict(item))

        # Otherwise, just try to convert the object to a dict
        else:
          data[field] = convert_object_to_dict(value)
      except:
        pass

  return data


def convert_image_data_to_dict(item, structure):
  """
    Serializes Google Vision API's returned data object
    Args:
      item (google.cloud.vision object): object to serialize
      structure (dict): structure to parse object with (see config.py)
    Returns serialized dict of object values
  """
  data = {}

  # Copy fields
  for field in structure['fields']:
    data[field] = getattr(item, field)

  # Copy objects
  for obj_name in structure['objects']:
    data[obj_name] = {}
    obj = getattr(item, obj_name)
    data[obj_name] = convert_object_to_dict(obj)

  # Go through list
  if structure.get('list'):
    data[structure['list']['name']] = [
      convert_image_data_to_dict(list_item, structure['list'])
      for list_item in getattr(item, structure['list']['name'])
    ]
  return data


def detect_columns(filepath, image_data):
  """
    Detects how many columns are in the object based on the texts' bounding boxes
    Args: image_data (google.cloud.vision.full_text_annotation) data to use for detection
    Returns number of columns detected
  """

  # Set up variables for collecting info on image
  mins = []
  maxes = []
  dataset = []

  # Collect starting x values for each block
  for page in image_data.full_text_annotation.pages:
    for y, block in enumerate(page.blocks):
      x0 = float(min([v.x for v in block.bounding_box.vertices]))
      mins.append(x0)
      maxes.append(max([v.x for v in block.bounding_box.vertices]))

      # Append the point to the dataset for each paragraph to give
      # it more weight, making sure that the point is unique as
      # k-means needs the set of points and will remove duplicates
      for i, paragraph in enumerate(block.paragraphs):
        while (x0, 0) in dataset:
          x0 += 0.5
        dataset.append((x0, 0))

  # Get clustered points
  max_width = max(maxes)
  column_clusters = (1, [min(mins)])
  if len(set(dataset)) > 2:
    sil = []
    for k in range(2, len(set(dataset))):
      kmeans = KMeans(n_clusters = k).fit(dataset)
      score = silhouette_score(dataset, kmeans.labels_, metric = 'correlation')
      cluster_centers = [c[0] for c in kmeans.cluster_centers_]
      sil.append((score, cluster_centers))
    column_clusters = next(((i + 2, s[1]) for i, s in enumerate(sil) if s[0] > 0), column_clusters)

  # Collect ranges based on boxes that fall into
  ranges = []
  if column_clusters[0] == 1:
    ranges = [(column_clusters[1][0], max_width)]

  else:
    radius = (max_width / column_clusters[0]) / 2 + COLUMN_DETECTION_THRESHOLD
    for starting_point in column_clusters[1]:
      x_range = {}
      for page in image_data.full_text_annotation.pages:
        for block in page.blocks:
          x0 = min([v.x for v in block.bounding_box.vertices])
          x1 = max([v.x for v in block.bounding_box.vertices])
          x_values = set(range(x0, x1))

          # Get highest width of boxes that are within the radius of the starting point
          if starting_point - radius <= x0 and x0 <= starting_point + radius \
            and x1 - x0 <= max_width / column_clusters[0] :
            x_range['x0'] = min(x0, x_range['x0']) if x_range.get('x0') else x0
            x_range['x1'] = max(x1, x_range['x1']) if x_range.get('x1') else x1

      if x_range:
        ranges.append((x_range['x0'], x_range['x1']))

  return ranges


def write_text_fields(data):
  """
    Adds text field to data
    Args:
      data (google.cloud.vision.FullTextAnnotation) OCR data
    Returns None
  """
  for page in data['pages']:
    page_text = ''
    for block in page['blocks']:
      block_text = ''
      for paragraph in block['paragraphs']:
        paragrph_text = ''
        for word in paragraph['words']:
          word_text = ''
          for symbol in word['symbols']:
            break_char = BREAK_MAP.get(symbol['property']['detected_break']['type']) or ''
            word_text += symbol['text'] + break_char
          word['text'] = word_text
          paragrph_text += word_text
        paragraph['text'] = paragrph_text
        block_text += paragrph_text
      block['text'] = block_text
      page_text += block_text + '\n\n'
    page['text'] = page_text


def write_block_data(filepath, save_to_path):
  """
    Writes the Google Vision API generated data to a json file
    Args:
      filepath (str) path to file to read
      filename (str) name of json file to write to
      directory (str) directory to save json file under
    Returns dict of metadata for the index.json file
  """
  # Generate path to write data to
  block_file_path = '{}_ocr.json'.format(save_to_path)

  # Read the file and generate data
  # Note: Cannot reuse the data from detect_orientation as the bounding boxes
  #       may have changed due to the image rotating
  response = get_text_detection(filepath, os.path.basename(save_to_path))

  # Convert the objects to a serializable dict
  image_data = response.full_text_annotation
  data = convert_image_data_to_dict(image_data, STRUCTURE)
  write_text_fields(data)

  # Write the data to the file
  with open(block_file_path, 'wb') as fobj:
    fobj.write(json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8'))

  # Return metadata to be saved under index.json file
  return {
    "columns": detect_columns(filepath, response),
    "file": block_file_path,
    "image": filepath,
    "boxes": draw_boxes_on_image(filepath, save_to_path, response.full_text_annotation.pages)
  }


###############################################################################
#
# MAIN PROCESSING FUNCTION
#
###############################################################################

def get_path(file_id, index, filename):
  """
    Generates a file path to write to
      Args:
        file_id (str) unique id for file
        index (int) page number
        filename (str) name of file to save to
      Returns str write to path
  """
  directory = os.path.sep.join([file_id, str(index)])
  if not os.path.exists(directory):
    os.makedirs(directory)

  return os.path.sep.join([directory, filename])

def process_scan(filepath):
  """
    Generates images and json files under a `<filename>-<hash of file>` folder
    Args: filepath (str) path to file to process
    Returns None

    Output:
      <filename>-<hash of file>
      -- index.json
      -- <filename>-<hash of file>-1.png
      -- <filename>-<hash of file>-1_ocr.json
      -- <filename>-<hash of file>-2.png
      -- <filename>-<hash of file>-2_ocr.json

    Where index.json stores the order of the pages as well as the following data:
      {
        "columns": int,  # Number of columns detected
        "file": str,     # Path to json file with Google Vision API data
        "image": str,    # Path to image that was used to generate data
      }
  """

  # Step 1: Set up file path to write to
  print('Processing {}'.format(filepath))
  filename, ext = os.path.splitext(os.path.basename(filepath))

  # Make sure the file is an accepted format before attempting to process it
  if ext.lower() not in ALLOWED_FORMATS:
    print('Skipping file, unknown format: {}'.format(filepath))
    print('(allowed formats: {})'.format(', '.join(ALLOWED_FORMATS)))
    # return false so that calling code can decide to raise, give non-zero exit code, etc.
    return False

  filehash = get_hash(filepath)
  file_id = '{}-{}'.format(filename, filehash)

  # Create directory
  directory = os.path.sep.join([WRITE_DIRECTORY, file_id])
  if not os.path.exists(directory):
    os.makedirs(directory)


  # Step 2: Convert each pdf page to an image
  images = []
  if ext.lower() == '.pdf':  # Parse pdfs
    images = generate_images_from_pdf(filepath, file_id, directory)

  # Or copy the file to same folder as json files if it's already an image
  else:
    image_path = get_path(directory, 0, "{}-0{}".format(file_id, ext))
    shutil.copyfile(filepath, image_path)
    images = [image_path]

  # Generate json files for each image
  index_data = []
  bar = Bar('Writing page data', max=len(images))
  for index, image_path in enumerate(images):

    # Step 3: Auto-rotate images based on detected orientation
    autocorrect_image(image_path)

    # Step 4: Write blocks data to json files and save bounding box images
    save_to_path = get_path(directory, index, '{}-{}'.format(file_id, index))
    block_data = write_block_data(image_path, save_to_path)
    index_data.append(block_data)
    bar.next()

  bar.finish()

  # Step 5: Write index.json file
  with open(os.path.sep.join([directory, 'index.json']), 'wb') as fobj:
    fobj.write(json.dumps(index_data, indent=2, ensure_ascii=False).encode('utf-8'))
  print('DONE: data written to {}'.format(directory))
  return True


def process_dir(directory):
  for afile in os.listdir(directory):
    filepath = os.path.join(directory, afile)
    process_scan(filepath)


###############################################################################
#
# CLI
#
###############################################################################

if __name__ == '__main__':

  # Make sure file path is provided
  if not len(sys.argv) > 1:
    raise RuntimeError('Filepath to curriculum must be included (Usage: process_scans.py <filepath>)')

  # Make sure the file exists at the given path
  elif not os.path.exists(sys.argv[1]):
    raise RuntimeError('{} not found'.format(sys.argv[1]))

  if os.path.isdir(sys.argv[1]):
    process_dir(sys.argv[1])
  else:
    process_scan(os.path.abspath(sys.argv[1]))
