#!/usr/bin/env python

import argparse
import os
import shutil
import subprocess


def rename_and_convert_files_in_dir(dirname):

    filenames = os.listdir(dirname)

    counter = 1
    for filename in sorted(filenames):

        if filename.endswith('.pdf'):
            _, dotext = os.path.splitext(filename)
            relpath = os.path.join(dirname, filename)
            print('Found PDF at', relpath)

            # detemine new basename
            abspath = os.path.abspath(relpath)
            dirs_list = abspath.split(os.path.sep)
            doc_id = dirs_list[-5].split('_')[0]
            chapter_id = dirs_list[-4].split('_')[0]
            section_id = dirs_list[-3].split('_')[0]
            topic_id = dirs_list[-2]
            newfilebasename = '{}_{}_{}_{}_chunk{:03d}'.format(doc_id, chapter_id, section_id, topic_id, counter)

            # Rename pdfs sequentially if not already
            newrelpath = os.path.join(dirname, newfilebasename + dotext)
            if relpath == newrelpath:
                counter += 1
                pass
            else:
                print('Moving', relpath, 'to', newrelpath)
                shutil.move(relpath, newrelpath)
                counter += 1

            # Convert pdf chunk to high-res png (for OCR)
            relpathpng = newrelpath.replace('.pdf', '.png')
            print('Converting', newrelpath, 'to', relpathpng)
            subprocess.run([
                "convert",
                "-density", "600",
                "-trim",
                newrelpath,
                "-quality", "100",
                relpathpng
            ])

            # Convert pdf chunk to low-resolution png (for display)
            relpathpng_lowres = newrelpath.replace('.pdf', '_lowres.png')
            print('Converting', newrelpath, 'to', relpathpng_lowres)
            subprocess.run([
                "convert",
                "-density", "300",
                "-trim",
                newrelpath,
                "-quality", "100",
                relpathpng_lowres
            ])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Renames and converts all document chunks.')
    parser.add_argument('--recursive', type=str, help='Do recusively for all subdirs of dir')
    args = parser.parse_args()
    print(args.__dict__)

    if args.recursive:
        startdir = args.recursive
        for dir, subdirs, filenames in os.walk(startdir):
            dirname = os.path.split(dir)[-1]
            if dirname == "inputs":  # skip dirname with source PDF
                continue
            print('Processing dir', dir)
            rename_and_convert_files_in_dir(dir)
    else:
        rename_and_convert_files_in_dir('.')
