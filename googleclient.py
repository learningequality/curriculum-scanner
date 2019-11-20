from io import BytesIO
import re

from config import CREDENTIALS_PATH
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from bs4 import BeautifulSoup

DRIVE_FOLDER = '1x2EhRa6sQhCDW0EwLcuNcIdT7lqEH0TN'
TEXT_CHUNK_SIZE = 500

class ListItem(object):
  def __init__(self, indent, item_type, text):
    self.type = item_type
    self.indent = indent
    self.text = text.strip().capitalize()
    self.notes = ""

  def add_notes(self, text, indent=0):
    self.notes += '\n{}- {}'.format('\t' * indent, text.strip())

class List(list):
  def get_last_of_kind(self, kind):
    return [i for i in self if i.type == kind][-1]


class GoogleDriveClient(object):
  def __init__(self):
    self.credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)
    self.service = build('drive', 'v3', credentials=self.credentials)

  def set_permission(self, file_id):
    anyone_permission = {
      'type': 'anyone',
      'role': 'writer'
    }
    self.service.permissions().create(
      fileId=file_id,
      body=anyone_permission,
      fields='id',
    ).execute()

  def create_folder(self, folder_name):
    data = {
      'name': folder_name,
      'mimeType': 'application/vnd.google-apps.folder',
      'parents': [DRIVE_FOLDER]
    }
    return self.service.files().create(body=data, fields='id').execute()

  def create_google_doc(self, filename, text):

    text = text.encode('utf-8') if isinstance(text, str) else text

    doc_text = BytesIO()
    doc_text.write(text)

    data = {
      'name': filename,
      'mimeType':  'application/vnd.google-apps.document',
      'parents': [DRIVE_FOLDER]
    }
    media = MediaIoBaseUpload(doc_text, mimetype="text/html", resumable=True)

    file = self.service.files().create(body=data, media_body=media, fields='id').execute()
    self.set_permission(file['id'])

  def get_doc(self, file_id):
    download = BytesIO()
    request = self.service.files().export_media(fileId=file_id, mimeType='text/html')
    downloader = MediaIoBaseDownload(download, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    download.seek(0)
    return download

  def convert_html_to_structure(self, contents):
    page = BeautifulSoup(contents, 'html.parser')

    results = List([])
    iterator = iter([c for c in page.find('body').children if c.name =='p' or c.name =='ul'])

    item = next(iterator, None)
    while item:
      keep_in_place = False
      # Get subjects and levels
      if item.name == 'p':
        if 'form' in item.text.lower():
          results.append(ListItem(2, 'level', item.text))
        else:
          results.append(ListItem(1, 'subject', item.text))

      # Get topics, content, and learning objectives
      elif item.name == 'ul':
        for list_item in item.find_all('li'):
          # Determine how to categorize based on indent and bullet
          header = re.search(r"\d+\.(\d+)\.(\d+) (.+)", list_item.text)
          if header:
            section = int(header.group(1))
            subsection = int(header.group(2))

            # Topic
            if section == 0 and subsection == 0:
              text = re.search(r"(.+) \(.+\)", header.group(3))
              results.append(ListItem(3, 'topic', text.group(1)))

            # Find the learning objectives
            elif section == 1 and subsection == 0:

              # Find the next list that matches the learning objectives format
              first_item = item.find('li')
              while item and not re.search(r"[a-z]+\) (.+)", first_item.text):
                item = next(iterator, None)
                first_item = item.find('li')

              # Add learning objectives
              for objective in item.find_all('li'):
                text = re.search(r"[a-z]+\) (.+)", objective.text)
                results.append(ListItem(4, 'learning_objective', text.group(1)))

            # Skip 'CONTENT' item
            elif section == 2 and subsection == 0:
              pass

            # Item is content, next item will be notes for content items
            else:
              results.append(ListItem(4, 'content', header.group(3)))

          # Parse for notes
          else:
            key_headers = ["notes", "suggested resources", "suggested further assessment"]
            last_item = results.get_last_of_kind('content')
            if any(h for h in key_headers if h in list_item.text.lower()):
              last_item = results.get_last_of_kind('topic')

            # Get any notes that don't match the header condition
            while item and item.name == 'ul' and not re.search(r"\d+\.\d+\.\d+ .+", item.find('li').text):
              keep_in_place = True

              # Find indent based on class
              indent = [re.search(r".+-(\d+)", c) for c in item['class'] if re.search(r".+-(\d+)", c)]
              if not indent:
                continue

              for note_item in item.find_all('li'):
                last_item.add_notes(note_item.text, indent = int(indent[0].group(1)))

              item = next(iterator, None)

      if not keep_in_place:
        item = next(iterator, None)

    return results

  def parse_document(self, file_id):
    doc = self.get_doc(file_id)
    structure = self.convert_html_to_structure(doc.read())
    return structure
