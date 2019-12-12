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

from io import BytesIO

from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.generic import Destination, NullObject
from PyPDF2.utils import PdfReadError
from pdf2image import convert_from_bytes
from PIL import Image
from PIL import ImageEnhance
from config import PAGE_RESOLUTION
from config import IMAGE_CONTRAST


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
      enhanced = ImageEnhance.Contrast(image).enhance(IMAGE_CONTRAST)
      yield enhanced
