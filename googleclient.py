from config import CREDENTIALS_PATH
from google.oauth2 import service_account
from googleapiclient.discovery import build

DRIVE_FOLDER = '1x2EhRa6sQhCDW0EwLcuNcIdT7lqEH0TN'
TEXT_CHUNK_SIZE = 500

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
    data = {
      'name': filename,
      'mimeType':  'application/vnd.google-apps.document',
      'parents': [DRIVE_FOLDER]
    }
    file = self.service.files().create(body=data, fields='id').execute()
    self.set_permission(file['id'])

    service = build('docs', 'v1', credentials=self.credentials)
    requests = [
      {
        'insertText': {
          'location': {
            'index': x + 1
          },
          'text': text[x:x+TEXT_CHUNK_SIZE]
        }
      }
      for x in range(0, len(text), TEXT_CHUNK_SIZE)
    ]

    result = service.documents().batchUpdate(documentId=file['id'], body={'requests': requests}).execute()
