#!/usr/bin/env python

import argparse
import os

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create empty dirs of the form n.0.0')
    parser.add_argument('--first', required=True, type=int, help='Start at number')
    parser.add_argument('--last', required=True, type=int, help='Finish with this number')
    args = parser.parse_args()
    # print(args.__dict__)

    for i in range(args.first, args.last+1):
        name = '{:d}.0.0'.format(i)
        if os.path.exists(name):
            print('Directory', name, 'already exists...')
        else:
            print('Creating directory', name)
            os.makedirs(name)

