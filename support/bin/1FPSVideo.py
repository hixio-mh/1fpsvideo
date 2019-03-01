#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# I waive copyright and related rights in the this work worldwide
# through the CC0 1.0 Universal public domain dedication.
# https://creativecommons.org/publicdomain/zero/1.0/legalcode
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
import tomputils.util as tutil

from datetime import datetime, timedelta
from pathlib import Path
from requests.auth import HTTPDigestAuth
from requests.exceptions import Timeout, ConnectionError, RequestException
from sys import exit
from twisted.internet import task, reactor

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', type=str, required=True,
                    help='Config File')

starttm = datetime.now()
sdate = starttm.strftime('%Y-%m-%d')
shour = starttm.strftime('%H')
endtm = None
loop = None
archpath = Path(os.getenv('VID_LOC', '/data'))
tmppath = Path('/tmp') / shour
timeout = None
count = 0


def get_image():
    global count
    if datetime.now() < endtm:
        try:
            if 'auth' in config:
                r = requests.get(config['url'],
                                 auth=HTTPDigestAuth(config['auth']['user'],
                                                     config['auth']['passwd']),
                                 timeout=timeout)
            else:
                r = requests.get(config['url'], timeout=timeout)

            with open('image%04d.jpg' % count, 'wb') as f:
                f.write(r.content)
            r.close()
            count += 1
        except ConnectionError as e:
            logger.error('Connection error: {}'.format(e))
        except Timeout as e:
            logger.error('Timeout: {}'.format(e))
        except RequestException as e:
            logger.error('Other requests error: {}'.format(e))
    else:
        loop.stop()
        return


def fix_images():
    logger.debug('Delete any failed images')
    files = tmppath.glob('*.jpg')
    sz = int(config['1fps']['minFileSize'])
    for f in files:
        if f.stat().st_size < sz:
            f.unlink()

    logger.debug('Renumber images')
    c = 0
    files = sorted(tmppath.glob('*.jpg'))
    for f in files:
        f.rename('image%04d.jpg' % c)
        c += 1


def encode_video():
    cmd = ['ffmpeg', '-framerate', '5', '-i', 'image%04d.jpg', '-c:v',
           'libx265', '-crf', '28', '-vf', 'scale=iw*.75:ih*.75', '-threads',
           '1', '1fps_{}00.mp4'.format(shour)]
    logger.debug('Encode video: {}'.format(' '.join(cmd)))
    subprocess.call(cmd)


def copy_to_share():
    logger.info('Copying to share')
    path = archpath / config['cam'] / sdate
    if not path.exists():
        logger.debug('Creating new archive directory: {}'.format(path))
        path.mkdir(parents=True)
    shutil.copy2('{}/1fps_{}00.mp4'.format(tmppath, shour), '{}/'.format(path))


def images_to_video_to_share(result):
    logger.info('Images gathered, creating video')
    fix_images()
    encode_video()
    copy_to_share()
    reactor.stop()


def parse_config(confFile):
    logger.debug('Parse config at {}'.format(confFile))
    with open(confFile, 'r') as f:
        return json.load(f)


def loop_failed(failure):
    logger.error(failure.getBriefTraceback())
    reactor.stop()


def cleanup():
    logger.debug('Deleting stuff')
    ftypes = ('*.jpg', '*.mp4')
    files = []
    for t in ftypes:
        files.extend(tmppath.glob(t))
    for f in files:
        f.unlink()
    tmppath.rmdir()


def main():
    global logger
    logger = tutil.setup_logging("1FPS")
    if 'PYLOGLEVEL' in os.environ:
        level = logging.getLevelName(os.getenv('PYLOGLEVEL', 'DEBUG'))
        logger.setLevel(level)

    args = parser.parse_args()
    logger.info('Starting')

    global config
    config = parse_config(args.config)
    global endtm
    endtm = starttm + timedelta(seconds=config['1fps']['time'])
    global timeout
    timeout = int(config['1fps']['interval']) * 2

    try:
        tmppath.mkdir()
        os.chdir(str(tmppath))
    except FileExistsError as e:
        logger.error('Temp path already exists. Is another process using it?')
        logger.error(e)
        logger.info('Exiting because of error')
        exit(0)

    global loop
    loop = task.LoopingCall(get_image)
    loopDeferred = loop.start(config['1fps']['interval'])
    loopDeferred.addCallback(images_to_video_to_share)
    loopDeferred.addErrback(loop_failed)
    reactor.run()
    cleanup()
    logger.info('Finished')
    logging.shutdown()


if __name__ == '__main__':
    main()
