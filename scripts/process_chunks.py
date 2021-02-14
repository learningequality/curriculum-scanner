#!/usr/bin/env python

import argparse
import json
import os

import sys
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(SCRIPTS_DIR, '..')
sys.path.append(BASE_DIR)

from process_scans import get_text_detection, STRUCTURE, convert_image_data_to_dict, write_text_fields


def run_ocr_on_chunks_in_dir(dirname):

    # 1. OCR ALL PNGS
    pngfilenames = [fn for fn in os.listdir(dirname) if fn.endswith('.png') and not fn.endswith('_lowres.png')]
    text_file_paths = []
    for filename in sorted(pngfilenames):
        image_path = os.path.join(dirname, filename)
        # print('Found high-res PNG at', image_path)

        basename, _ = os.path.splitext(filename)
        
        print('Calling Cloud vision API for image', image_path)
        response = get_text_detection(image_path, basename)
        image_data = response.full_text_annotation

        # Convert the objects to a serializable dict
        data = convert_image_data_to_dict(image_data, STRUCTURE)
        write_text_fields(data)

        # Write the comlete OCR data to the file
        block_file_path = os.path.join(dirname, '{}_ocr.json'.format(basename))
        with open(block_file_path, 'wb') as jsonfobj:
            jsonfobj.write(json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8'))

        # Extract the plaintext from the OCR data
        text_file_path = os.path.join(dirname, '{}_ocr.txt'.format(basename))
        chunk_text = data['text']

        with open(text_file_path, 'w', encoding="utf-8") as txtfobj:
            txtfobj.write(chunk_text)
            text_file_paths.append(text_file_path)

    # 2. COMBINE all OCR text into a single .txt file
    if text_file_paths:
        combined_text = ''
        combined_text_filepath = None
        for text_file_path in sorted(text_file_paths):
            # print('found txt file', text_file_path)
            if combined_text_filepath is None:
                combined_text_filepath = text_file_path.split('_chunk')[0] + '_combined.txt'
            with open(text_file_path, 'r', encoding="utf-8") as txtfobj:
                combined_text += txtfobj.read()
        with open(combined_text_filepath, 'w', encoding="utf-8") as combinedtxtfobj:
            combinedtxtfobj.write(combined_text)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Converts and renames files sequentially 001.png 002.png etc')
    parser.add_argument('--recursive', type=str, help='Do recusively for all subdirs of dir')
    args = parser.parse_args()
    print(args.__dict__)

    if args.recursive:
        startdir = args.recursive
        for dir, subdirs, filenames in os.walk(startdir):
            print('OCRing all files in dir', dir)
            run_ocr_on_chunks_in_dir(dir)
    else:
        run_ocr_on_chunks_in_dir('.')
