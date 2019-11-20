from io import BytesIO
import re

from config import CREDENTIALS_PATH
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from bs4 import BeautifulSoup

DOCS_FOLDER = '1_qWammKogC1_s__Dzwmekm6w28ruhppZ'
SPREADSHEET_FOLDER = '1TnEJchizCW71Mrcltmdt1ecgY59J5ihx'

class ListItem(object):
  def __init__(self, indent, item_type, text, identifier=''):
    self.type = item_type
    self.indent = indent
    self.text = text.strip().capitalize()
    self.identifier = identifier or self.text
    self.notes = ""

  def add_notes(self, text, indent=0):
    self.notes += '\n{}- {}'.format('\t' * indent, text.strip())

class List(list):
  def get_last_of_kind(self, kind):
    return [i for i in self if i.type == kind][-1]

  def break_by_subject(self):
    results = []
    tmplist = []
    for item in self:
      if item.type == 'subject':
        if tmplist:
          results.append(tmplist)
        tmplist = []
      tmplist.append(item)
    results.append(tmplist)
    return results



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
      'parents': [DOCS_FOLDER]
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
          header = re.search(r"(\d+)\.(\d+)\.(\d+)\s*(.+)", list_item.text)
          if header:
            unit = int(header.group(1))
            section = int(header.group(2))
            subsection = int(header.group(3))

            # Topic
            if section == 0 and subsection == 0:
              text = re.sub(r"\s*\(\d+ Lessons\)", '', header.group(4))
              identifier = "{}.{}".format(unit, section)
              results.append(ListItem(3, 'topic', text, identifier=identifier))

            # Find the learning objectives
            elif section == 1 and subsection == 0:
              # Find the next list that matches the learning objectives format
              first_item = item.find('li')
              while item and not re.search(r"[a-z0-9]+\)\s*(.+)", first_item.text):
                item = next(iterator, None)
                first_item = item.find('li')

              # Add learning objectives
              for index, objective in enumerate(item.find_all('li')):
                text = re.search(r"([a-z0-9A-Z]+)\)\s*(.+)", objective.text)
                if not text:
                  continue
                identifier = '{}.{}.{}'.format(unit, section, text.group(1))
                results.append(ListItem(4, 'learning_objective', text.group(2), identifier=identifier))

            # Skip 'CONTENT' item
            elif section == 2 and subsection == 0:
              pass

            # Item is content, next item will be notes for content items
            else:
              identifier = '{}.{}.{}'.format(unit, section, subsection)
              results.append(ListItem(4, 'content', header.group(4), identifier=identifier))

          # Parse for notes
          else:
            key_headers = ["notes", "suggested resources", "suggested further assessment"]
            last_item = results.get_last_of_kind('content')
            if any(h for h in key_headers if h in list_item.text.lower()):
              last_item = results.get_last_of_kind('topic')

            # Get any notes that don't match the header condition
            while item and item.name == 'ul' and not re.search(r"\d+\.\d+\.\d+\s*.+", item.find('li').text):
              keep_in_place = True

              # Find indent based on class
              indent = [re.search(r".+-(\d+)", c) for c in item['class'] if re.search(r".+-(\d+)", c)]
              if not indent:
                continue

              for note_item in item.find_all('li'):
                last_item.add_notes(note_item.text, indent=int(indent[0].group(1)))

              item = next(iterator, None)

      if not keep_in_place:
        item = next(iterator, None)

    return results

  def write_csv_from_structure(self, structure, title, metadata=None):
    spreadsheet_service = build('sheets', 'v4', credentials=self.credentials)
    metadata = metadata or {}
    data = {
      'name': title,
      'mimeType': 'application/vnd.google-apps.spreadsheet',
      'parents': [SPREADSHEET_FOLDER]
    }
    spreadsheet = self.service.files().create(body=data, fields='id').execute()
    self.set_permission(spreadsheet['id'])
    sheets = spreadsheet_service.spreadsheets().get(spreadsheetId=spreadsheet['id']).execute()['sheets']
    existing_sheets = [sheet['properties']['sheetId'] for sheet in sheets]

    headers = ['Depth', 'Identifier', 'Kind', 'Title', 'Units of time', 'Notes and modification attributes']

    requests = []
    for index, subject_structure in enumerate(structure.break_by_subject()):
      sheet_name = subject_structure[0].text
      add_sheet_request = {
        'addSheet': {
          "properties": {
            "title": sheet_name,
            "gridProperties": {
              "rowCount": len(subject_structure) + len(metadata) + 10,
              "columnCount": 26
            }
          }
        }
      }
      response = spreadsheet_service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet['id'], body={'requests': [add_sheet_request]}).execute()
      sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']

      values = [create_row(['Title', '{} {}'.format(title, sheet_name)])]
      values.extend([create_row([k, v]) for k, v in metadata.items()])
      values.append(create_row([]))
      values.append([create_row(headers)])

      chunks = [structure[x:x+500] for x in range(0, len(structure), 500)]
      for sheetId, chunk in enumerate(chunks):
        values.extend([create_row(['#' * item.indent, item.identifier, item.type, item.text, '', item.notes]) for item in chunk])

      append_cells_request = {
        'appendCells': {
          "sheetId": sheet_id,
          "rows": [values],
          "fields": "*"
        }
      }
      spreadsheet_service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet['id'], body={'requests': [append_cells_request]}).execute()

    delete_requests = [{
      'deleteSheet': {
        'sheetId': sheetId
      }
    } for sheetId in existing_sheets]
    response = spreadsheet_service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet['id'], body={'requests': delete_requests}).execute()

  def parse_document(self, file_id, title, metadata=None):
    doc = self.get_doc(file_id)
    structure = self.convert_html_to_structure(doc.read())
    self.write_csv_from_structure(structure, title, metadata=metadata)
    return structure

def create_row(values):
  return [
    {
      "values": [
        {
          "userEnteredValue": {
            "stringValue": value
          }
        }
        for value in values
      ]
    }
  ]
