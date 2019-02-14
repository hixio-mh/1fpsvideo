#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# I waive copyright and related rights in the this work worldwide
# through the CC0 1.0 Universal public domain dedication.
# https://creativecommons.org/publicdomain/zero/1.0/legalcode
#
# RepeatedTimer code taken mostly from
# http://stackoverflow.com/questions/3393612/run-certain-code-every-n-seconds
#
# Author(s):
#   Bill Tollett <wtollett@usgs.gov>

import argparse
import json
import logging
import os
import requests
import shutil
import subprocess
import sys
import tomputils.util as tutil

from pathlib import Path
from threading import Timer
from time import sleep, strftime

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', type=str, required=True,
                    help='Config File')

DATE = strftime('%Y-%m-%d')
HOUR = strftime('%H')
TFMT = '%Y-%m-%d %H:%M:%S'
APATH = Path(os.getenv('VID_LOC', '/data'))
FPATH = Path('/tmp') / HOUR
count = 0


class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False


def get_image(url):
    global count
    r = requests.get(url)
    with open('image%04d.jpg' % count, 'wb') as f:
        f.write(r.content)
    r.close()
    count += 1


def get_protected_image(url, user, passwd):
    global count
    r = requests.get(url, auth=requests.auth.HTTPDigestAuth(user, passwd))
    with open('image%04d.jpg' % count, 'wb') as f:
        f.write(r.content)
    r.close()
    count += 1


def collect_images(interval, slp, url, user=None, passwd=None):
    logger.debug('Starting image acquisition')
    if user:
        rt = RepeatedTimer(int(interval), get_protected_image,
                           *[url, user, passwd])
    else:
        rt = RepeatedTimer(int(interval), get_image, url)
    try:
        sleep(float(slp))
    finally:
        rt.stop()


def delete_failed_images(minfilesize):
    logger.debug('Delete failed images')
    files = FPATH.glob('*.jpg')
    for f in files:
        if f.stat().st_size < int(minfilesize):
            f.unlink()


def renumber_images():
    logger.debug('Renumber images')
    c = 0
    files = sorted(FPATH.glob('*.jpg'))
    for f in files:
        f.rename('image%04d.jpg' % c)
        c += 1


def encode_video():
    logger.debug('Encode video')
    cmd = ['ffmpeg', '-framerate', '5', '-i', 'image%04d.jpg', '-c:v',
           'libx265', '-crf', '28', '-vf', 'scale=iw*.75:ih*.75', '-threads',
           '1', '1fps_{}00.mp4'.format(HOUR)]
    subprocess.call(cmd)


def copy_to_share(camname):
    logger.info('Copying to share')
    path = APATH / camname / DATE
    if not path.exists():
        logger.debug('Creating new archive directory: {}'.format(path))
        path.mkdir(parents=True)
    shutil.copy2('{}/1fps_{}00.mp4'.format(FPATH, HOUR), '{}/'.format(path))


def cleanup():
    logger.debug('Deleting stuff')
    ftypes = ('*.jpg', '*.mp4')
    files = []
    for t in ftypes:
        files.extend(FPATH.glob(t))
    for f in files:
        f.unlink()
    FPATH.rmdir()


def parse_config(confFile):
    logger.debug('Parse config at {}'.format(confFile))
    with open(confFile, 'r') as f:
        return json.load(f)


if __name__ == '__main__':
    global logger
    logger = tutil.setup_logging("1FPS")
    if 'PYLOGLEVEL' in os.environ:
        level = logging.getLevelName(os.getenv('PYLOGLEVEL', 'DEBUG'))
        logger.setLevel(level)

    args = parser.parse_args()
    logger.info('Starting')
    conf = parse_config(args.config)

    try:
        FPATH.mkdir()
        os.chdir(str(FPATH))
    except FileExistsError as e:
        logger.error('Temp path already exists. Is another process using it?')
        logger.error(e)
        logger.info('Exiting because of error')
        sys.exit(0)

    if 'auth' in conf:
        collect_images(conf['1fps']['interval'], conf['1fps']['time'],
                       conf['url'], conf['auth']['user'],
                       conf['auth']['passwd'])
    else:
        collect_images(conf['1fps']['interval'], conf['1fps']['time'],
                       conf['url'])

    logger.info('Images gathered, create video')
    delete_failed_images(conf['1fps']['minFileSize'])
    renumber_images()
    encode_video()
    copy_to_share(conf['cam'])
    cleanup()
    logger.info('Finished')
    logging.shutdown()
