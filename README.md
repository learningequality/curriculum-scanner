
# Curriculum Scanner
Uses a scan of a curriculum book or pdf to generate a csv structure

## Getting Started

You'll need to install the following libraries first:
* [poppler](https://poppler.freedesktop.org/)
* [Python](https://www.python.org/downloads/)
* [pip](https://pip.pypa.io/en/stable/installing/)

Next, install the requirements
 `pip install -r requirements.txt`

You are now ready to start using the CurriculumScanner class!


## The CurriculumScanner Class

The CurriculumScanner class reads the data from running `process_scans.py`. To use this class, you will need to instantiate an object first:

```
from scanner import CurriculumScanner

scanner = CurriculumScanner("<path-to-file>")
```
Note: you may get an error if the Google Vision API hasn't been run on the specified file. To resolve this, you will need to run `CurriculumScanner.process("path-to-file")`. This accepts png, jpg, and pdf files. If you would like to change the detection settings, you'll need to update `config.py`



#### CurriculumScanner.pages
If you would like to access the data directly, you can use the `scanner.pages` attribute. The data will be formatted as the following:

```
[
	{
	    "columns": [
	      [starting point, ending point],
	      ...
	    ],
	    "file": "path/to/page/data.json",
	    "image": "path/to/image.png,
	    "boxes": "path/to/image/with/boxes.png"
	}
]
```


#### Individual page data
Each item in this list will have a path to the corresponding page data, which is the serialized version of the data returned from the [Google Vision API](https://cloud.google.com/vision/docs/). The basic hierarchy is as follows:

```
{
	"pages": [{
		"blocks": [{
			"paragraphs": [{
				"words": [{
					"symbols": {...}
				}]
			}]
		}]
	}]
}
```

If you would like to see each structure's bounds, a visual guide has been generated for you under the `boxes` field under the `scanner.pages` data.
* Blocks = red
* Paragraphs = blue
* Words = yellow

##### Accessing the data
To access this data, you can use the `scanner.get_page_data(page number)` method. Alternatively, if you are iterating through the pages, you can use the `scanner.get_page_data()` function.

```
for page in scanner.get_next_page():
    # Do something with page data
```

In some cases, you may want to access the page blocks in a certain order as they appear on the page. To do this, you can use the `scanner.get_blocks_by_order(page_number, order=BlockOrder)` function.

```
from scanner import BlockOrder

for page_number, page in enumerate(scanner.get_next_page()):
  blocks = scanner.get_blocks_by_order(page_number, order=BlockOrder.LEFTRIGHT)
```

The BlockOrder enum has the following options:
* TOPBOTTOM to read from top to bottom
* BOTTOMTOP to read from the bottom to the top
* LEFTRIGHT to read from left to right
* RIGHTLEFT to read from right to left

---
### Additional Methods

#### text_within
If you would like to get the text that is within a certain boundary, use `scanner.text_within`
```
	# To get text within the box (1, 2) (1, 3) (5, 2) (5, 3) on the first page
	text = scanner.text_within(0, x0=1, y0=2, x1=5, y1=3)
```

#### find_text_matches
If you would like to find where a text appears across the pages, you can use the `scanner.find_text_matches(text)` method.

```
	matches = scanner.find_text_matches('text to find')
```

This will return a list of where each match is found
```
[
  {
    "page": int,
    "block": int,
    "paragraph": int,
    "word": int,
    "bounds": [
      {"x": int, "y": int},
      {"x": int, "y": int},
      {"x": int, "y": int},
      {"x": int, "y": int}
    ]
  }
]
```
