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
import re
import uuid

from config import CREDENTIALS_PATH
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from bs4 import BeautifulSoup

DOCS_FOLDER = "1_qWammKogC1_s__Dzwmekm6w28ruhppZ"
SPREADSHEET_FOLDER = "1TnEJchizCW71Mrcltmdt1ecgY59J5ihx"


class StandardEntry(object):
    def __init__(self, level, item_type, text, notes="", units="", identifier=""):
        self.type = item_type
        self.level = level
        self.text = text.strip()
        self.identifier = identifier or self.text
        self.notes = notes
        self.units = units

    def add_note_line(self, text, indent=0):
        self.notes = (self.notes + "\n" + ("\t" * indent) + "- " + text).strip()


class StandardEntryList(list):
    def get_last_of_kind(self, kind):
        return [i for i in self if i.type == kind][-1]

    def break_by_subject(self):
        results = []
        for item in self:
            if item.type == "subject":
                results.append([])
            results[-1].append(item)
        return results


class LineItem(object):
    indent = None
    text = None
    bullet = None

    def __init__(self, indent, text, bullet=""):
        self.indent = indent
        self.text = text
        self.bullet = bullet

    def get_bullet_with_space(self):
        return self.bullet + " " if self.bullet else ""

    def __str__(self):
        return "\t" * self.indent + self.get_bullet_with_space() + self.text


