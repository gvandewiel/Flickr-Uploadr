# Flickr Uploadr
Flickr upload tool with GUI using the MD5 and SHA1 checksum as propose by Mark Longair in the following article:
* [HASHING FLICKR PHOTOS](https://longair.net/blog/2009/12/19/hashing-flickr-photos/) - The article by Mark Longair

Only tested on Mac systems.

The uploader requires a config.ini file placed in a "flickr" folder inside the users home directory ("/Users/<USER>/flickr").
The file contains settings for one (or more) Flickr users in the following format:
```
[username_1]
api_key: <API_KEY>
api_secret: <API_SECRET>
root_dir: <ROOT DIR without trailing slash>

[username_2]
api_key: <API_KEY>
api_secret: <API_SECRET>
root_dir: <ROOT DIR without trailing slash>
```
The program makes use of the eel module to make use of Google Chrome for the user interface. The userface is used to start/stop the Uploadr and monitor the progress of the processed photos, ablums and the upload of new photos.
