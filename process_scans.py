from collections.abc import Iterable
import hashlib
import io
import json
import os
import shutil

# Imports the Google Cloud client library
from google.cloud import vision
from google.cloud.vision import types
from google.oauth2 import service_account

# Other imports
from progress.bar import Bar
import numpy as np
from PIL import Image

from pdf_reader import PDFParser
from config import STRUCTURE, WRITE_DIRECTORY, ORIENTATION_DETECTION_THRESHOLD

# Instantiates a client
credentials = service_account.Credentials.from_service_account_file('credentials/client_secret.json')
CLIENT = vision.ImageAnnotatorClient(credentials=credentials)

def get_hash(filepath):
  filehash = hashlib.md5()

  with open(filepath, 'rb') as fobj:
    for chunk in iter(lambda: fobj.read(2097152), b""):
      filehash.update(chunk)

  return filehash.hexdigest()

def convert_object_to_dict(obj):
  data = {}
  for field in dir(obj):
    try:
      value = getattr(obj, field)
      if field.islower() and not field.startswith('_') and not callable(value):
        json.dumps(value)  # Check if this is serializable
        data[field] = value
    except AttributeError:
      continue
    except:
      try:
        if isinstance(value, Iterable):
          data[field] = []
          for item in value:
            data[field].append(convert_object_to_dict(item))
        else:
          data[field] = convert_object_to_dict(value)
      except:
        pass

  return data

def convert_image_data_to_dict(item, structure):
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

def detect_orientation(annotations):
  for annotation in annotations[1:]:  # Skip first item as it contains the whole sentence
    if len(annotation.description) > ORIENTATION_DETECTION_THRESHOLD:
      break;

  center_x = np.mean([v.x for v in annotation.bounding_poly.vertices])
  center_y = np.mean([v.y for v in annotation.bounding_poly.vertices])

  first_point = annotation.bounding_poly.vertices[0]

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


def rotate_image(filepath):
  with open(filepath, 'rb') as image_file:
    content = image_file.read()
  image = types.Image(content=content)
  response = CLIENT.text_detection(image=image)
  orientation = detect_orientation(response.text_annotations)

  if orientation != 0:
    with Image.open(filepath) as image:
      rotated = image.rotate(orientation, expand=1)
      rotated.save(filepath)

  return orientation


def write_block_data(filepath, filename, directory):
  block_file_path = os.path.sep.join([directory, '{}_ocr.json'.format(filename)])

  # if os.path.exists(block_file_path):
  #   return block_file_path

  rotate_image(filepath)

  with open(filepath, 'rb') as image_file:
    content = image_file.read()
  image = types.Image(content=content)
  response = CLIENT.text_detection(image=image)

  image_data = response.full_text_annotation
  data = convert_image_data_to_dict(image_data, STRUCTURE)

  with open(block_file_path, 'wb') as fobj:
    fobj.write(json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8'))

  return {
    "columns": detect_number_of_columns(image_data),
    "file": block_file_path,
    "image": filepath
  }


def detect_number_of_columns(image_data):
  number_of_columns = 0
  for page in image_data.pages:
    max_y = 0
    max_x = 0
    for block in page.blocks:
      string = ''
      for paragraph in block.paragraphs:
        for word in paragraph.words:
          for symbol in word.symbols:
            string += symbol.text
      print("String: ", string.strip())

      print(block.bounding_box.vertices[0].x,  block.bounding_box.vertices[-2].x, block.bounding_box.vertices[0].y, block.bounding_box.vertices[-2].y)

  return number_of_columns

def generate_images_from_pdf(filepath, file_id, directory):
  images = []
  with PDFParser(filepath) as parser:
    # Write page images to image file
    bar = Bar('Converting pages to images', max=parser.get_num_pages())
    for index, image in enumerate(parser.get_next_page()):
      image_path = os.path.sep.join([directory, "{}-{}.png".format(file_id, index)])
      if not os.path.exists(image_path):
        image.save(image_path)
      images.append(image_path)
      bar.next()
    bar.finish()
  return images

def process_scan(filepath):
  print('Processing {}'.format(filepath))
  # Set up write to path
  filename, ext = os.path.splitext(os.path.basename(filepath))
  filehash = get_hash(filepath)
  file_id = '{}-{}'.format(filename, filehash)

  # Create directory
  directory = os.path.sep.join([WRITE_DIRECTORY, file_id])
  if not os.path.exists(directory):
    os.makedirs(directory)

  # Get images
  images = []
  if ext.lower() == '.pdf':  # Parse pdfs
    images = generate_images_from_pdf(filepath, file_id, directory)
  else:  # Parse images
    image_path = os.path.sep.join([directory, "{}-1{}".format(file_id, ext)])
    if not os.path.exists(image_path):
      shutil.copyfile(filepath, image_path)
    images = [image_path]

  # Generate data
  index_data = []
  bar = Bar('Writing page data', max=len(images))
  for index, image_path in enumerate(images[:1]):
    # Write block data to file
    block_data = write_block_data(image_path, '{}-{}'.format(file_id, index), directory)
    index_data.append(block_data)
    bar.next()
  bar.finish()

  # Write to index.json file
  with open(os.path.sep.join([directory, 'index.json']), 'wb') as fobj:
    fobj.write(json.dumps(index_data, indent=2, ensure_ascii=False).encode('utf-8'))
  print('DONE: data written to {}'.format(directory))

process_scan(os.path.abspath('tests/columns.jpg'))
