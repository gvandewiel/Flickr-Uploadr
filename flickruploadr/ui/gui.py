from __future__ import print_function
import logging
import os
import configparser
import eel
from flickruploadr.core import FlickrCore
import flickruploadr.common as common

class GuiLogHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
    def emit(self, record):
        record = self.format(record)
        try:
            eel.js_pre(record)
        except AttributeError:
            pass


@eel.expose
def proc_iput(post_data):
    threads = dict()
    nargs = {}
    logger.debug(post_data)

    nargs['main_dir'] = post_data['main_dir']
    nargs['subdir'] = post_data['subdir']
    nargs['public'] = post_data['public']
    nargs['family'] = post_data['family']
    nargs['friends'] = post_data['friends']
    nargs['update'] = post_data['update']

    username = post_data['username']
    method = post_data['action']

    logger.debug(username)
    logger.debug(method)
    logger.debug(nargs)

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
        exporting_threads[thread_id] = FlickrCore(user=username,
                                                  method=method,
                                                  dry_run=False,
                                                  mkwargs=nargs)

        # Set thread as non-deamon to prevent the usage of join
        # Furhtermore it allows to see the progress while stopping a thread
        exporting_threads[thread_id].setDaemon(False)
        exporting_threads[thread_id].start()

        for key in logging.Logger.manager.loggerDict.keys():
            if 'Flickr' in key:
                logging.getLogger(key).addHandler(handler)

        eel.poll(thread_id)
        return thread_id
    else:
        return False


@eel.expose
def stop_thread(thread_id):
    global exporting_threads
    logger.info('Stopping thread_id {}'.format(thread_id))
    exporting_threads[thread_id].progress.dict['stop'] = True


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
    logger.debug(configuration)
    return configuration


@eel.expose
def dirlist(main_dir):
    dirs = sorted([f for f in os.listdir(main_dir) if not f.startswith('.')], key=lambda f: f.lower())
    logger.debug(dirs)
    return dirs


@eel.expose
def update_monitor(thread_id):
    global exporting_threads
    progress = exporting_threads[thread_id].progress.dict
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
    """Main console function."""

    global logger
    global handler
    formatter = logging.Formatter('%(name)-15s %(levelname)-8s %(message)s')
    handler = GuiLogHandler()
    handler.setFormatter(formatter)

    logger = common.create_logger('FlickrGUI', handler=handler)

    logger.info('Running Flickr Uploader from {}'.format(os.getcwd()))

    global exporting_threads
    global thread_id
    exporting_threads = {}
    thread_id = 0

    import pkg_resources

    web_path = os.path.join(pkg_resources.resource_filename('flickruploadr', 'ui'), 'web')
    logger.debug(web_path)
    eel.init(web_path)
    eel.start('index.html', size=(600, 650), options={'chromeFlags': ["-incognito"]})


if __name__ == "__main__":
    main()
