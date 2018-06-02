import eel
import logging
import os
from flickr_uploadr.threaded_uploadr import Uploadr
# from flickr_uploadr.common import *
import configparser

print('Running Flickr Uploader from {}'.format(os.getcwd()))

exporting_threads = {}
thread_id = 0

# Reduce amount of output
# logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.basicConfig(level=logging.ERROR)

for key in logging.Logger.manager.loggerDict.keys():
    logging.getLogger(key).setLevel(logging.ERROR)

logging.getLogger('FlickrUploader').setLevel(logging.INFO)

# Custom handler


class LogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        eel.js_pre(log_entry)


FlickrLogger = logging.getLogger('FlickrUploader')
FlickrLogger.setLevel(logging.DEBUG)
handler = LogHandler()
FlickrLogger.addHandler(handler)

Flickr2SQLiteLogger = logging.getLogger('Flickr2SQLite')
Flickr2SQLiteLogger.setLevel(logging.DEBUG)
handler = LogHandler()
Flickr2SQLiteLogger.addHandler(handler)


eel.init('web')


@eel.expose
def proc_iput(post_data):
    threads = dict()
    nargs = {}
    print(post_data)
    nargs['main_dir'] = post_data['main_dir']
    nargs['subdir'] = post_data['subdir']
    nargs['public'] = post_data['public']
    nargs['family'] = post_data['family']
    nargs['friends'] = post_data['friends']
    nargs['update'] = post_data['update']

    username = post_data['username']
    method = post_data['action']

    print(username)
    print(method)
    print(nargs)

    thread_id = startThread(username=username, method=method, nargs=nargs)
    eel.set_thread(thread_id)
    if len(exporting_threads) != 0:
        for thread_id in exporting_threads:
            threads[thread_id] = {'id': thread_id,
                                  'user': exporting_threads[thread_id].user,
                                  'method': exporting_threads[thread_id].method}


def startThread(username='', method='', nargs=None):
    global exporting_threads
    global thread_id

    # Set arguments for target function as keyword paramters
    if username != '' and method != '' and nargs is not None:
        thread_id += 1
        exporting_threads[thread_id] = Uploadr(user=username,
                                               method=method,
                                               mkwargs=nargs)
        # Set thread as non-deamon to prevent the usage of join
        # Furhtermore it allows to see the progress while stopping a thread
        exporting_threads[thread_id].setDaemon(False)
        exporting_threads[thread_id].start()
        eel.poll(thread_id)
        return thread_id
    else:
        return False


@eel.expose
def stop_thread(thread_id):
    global exporting_threads
    print('Stopping thread_id {}'.format(thread_id))
    exporting_threads[thread_id].progress['stop'] = True


@eel.expose
def get_user(username):
    config = configparser.ConfigParser()
    try:
        config.read(os.path.join(os.path.expanduser("~"), 'flickr', 'config.ini'))
    except:
        raise IOError('"~/flickr/config.ini" file not found.')

    if len(config.sections()) is 0:
        raise ValueError('No configuration provided in file')
    configuration = {}
    if username == "":
        configuration = list(config.sections())
    elif username in config.sections():
        configuration['api_key'] = config.get(username, 'api_key')
        configuration['api_secret'] = config.get(username, 'api_secret')
        configuration['main_dir'] = config.get(username, 'root_dir')
        configuration['dirs'] = sorted([f for f in os.listdir(config.get(username, 'root_dir')) if not f.startswith('.')], key=lambda f: f.lower())
    else:
        configuration = False
    print(configuration)
    return configuration


@eel.expose
def dirlist(main_dir):
    dirs = sorted([f for f in os.listdir(main_dir) if not f.startswith('.')], key=lambda f: f.lower())
    print(dirs)
    return dirs


@eel.expose
def update_monitor(thread_id):
    global exporting_threads
    progress = exporting_threads[thread_id].progress
    try:
        progress['pb_albums'] = int((progress['actual_album'] / progress['total_albums']) * 100)
    except:
        progress['pb_albums'] = 0
    try:
        progress['pb_photos'] = int((progress['actual_image'] / progress['total_images']) * 100)
    except:
        progress['pb_upload'] = 0
    return progress


def main():
    eel.start('index.html', size=(600, 650), options={'chromeFlags': ["-incognito"]})


if __name__ == "__main__":
    main()
