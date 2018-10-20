from __future__ import print_function
import logging
import os
import configparser
import signal
from flickruploadr.core import FlickrCore

class c:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM = '\033[2m'


def handler(signum, frame):
    stop_thread(thread_id)


def proc_iput(post_data):
    global thread_id
    threads = dict()
    nargs = {}
    # print(post_data)
    nargs['main_dir'] = post_data['main_dir']
    nargs['subdir'] = post_data['subdir']
    nargs['public'] = post_data['public']
    nargs['family'] = post_data['family']
    nargs['friends'] = post_data['friends']
    nargs['update'] = post_data['update']

    username = post_data['username']
    method = post_data['action']

    thread_id = startThread(username=username, method=method, nargs=nargs)

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
                                                  dry_run=True,
                                                  mkwargs=nargs)
        # Set thread as non-deamon to prevent the usage of join
        # Furhtermore it allows to see the progress while stopping a thread
        exporting_threads[thread_id].setDaemon(False)
        exporting_threads[thread_id].start()
        return thread_id
    else:
        return False


def stop_thread(thread_id):
    global exporting_threads
    if thread_id in exporting_threads:
        print('\n\n' + c.FAIL + c.BOLD + '===== STOPPING THREAD WITH ID = {} ====='.format(thread_id) + c.ENDC)
        exporting_threads[thread_id].progress['stop'] = True
    else:
        exit(0)


def get_user(username):
    '''Retrieve list of configured users.
    If username (string) is empty a list of users is returned from the config.ini file
    if username (string( is provided the settings for that user are returned as a dict.
    '''
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

    return configuration


def dirlist(main_dir):
    dirs = sorted([f for f in os.listdir(main_dir) if not f.startswith('.')], key=lambda f: f.lower())
    return dirs


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


def get_bool(prompt, default=True):
    while True:
        try:
            return {"y": True, "n": False, "": default}[input(prompt).lower()]
        except KeyError:
            print('Invalid input please enter "y" or "n"!')
        except KeyboardInterrupt:
            exit(0)


def main():
    """Main console function."""

    signal.signal(signal.SIGINT, handler)

    print('Running Flickr Uploader from {}'.format(os.getcwd()))

    global exporting_threads
    global thread_id
    exporting_threads = {}
    thread_id = 0

    # Reduce amount of output
    '''
    logging.basicConfig()
    logging.getLogger().setLevel(logging.ERROR)

    for key in logging.Logger.manager.loggerDict.keys():
        logging.getLogger(key).setLevel(logging.ERROR)

    FlickrLogger = logging.getLogger('FlickrUploader')
    FlickrLogger.setLevel(logging.DEBUG)

    Flickr2SQLiteLogger = logging.getLogger('Flickr2SQLite')
    Flickr2SQLiteLogger.setLevel(logging.DEBUG)
    '''
    data = dict()

    users = get_user(username='')
    print(c.HEADER + c.BOLD + '==== CONFIGURED USERS ====' + c.ENDC)
    for cnt, user in enumerate(users, 0):
        print(c.GREEN + c.BOLD + '{:2}'.format(cnt) + c.ENDC + ' {}'.format(user))

    while True:
        try:
            data['username'] = users[int(input('\nSelect user: '))]
        except IndexError:
            print(c.WARNING + 'Please select a correct number' + c.ENDC)
            continue
        else:
            print('')
            break

    # Retrieve user configuration
    configuration = get_user(data['username'])
    data['main_dir'] = configuration['main_dir']

    # Subdir selection
    print(c.HEADER + c.BOLD + '==== SUBDIRECTORIES IN MAIN DIR ====' + c.ENDC)
    print(c.HEADER + 'Main directory: {}'.format(data['main_dir']))
    print(c.GREEN + c.BOLD + ' 0 ' + c.ENDC + 'Main upload directory (including all subdirectories) *')
    for cnt, subdir in enumerate(configuration['dirs'], 1):
        print(c.GREEN + c.BOLD + '{:2}'.format(cnt) + c.ENDC + ' {}'.format(subdir))

    while True:
        dirno = input('\nSelect which subdirectory to upload: ')
        if dirno == '':
            data['subdir'] = ''
            print('')
            break
        if int(dirno) == 0:
            data['subdir'] = ''
            print('')
            break
        else:
            try:
                data['subdir'] = configuration['dirs'][int(dirno) - 1]
            except IndexError:
                print(c.WARNING + 'Please select a correct number' + c.ENDC)
                continue
            else:
                print('')
                break

    # Uploadr action
    print(c.HEADER + c.BOLD + '==== Uploadr actions ====' + c.ENDC)
    print(c.GREEN + ' 1' + c.ENDC + ' Upload new photos to Flickr *')
    print(c.GREEN + ' 2' + c.ENDC + ' Only update database')

    while True:
        action = input('\nSelect required action: ')
        if action == '':
            data['action'] = 'update_remote'
            print('')
            break
        if int(action) == 1:
            data['action'] = 'update_remote'
            print('')
            break
        elif int(action) == 2:
            data['action'] = 'update_db'
            print('')
            break
        else:
            print(c.WARNING + 'Please select a correct number' + c.ENDC)
            continue

    # Update database
    print(c.HEADER + c.BOLD + '==== OPTIONS ====' + c.ENDC)
    data['update'] = get_bool(c.GREEN + 'Update database before upload?' + c.ENDC + ' (y / n *) ', default=False)

    # Privacy selection
    data['public'] = get_bool(c.GREEN + 'Uploaded photos are public?' + c.ENDC + ' (y * / n) ')
    data['friends'] = get_bool(c.GREEN + 'Uploaded photos are visible for friends?' + c.ENDC + ' (y * / n) ')
    data['family'] = get_bool(c.GREEN + 'Uploaded photos are visible for family?' + c.ENDC + ' (y * / n) ')
    print('')

    print(c.HEADER + c.BOLD + '==== START UPLOADR ====' + c.ENDC)
    proc_iput(data)


if __name__ == "__main__":
    main()
