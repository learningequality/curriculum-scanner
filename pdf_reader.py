from io import BytesIO

from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.generic import Destination, NullObject
from PyPDF2.utils import PdfReadError
from pdf2image import convert_from_bytes
from PIL import Image
from PIL import ImageEnhance
from config import PAGE_RESOLUTION

class PDFParser(object):
  path = None

  def __init__(self, path):
    """
      Initializes PDFParser object
      Args: path (str) to pdf
      Returns None
    """
    self.path = path

  def __enter__(self):
    """ Called when opening context (e.g. with HTMLWriter() as writer: ) """
    self.open()
    return self

  def __exit__(self, type, value, traceback):
    """ Called when closing context """
    self.close()


  def open(self):
    """ open: Opens pdf file to read from
      Args: None
      Returns: None
    """

    self.file = open(self.path, 'rb')
    self.pdf = PdfFileReader(self.file)

  def close(self):
    """ close: Close main pdf file when done
      Args: None
      Returns: None
    """
    self.file.close() # Make sure zipfile closes no matter what

  def get_num_pages(self):
    """
      Returns the number of pages in the pdf
    """
    return self.pdf.numPages

  def get_next_page(self):
    """
      Generator for images of each pdf page
      Args: None
      Returns PIL.Image of pdf page
    """
    for page in range(0, self.pdf.numPages):
      tmppdf = BytesIO()
      writer = PdfFileWriter()
      writer.addPage(self.pdf.getPage(page))
      writer.write(tmppdf)
      tmppdf.seek(0)

      # Enhance image to make it more accurate to read
      image = convert_from_bytes(tmppdf.read(), size=PAGE_RESOLUTION, fmt="PNG")[0]
      enhanced = ImageEnhance.Sharpness(image).enhance(1)
      enhanced = ImageEnhance.Contrast(enhanced).enhance(2)
      greyscale = enhanced.convert('L')
      yield greyscale
