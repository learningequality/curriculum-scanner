import csv
import os
import sys

filename = sys.argv[1]
fieldnames = ['depth', 'identifier', 'kind', 'title', 'time', 'notes']

rows = []


class CurriculumSpreadsheet:
    def __init__(self, filename):
        self.filename = filename

    def add_depth(self):
        rows = []
        with open(self.filename) as f:
            reader = csv.DictReader(f, fieldnames=fieldnames)
            add_depth = False
            for row in reader:
                depth = row['depth']
                identifier = row['identifier']

                if add_depth:
                    if len(depth.split()) == 0 and len(identifier) > 0:
                        depth = '#' * (1 + identifier.count('.'))

                if depth.lower().strip() == 'depth':
                    add_depth = True

                row['depth'] = depth
                rows.append(row)

        return rows

    def write_csv(self, filename, rows):
        with open(filename, 'w') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            for row in rows:
                writer.writerow(row)

    # print("rows = {}".format(rows))

if __name__ == '__main__':
    filename = sys.argv[1]
    base, ext = os.path.splitext(filename)
    doc = CurriculumSpreadsheet(filename)
    rows = doc.add_depth()
    doc.write_csv(base + '-depth' + ext, rows)
