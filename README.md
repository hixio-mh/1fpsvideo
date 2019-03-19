# 1fpsvideo

[![Build Status](https://travis-ci.org/wtollett-usgs/1fpsvideo.svg?branch=master)](https://travis-ci.org/wtollett-usgs/1fpsvideo)

## Usage
---
Expected volume mounts:
1. Camera (json) config files and 1fps.cron to /app/1fps/etc. 
2. Location into which to save videos.
3. If you want to view the logs outside of the container, mount another volume and pipe the output.

Cron info:
* The cron entry should look something like the following:
```
00 */2 * * * /app/1fps/bin/1FPSVideo.py -c /app/1fps/etc/camconfig.json
```
* Additionally, a few variables can be set in this file:
  * PYLOGLEVEL -- the level of logging to use. Default: DEBUG
  * VID_LOC -- the location (inside the container) into which to save the videos. Default: /data
