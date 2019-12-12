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
