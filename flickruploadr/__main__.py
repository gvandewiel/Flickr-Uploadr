from __future__ import print_function
from optparse import OptionParser
from .ui.console import main as console
from .ui.gui import main as gui


def main(args=None):
    """The main routine."""
    parser = OptionParser()
    parser.add_option("-c", "--console",
                      action="store_true", dest="console", default=False,
                      help="Run FlickrUploadr from console")

    parser.add_option("-g", "--gui",
                      action="store_true", dest="gui", default=False,
                      help="Run FlickrUploadr with GUI")

    (options, args) = parser.parse_args()

    if options.console:
        console()
    elif options.gui:
        gui()
    elif options.console and options.gui:
        print("FlickrUploadr can't run in console and GUI simultaneously")
    else:
        print("FlickrUploadr did not recieve any command flags, exiting...")

if __name__ == "__main__":
    main()
