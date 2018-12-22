"""Threaded uploader modulue.

This module allows to activate multiple FlickrAPI instances to run concurrently
"""

from __future__ import print_function
from queue import Queue
import flickrapi
import exifread
import os
import re
import logging
import threading
import configparser

from .output_dict import OutDict
from .database import FlickrDatabase
from .photos import Photos
from .albums import Albums
from .parser import Parser
from .uploader import Uploader
from . import common

__version__ = '2.0.2'


class FlickrCore(threading.Thread):
    def _add_subclasses(self):
        # Add additional classes
        'Local database I/O'
        self.db = FlickrDatabase(self)

        'Handling of local and remote photo objects'
        self.photos = Photos(self)

        'Handling of local and remote album objects'
        self.albums = Albums(self)

        'Parser for local directory structure'
        self.parser = Parser(self)

        'Uploads a single photo / video to flickr'
        self.uploader = Uploader(self)

    def __init__(self, user=None, queue=None, method='', dry_run=False, mkwargs=''):
        """Summary

        Args:
            user (None, optional): Description
            queue (None, optional): Description

        Returns:
            TYPE: Description
        """

        # Init thread
        threading.Thread.__init__(self)

        # Set some instance variables
        self.user = user
        self.method = method
        self.dry_run = dry_run
        self.mkwargs = mkwargs
        self.album_up2date = False

        self.exclude_folders = ['raw', 'rejects', '@eaDir']
        self.photo_ext = '.*\.gif|.*\.png|.*\.jpg|.*\.jpeg|.*\.tif|.*\.tiff'
        self.video_ext = '.*\.mov|.*\.avi|.*\.mp4'

        'Start logger'
        'Prepare output dictionary'
        self.logger, self.progress = self.__prep_logging__(queue)

        'Read configuration file'
        'Return dict with configuration data'
        configuration = self.__read_config__(user)

        'Start FlickrAPI'
        self.flickr = self.__start_flickr__(configuration)

        # Start database connection and functions
        self.logger.info('Initate Flickr2SQLite module')
        self.progress(msg2='FlickrUpload: Initate Flickr2SQLite module')

        # Extend FlickrCore with additional classes by composition
        self._add_subclasses()
        self.set_log_level('INFO')

    def __del__(self):
        self.progress(msg1='Uploadr Thread died...')
        self.logger.info('Uploadr Thread died...')
        self.progress(exitFlag=True)

    def __prep_logging__(self, queue):
        logger = common.create_logger('FlickrCore')

        # Setup output dictionary
        if queue is None:
            logger.debug("No queue provided")
            logger.debug("A queue object will be created")
            queue = Queue()

        logger.info('FlickrUpload: Starting output_dictionary')
        progress = OutDict(queue)
        progress.clear()

        return logger, progress

    def set_log_level(self, *args):
        for key in logging.Logger.manager.loggerDict.keys():
            if 'Flickr' in key:
                if len(args) == 0:
                    logging.getLogger(key).setLevel(logging.WARNING)
                else:
                    if args[0] == 'INFO':
                        logging.getLogger(key).setLevel(logging.INFO)
                    if args[0] == 'DEBUG':
                        logging.getLogger(key).setLevel(logging.DEBUG)

    def __read_config__(self, user):
        # Retrieve configuration
        self.logger.debug('Reading configuration file')
        configuration = {}

        if user is None:
            self.logger.error('No username provided')
            raise ValueError('user = None or blank')
        else:
            # Read configuration paramters from file in User directory
            try:
                config = configparser.ConfigParser()
                config.read(os.path.join(os.path.expanduser("~"), 'flickr', 'config.ini'))

                if len(config.sections()) is 0:
                    self.logger.error('No configuration provided in file')
                    raise ValueError('No configuration provided in file')
                elif user in config.sections():
                    configuration['api_key'] = config.get(user, 'api_key')
                    configuration['api_secret'] = config.get(user, 'api_secret')
                    configuration['main_dir'] = config.get(user, 'root_dir')
                else:
                    self.logger.error('User "{}" not found in dictionary'.format(user))
                    pass
            except:
                self.logger.error('"~/flickr/config.ini" file not found.')
                raise IOError('"~/flickr/config.ini" file not found.')

        return configuration

    def __start_flickr__(self, configuration):
        self.logger.info('Starting FlickrAPI')
        self.progress(msg1='Starting FlickrAPI')

        flickr = flickrapi.FlickrAPI(configuration['api_key'],
                                     configuration['api_secret'])

        try:
            flickr.authenticate_via_browser(perms='delete')
        except:
            del flickr
            flickr = flickrapi.FlickrAPI(configuration['api_key'],
                                              configuration['api_secret'])

            flickr.get_request_token(oauth_callback='oob')

            # Require user action to retrieve verifier code
            authorize_url = self.flickr.auth_url(perms='delete')
            print('Visit: {}'.format(authorize_url))

            verifier = str(input('Verifier code: '))
            flickr.get_access_token(verifier)

        return flickr

    def run(self):
        if self.method == 'update_remote':
            self.logger.debug('Running Uploadr => remote_update')
            self.parser(**self.mkwargs)

        elif self.method == 'update_db':
            self.logger.debug('Running Uploadr => update_db')
            self.logger.info('Rebuilding database')

            self.progress(msg1='Rebuilding database')
            self.db.rebuild_database()

            self.progress.clear()

            self.logger.info('Uploadr Thread died...')
            self.progress(msg1='Uploadr Thread died...')
            self.progress(exitFlag=True)

        elif self.method == '':
            self.logger.warning('Running Uploadr => No method specified!')
            exit()

        else:
            self.logger.warning('Running Uploadr => Method not available')
            exit()