class GoogleDriveClient(object):
    def __init__(self):
        self.credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH
        )
        self.service = build("drive", "v3", credentials=self.credentials)

    def set_permission(self, file_id):
        anyone_permission = {"type": "anyone", "role": "writer"}
        self.service.permissions().create(
            fileId=file_id, body=anyone_permission, fields="id"
        ).execute()

    def create_folder(self, folder_name):
        data = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [DRIVE_FOLDER],
        }
        return self.service.files().create(body=data, fields="id").execute()

    def create_google_doc(self, filename, text):

        text = text.encode("utf-8") if isinstance(text, str) else text

        doc_text = BytesIO()
        doc_text.write(text)

        data = {
            "name": filename,
            "mimeType": "application/vnd.google-apps.document",
            "parents": [DOCS_FOLDER],
        }
        media = MediaIoBaseUpload(doc_text, mimetype="text/html", resumable=True)

        file = (
            self.service.files()
            .create(body=data, media_body=media, fields="id")
            .execute()
        )
        self.set_permission(file["id"])

    def get_doc(self, file_id):
        download = BytesIO()
        request = self.service.files().export_media(
            fileId=file_id, mimeType="text/html"
        )
        downloader = MediaIoBaseDownload(download, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        download.seek(0)
        return download

    def extract_line_items_from_html(self, html):

        page = BeautifulSoup(html, "html.parser")
        elements = page.find_all(["p", "li"])
        results = []

        for el in elements:
            if el.name == "p":
                results.append(LineItem(indent=0, text=el.text))
            else:
                indent = int(el.parent["class"][0].split("-")[-1]) + 1
                results.append(LineItem(indent=indent, text=el.text))

        return results

    # def convert_html_to_structure(self, contents):
    #     page = BeautifulSoup(contents, "html.parser")

    #     results = StandardEntryList([])
    #     iterator = iter(
    #         [c for c in page.find("body").children if c.name == "p" or c.name == "ul"]
    #     )

    #     item = next(iterator, None)
    #     while item:
    #         keep_in_place = False
    #         # Get subjects and levels
    #         if item.name == "p":
    #             if "form" in item.text.lower():
    #                 results.append(StandardEntry(2, "level", item.text))
    #             else:
    #                 results.append(StandardEntry(1, "subject", item.text))

    #         # Get topics, content, and learning objectives
    #         elif item.name == "ul":
    #             for list_item in item.find_all("li"):
    #                 # Determine how to categorize based on indent and bullet
    #                 header = re.search(r"^(\d+)\.(\d+)\.(\d+)\s*(.+)", list_item.text)
    #                 if header:
    #                     unit = int(header.group(1))
    #                     section = int(header.group(2))
    #                     subsection = int(header.group(3))

    #                     # Topic
    #                     if section == 0 and subsection == 0:
    #                         text = re.sub(r"\s*\(\d+ Lessons\)", "", header.group(4))
    #                         identifier = "{}.{}".format(unit, section)
    #                         results.append(
    #                             StandardEntry(3, "topic", text, identifier=identifier)
    #                         )

    #                     # Find the learning objectives
    #                     elif section == 1 and subsection == 0:
    #                         # Find the next list that matches the learning objectives format
    #                         first_item = item.find("li")
    #                         while item and not re.search(
    #                             r"[a-z0-9]+\)\s*(.+)", first_item.text
    #                         ):
    #                             item = next(iterator, None)
    #                             first_item = item.find("li")

    #                         # Add learning objectives
    #                         for index, objective in enumerate(item.find_all("li")):
    #                             text = re.search(
    #                                 r"([a-z0-9A-Z]+)\)\s*(.+)", objective.text
    #                             )
    #                             if not text:
    #                                 continue
    #                             identifier = "{}.{}.{}".format(
    #                                 unit, section, text.group(1)
    #                             )
    #                             results.append(
    #                                 StandardEntry(
    #                                     4,
    #                                     "learning_objective",
    #                                     text.group(2),
    #                                     identifier=identifier,
    #                                 )
    #                             )

    #                     # Skip 'CONTENT' item
    #                     elif section == 2 and subsection == 0:
    #                         pass

    #                     # Item is content, next item will be notes for content items
    #                     else:
    #                         identifier = "{}.{}.{}".format(unit, section, subsection)
    #                         results.append(
    #                             StandardEntry(
    #                                 4, "content", header.group(4), identifier=identifier
    #                             )
    #                         )

    #                 # Parse for notes
    #                 else:
    #                     key_headers = [
    #                         "notes",
    #                         "suggested resources",
    #                         "suggested further assessment",
    #                     ]
    #                     last_item = results.get_last_of_kind("content")
    #                     if any(h for h in key_headers if h in list_item.text.lower()):
    #                         last_item = results.get_last_of_kind("topic")

    #                     # Get any notes that don't match the header condition
    #                     while (
    #                         item
    #                         and item.name == "ul"
    #                         and not re.search(
    #                             r"\d+\.\d+\.\d+\s*.+", item.find("li").text
    #                         )
    #                     ):
    #                         keep_in_place = True

    #                         # Find indent based on class
    #                         indent = [
    #                             re.search(r".+-(\d+)", c)
    #                             for c in item["class"]
    #                             if re.search(r".+-(\d+)", c)
    #                         ]
    #                         if not indent:
    #                             continue

    #                         for note_item in item.find_all("li"):
    #                             last_item.add_notes(
    #                                 note_item.text, indent=int(indent[0].group(1))
    #                             )

    #                         item = next(iterator, None)

    #         if not keep_in_place:
    #             item = next(iterator, None)

    #     return results

    def write_csv_from_structure(self, structure, title, metadata=None, sheet=None):
        spreadsheet_service = build("sheets", "v4", credentials=self.credentials)
        metadata = metadata or {}

        if not sheet:
            data = {
                "name": title,
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "parents": [SPREADSHEET_FOLDER],
            }
            spreadsheet = self.service.files().create(body=data, fields="id").execute()
            self.set_permission(spreadsheet["id"])
        else:
            spreadsheet = {"id": sheet}
        sheets = (
            spreadsheet_service.spreadsheets()
            .get(spreadsheetId=spreadsheet["id"])
            .execute()["sheets"]
        )
        existing_sheets = [sheet["properties"]["sheetId"] for sheet in sheets]

        # rename old sheets to avoid conflicts
        rename_requests = [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet["properties"]["sheetId"],
                        "title": sheet["properties"]["title"]
                        + "-"
                        + uuid.uuid4().hex[:5],
                    },
                    "fields": "title",
                }
            }
            for sheet in sheets
        ]
        response = (
            spreadsheet_service.spreadsheets()
            .batchUpdate(
                spreadsheetId=spreadsheet["id"], body={"requests": rename_requests}
            )
            .execute()
        )

        headers = ["Depth", "Identifier", "Kind", "Title", "Units of time", "Notes"]

        requests = []
        for index, subject_structure in enumerate(structure.break_by_subject()):
            sheet_name = subject_structure[0].text
            add_sheet_request = {
                "addSheet": {
                    "properties": {
                        "title": sheet_name,
                        "gridProperties": {
                            "rowCount": len(subject_structure) + len(metadata) + 10,
                            "columnCount": 26,
                        },
                    }
                }
            }
            response = (
                spreadsheet_service.spreadsheets()
                .batchUpdate(
                    spreadsheetId=spreadsheet["id"],
                    body={"requests": [add_sheet_request]},
                )
                .execute()
            )
            sheet_id = response["replies"][0]["addSheet"]["properties"]["sheetId"]

            values = [create_row(["Title", "{} {}".format(title, sheet_name)])]
            values.extend([create_row([k, v]) for k, v in metadata.items()])
            values.append(create_row([]))
            values.append([create_row(headers)])

            for item in subject_structure:
                values.append(
                    create_row(
                        [
                            "#" * item.level,
                            item.identifier,
                            item.type,
                            item.text,
                            item.units,
                            item.notes,
                        ]
                    )
                )

            append_cells_request = {
                "appendCells": {"sheetId": sheet_id, "rows": [values], "fields": "*"}
            }
            spreadsheet_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet["id"],
                body={"requests": [append_cells_request]},
            ).execute()

        delete_requests = [
            {"deleteSheet": {"sheetId": sheetId}} for sheetId in existing_sheets
        ]
        response = (
            spreadsheet_service.spreadsheets()
            .batchUpdate(
                spreadsheetId=spreadsheet["id"], body={"requests": delete_requests}
            )
            .execute()
        )

        return spreadsheet

    def parse_document(self, file_id, title, metadata=None, sheet=None):
        doc = self.get_doc(file_id)
        structure = self.convert_html_to_structure(doc.read())
        self.write_csv_from_structure(structure, title, metadata=metadata, sheet=sheet)
        return structure


def create_row(values):
    return [
        {"values": [{"userEnteredValue": {"stringValue": value}} for value in values]}
    ]
