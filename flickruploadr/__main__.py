from __future__ import print_function
from optparse import OptionParser
import os

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


def main(args=None):
    """The main routine."""
    parser = OptionParser()
    parser.add_option("-c", "--console",
                      action="store_true", dest="console", default=False,
                      help="Run FlickrUploadr from console")

    parser.add_option("-g", "--gui",
                      action="store_true", dest="gui", default=False,
                      help="Run FlickrUploadr with GUI")

    parser.add_option("-a", "--add",
                      action="store_true", dest="add", default=False,
                      help="Add user to config file")

    (options, args) = parser.parse_args()

    if options.console:
        from .ui.console import main as console
        console()
    elif options.gui:
        from .ui.gui import main as gui
        gui()
    elif options.add:
        add_user()
    elif options.console and options.gui:
        print("FlickrUploadr can't run in console and GUI simultaneously")
    else:
        print("FlickrUploadr did not recieve any command flags, exiting...")


def add_user():
    print(c.HEADER + c.BOLD + '==== CREATE NEW USER ====' + c.ENDC)
    print(c.HEADER + 'Visit below website to apply for API-key' + c.ENDC)
    print('https://www.flickr.com/services/apps/create/noncommercial/')
    username = input('\nUsername: ')
    api_key = input('API Key: ')
    api_secret = input('API Secret: ')
    root_dir = input('Root directory: ')

    with open(os.path.join(os.path.expanduser("~"), 'flickr', 'config.ini'), "a+") as f:
        f.write('\n[{}]'.format(username))
        f.write('\napi_key: {}'.format(api_key))
        f.write('\napi_secret: {}'.format(api_secret))
        f.write('\nroot_dir: {}'.format(root_dir))
        f.write('\n')

if __name__ == "__main__":
    main()
