from collections.abc import Iterable
import hashlib
import io
import json
import os

# Imports the Google Cloud client library
from google.cloud import vision
from google.cloud.vision import types
from google.oauth2 import service_account

# Other imports
from progress.bar import Bar
import numpy as np

from pdf_reader import PDFParser
from config import STRUCTURE, WRITE_DIRECTORY

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


def write_block_data(filepath, filename, directory):
  block_file_path = os.path.sep.join([directory, '{}_ocr.json'.format(filename)])

  # if os.path.exists(block_file_path):
  #   return block_file_path

  with open(filepath, 'rb') as image_file:
    content = image_file.read()
  image = types.Image(content=content)
  response = CLIENT.text_detection(image=image)
  image_data = response.full_text_annotation
  data = convert_image_data_to_dict(image_data, STRUCTURE)

  with open(block_file_path, 'wb') as fobj:
    fobj.write(json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8'))

  return {
    "columns": 1,
    "orientation": detect_orientation(response.text_annotations),
    "file": block_file_path,
    "image": filepath
  }

def detect_orientation(annotations):
  for annotation in annotations[1:]:  # Skip first item as it contains the whole sentence
    if len(annotation.description) > 10:  # 10 characters minimum seems to return more accurate results
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

def detect_number_of_columns():
  import pdb; pdb.set_trace()

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
    images = [filepath]

  # Generate data
  index_data = []
  bar = Bar('Writing page data', max=len(images))
  for index, image_path in enumerate(images):
    # Write block data to file
    block_data = write_block_data(image_path, '{}-{}'.format(file_id, index), directory)
    index_data.append(block_data)
    bar.next()
  bar.finish()

  # Write to index.json file
  with open(os.path.sep.join([directory, 'index.json']), 'wb') as fobj:
    fobj.write(json.dumps(index_data, indent=2, ensure_ascii=False).encode('utf-8'))
  print('DONE: data written to {}'.format(directory))

process_scan(os.path.abspath('tests/base.pdf'))
