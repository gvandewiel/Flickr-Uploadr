"""Threaded uploader modulue.

This module allows to activate multiple FlickrAPI instances to run concurrently
"""

from __future__ import print_function
from queue import Queue
import flickrapi
import exifread
import logging
import os
import re
from .output_dict import OutDict
from .database import FlickrDatabase
from .photos import Photos
from .albums import Albums
from .uploader import Uploader
from . import common
import threading
import configparser

__version__ = '2.0.2'


class FlickrCore(threading.Thread):
    """Threaded uploader."""

    def _add_subclass(self):
        # Add additional classes
        self.db = FlickrDatabase(self)
        self.photos = Photos(self)
        self.albums = Albums(self)
        self.uploader = Uploader(self)

    def __init__(self, user=None, queue=None, method='', mkwargs=''):
        """Summary

        Args:
            user (None, optional): Description
            queue (None, optional): Description

        Returns:
            TYPE: Description
        """
        threading.Thread.__init__(self)

        # Export progress values
        self.progress = {}

        # Setup logging
        self.logger = logging.getLogger('FlickrUploader')
        # self.logger.setLevel(logging.INFO)

        # Set some instance variables
        self.user = user
        self.method = method
        self.mkwargs = mkwargs
        self.album_up2date = False

        self.exclude_folders = ['raw', 'rejects', '@eaDir']
        self.photo_ext = '.*\.gif|.*\.png|.*\.jpg|.*\.jpeg|.*\.tif|.*\.tiff'
        self.video_ext = '.*\.mov|.*\.avi|.*\.mp4'

        # Retrieve configuration
        if user is None:
            self.logger.error('No username provided')
            raise ValueError('user = None or blank')

        # Read configuration paramters from file in User directory
        config = configparser.ConfigParser()
        try:
            config.read(os.path.join(os.path.expanduser("~"), 'flickr', 'config.ini'))
        except:
            self.logger.error('"~/flickr/config.ini" file not found.')
            raise IOError('"~/flickr/config.ini" file not found.')

        if len(config.sections()) is 0:
            self.logger.error('No configuration provided in file')
            raise ValueError('No configuration provided in file')

        self.configuration = {}
        if user in config.sections():
            self.configuration['api_key'] = config.get(user, 'api_key')
            self.configuration['api_secret'] = config.get(user, 'api_secret')
            self.configuration['main_dir'] = config.get(user, 'root_dir')
        else:
            self.logger.error('User "{}" not found in dictionary'.format(user))
            pass

        # Setup output dictionary
        if queue is None:
            self.logger.warning("No queue provided")
            self.logger.warning("A queue object will be created")
            self.queue = Queue()
        else:
            self.queue = queue

        self.logger.info('FlickrUpload: Starting output_dictionary')
        # self.out_dict = OutDict(queue=None)
        self.out_dict = OutDict(self.queue)
        self.out_dict.clear()

        # Start FlickrAPI
        self.logger.info('Starting FlickrAPI and database connection')
        self.progress = self.out_dict(msg1='Starting FlickrAPI and database connection')
        self.flickr = flickrapi.FlickrAPI(self.configuration['api_key'], self.configuration['api_secret'])

        try:
            self.flickr.authenticate_via_browser(perms='delete')
        except:
            del self.flickr
            self.flickr = flickrapi.FlickrAPI(self.configuration['api_key'], self.configuration['api_secret'])
            self.flickr.get_request_token(oauth_callback='oob')
            authorize_url = self.flickr.auth_url(perms='delete')
            print('Visit: {}'.format(authorize_url))
            verifier = str(input('Verifier code: '))
            self.flickr.get_access_token(verifier)

        # Start database connection and functions
        self.logger.info('Initate Flickr2SQLite module')
        self.progress = self.out_dict(msg2='FlickrUpload: Initate Flickr2SQLite module')

        self._add_subclass()
        '''
        self.db = FlickrDatabase(flickr=self.flickr,
                                 out_dict=self.out_dict,
                                 user=user)
        '''
        # print('\n')

    def __del__(self):
        self.progress = self.out_dict(msg1='Uploadr Thread died...')
        self.logger.info('Uploadr Thread died...')
        self.progress = self.out_dict(exitFlag=True)

    def run(self):
        if self.method == 'update_remote':
            self.logger.debug('Running Uploadr => remote_update')
            self.update_remote(**self.mkwargs)

        elif self.method == 'update_db':
            self.logger.debug('Running Uploadr => update_db')
            self.logger.info('Rebuilding database')

            self.progress = self.out_dict(msg1='Rebuilding database')
            self.db.rebuild_database()
            
            self.progress = self.out_dict.clear()

            self.logger.info('Uploadr Thread died...')
            self.progress = self.out_dict(msg1='Uploadr Thread died...')
            self.progress = self.out_dict(exitFlag=True)

        elif self.method == '':
            self.logger.warning('Running Uploadr => No method specified!')
            exit()

        else:
            self.logger.warning('Running Uploadr => Method not available')
            exit()

    def update_remote(self, main_dir='', subdir='', public=False, family=False, friends=False, update=False):
        """Check input
        If no main_dir is provided only on update of the users database
        is possible. If update parameter is False (or empty) the function
        will exit without any action. If update is True the databse will
        be updated and the function will exit."""

        '##### Nested functions #####'

        def _check_datetaken(fname=''):
            """Open image file for reading (binary mode)."""
            if fname == '':
                datetaken = ''
            else:
                try:
                    with open(fname, 'rb') as f:
                        # Return Exif tags
                        tags = exifread.process_file(f, details=False)
                        # Retrieve DateTimeOriginal
                        datetaken = str(tags['EXIF DateTimeOriginal'])
                        # Remove colon in string
                        datetaken = datetaken.replace(":", "")
                        # Remove whitepace from datetaken string
                        datetaken = datetaken.replace(" ", "")
                except:
                    datetaken = ''
            return datetaken

        def _check_folder(dirname='', filelist=''):
            # Check folder is hidden (starts with .)
            b_hidden = re.match('^\.', os.path.basename(dirname))
            b_exclude = common.normalize(os.path.basename(dirname)) in self.exclude_folders

            # Make list of files to be uploaded
            img_list = [name for name in filelist
                        if not name.startswith(".") and
                        (common.normalize(name.rsplit(".", 1)[-1]) in self.photo_ext or
                         common.normalize(name.rsplit(".", 1)[-1]) in self.video_ext)]

            img_cnt = len(img_list)

            b_img_cnt = img_cnt == 0

            if b_hidden or b_exclude or b_img_cnt:
                self.logger.debug('Skipped folder:  {}'.format(os.path.basename(dirname)))
                return None

            else:
                # Determine the title of the folder
                if os.path.basename(dirname) == '':
                    album_title = os.path.basename(os.path.normpath(dirname))
                else:
                    album_title = os.path.basename(dirname)

                # Message in CLI to show which folder is being processed
                print('')
                self.logger.info('Processing: {} ({} files)'.format(album_title, img_cnt))
                self.progress = self.out_dict(total_images=img_cnt)

                # # print out excluded files
                for file in filelist:
                    if file.startswith(".") or \
                        (common.normalize(file.rsplit(".", 1)[-1]) not in self.photo_ext and
                         common.normalize(file.rsplit(".", 1)[-1]) not in self.video_ext):
                        self.logger.debug('Skipped file: {}'.format(file))
                        pass

                # Find album id (if any)
                album_id = self.find_album(album_title)

                # Retrieve photo_id's from the local database
                if album_id is not False:
                    photo_dict = self.db.retrieve_album_photos(album_id)

                    self.progress = self.out_dict(album=album_title,
                                                  total_images=img_cnt,
                                                  album_id=album_id)
                else:
                    photo_dict = {}

                return {'album_title': album_title,
                        'album_id': album_id,
                        'photo_dict': photo_dict,
                        'filtered_file_list': img_list}

        '############################'

        if main_dir == '' and update is False:
            exit()
            self.progress = self.out_dict(exitFlag=True)

        if main_dir == '' and update is True:
            self.logger.info('Make local copy of Flickr database')
            self.progress = self.out_dict(msg1='Make local copy of Flickr database')
            # Rebuild database
            self.db.rebuild_database()

            # Clear out_dict
            self.out_dict.clear()

            # Tell GUI update is finished
            self.progress = self.out_dict(exitFlag=True)
            # Exit function
            exit()

        if main_dir != '' and update is True:
            self.logger.info('Make local copy of Flickr database')
            self.progress = self.out_dict(msg1='Make local copy of Flickr database')
            # Rebuild database
            self.db.rebuild_database()

            # Clear out_dict
            self.out_dict.clear()

        if main_dir != '':
            # Start the upload process
            if subdir != '':
                main_dir = os.path.join(main_dir, subdir, '')
            self.logger.info('Start upload of main_dir = {}'.format(main_dir))
            self.progress = self.out_dict(msg1='Start upload of main_dir =',
                                          msg2=main_dir)

            # Determine the number of folders in main_dir
            total_folders = len(list(os.walk(main_dir)))
            self.progress = self.out_dict(total_albums=total_folders)

            # Set the number of processed folders
            folder_count = 0

            # Start of dirloop
            for dirname, subdirlist, filelist in os.walk(main_dir, topdown=True):
                subdirlist[:] = [d for d in subdirlist if d not in self.exclude_folders]
                folder_count += 1

                # Check if folder needs processing
                cf = _check_folder(dirname=dirname, filelist=filelist)
                if cf is not None:
                    album_title = cf['album_title']
                    album_id = cf['album_id']
                    photo_dict = cf['photo_dict']
                    filtered_file_list = cf['filtered_file_list']

                    self.progress = self.out_dict(album=os.path.basename(dirname),
                                                  total_albums=total_folders,
                                                  actual_album=folder_count)

                    # Loop over filtered filelist
                    total_images = len(filtered_file_list)
                    photo_count = 0
                    for file in filtered_file_list:
                        photo_count += 1
                        
                        # Set full path of image file
                        print('\tChecking file: {}'.format(file), end='\r')
                        fname = os.path.join(dirname, file)

                        # Calculate checksum of file
                        real_md5 = common.md5sum(fname)
                        real_sha1 = common.sha1sum(fname)

                        self.logger.debug('Processing {} of {}'.format(photo_count, total_images))
                        self.progress = self.out_dict(actual_image=photo_count,
                                                      total_images=total_images,
                                                      filename=file,
                                                      md5=real_md5,
                                                      sha1=real_sha1)

                        # Check local and remote databse for photo
                        photo_id, photo = self.find_photo(real_md5)
                        datetaken = _check_datetaken(fname)

                        '##### Photo management #####'
                        # Photo not uploaded
                        if photo_id is False:
                            self.logger.info('Nothing found in local or remote database')
                            self.progress = self.out_dict(msg1='Nothing found in local or remote database',
                                                          msg2='Uploading photo...')

                            # Start upload of new photo
                            photo_id, photo = self.uploader(fname, file, real_md5, real_sha1, public, family, friends)

                            # If photo is correctly uploaded a photo_id is provided by Flickr
                            if photo_id is not False:
                                self.logger.info('Photo uploaded to Flickr with id: {}'.format(photo_id))
                                self.progress = self.out_dict(msg1='Photo uploaded to Flickr',
                                                              msg2='')

                                # Add newly uploaded photo to photolist
                                self.logger.debug('Adding photo to dict after upload')
                                self.logger.debug(self.photo_to_dict(photo), photo_dict)
                                photo_dict = self.photos.add_to_album(self.photos.photo_to_dict(photo), photo_dict)

                        # Photo already uploaded
                        elif photo_id is not False:
                            if type(photo) is dict:
                                photo_dict = self.photos.add_to_album(photo, photo_dict)
                            else:
                                photo_dict = self.photos.add_to_album(self.photos.photo_to_dict(photo), photo_dict)

                        # Delete all photo variables
                        if 'file' in locals():
                            del file
                        if 'fname' in locals():
                            del fname
                        if 'real_md5' in locals():
                            del real_md5
                        if 'real_sha1' in locals():
                            del real_sha1
                        if 'tags' in locals():
                            del tags
                        if 'photo_id' in locals():
                            del photo_id
                        if 'photo' in locals():
                            del photo
                        if 'datetaken' in locals():
                            del datetaken

                        'Check for an exifFlag to exit the file loop'
                        if self.progress['stop'] is True:
                            self.logger.warning('ExitFlag recieved')
                            self.logger.warning('Breaking out file loop')

                            self.progress = self.out_dict(msg1='ExitFlag recieved',
                                                          msg2='Breaking out file loop...')
                            break
                    # End of file loop

                    '##### Album management #####'
                    # Create album
                    if album_id is False:
                        self.progress = self.out_dict(msg1='Creating new album')
                        album_id = self.albums.create_album(album_title=album_title, photo_dict=photo_dict)

                    # Update album
                    self.logger.info('Updating album "{}"'.format(album_title))
                    self.progress = self.out_dict(msg1='Updating album')
                    self.albums.update_album(album_id=album_id, album_title=album_title, photo_dict=photo_dict)

                    # Delete all album variables
                    if 'album_id' in locals():
                        del album_id
                    if 'album_title' in locals():
                        del album_title
                    if 'photo_dict' in locals():
                        del photo_dict
                    if 'filtered_file_list' in locals():
                        del filtered_file_list

                    # Check for an exifFlag to exit the dir loop
                    if self.progress['stop'] is True:
                        self.logger.warning('ExitFlag recieved')
                        self.logger.warning('Breaking out file loop')
                        self.progress = self.out_dict(msg1='ExitFlag recieved',
                                                      msg2='Breaking out file loop...')
                        break

                    # Clear output dict
                    self.progress = self.out_dict.clear()

            self.progress = self.out_dict.clear()

            self.logger.info('Finished processing all local folders')
            self.progress = self.out_dict(msg1='Finished processing all local folders')

            self.progress = self.out_dict(msg2='Sorting albums')
            self.sort_albums()

            self.logger.info('Finished sorting albums.')
            self.progress = self.out_dict(msg2='Finished sorting albums.')

        self.progress = self.out_dict.clear()
        self.logger.info('Uploadr Thread died...')
        self.progress = self.out_dict(msg1='Uploadr Thread died...')
        self.progress = self.out_dict(exitFlag=True)
