from io import BytesIO

from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.generic import Destination, NullObject
from PyPDF2.utils import PdfReadError
from pdf2image import convert_from_bytes

class PDFParser(object):
    path = None

    def __init__(self, path):
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
        return self.pdf.numPages

    def get_next_page(self):
        for page in range(0, self.pdf.numPages):
            tmppdf = BytesIO()
            writer = PdfFileWriter()
            writer.addPage(self.pdf.getPage(page))
            writer.write(tmppdf)
            tmppdf.seek(0)
            yield convert_from_bytes(tmppdf.read(), size=1000, fmt="PNG")[0]
