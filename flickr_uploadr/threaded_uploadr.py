"""Threaded uploader modulue.

This module allows to activate multiple FlickrAPI instances to run concurrently
"""
#from gevent.queue import Queue
from queue import Queue

import flickrapi
import exifread
import logging
from time import sleep
import os
import re
from .output_dict import OutDict
from .database import FlickrDatabase
from . import common
import threading
import configparser


class Uploadr(threading.Thread):
    """Threaded uploader."""

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
        self.logger.setLevel(logging.INFO)

        # add a rotating handler
        # if not os.path.exists('logs'):
        #     os.makedirs('logs')
        # log_name = '{}_{}.log'.format(user, method)
        # handler = logging.FileHandler(os.path.join('logs',log_name))
        # self.logger.addHandler(handler)

        # Green Bold  = \033[1m\033[92m
        # Red bold    = \033[91m\033[1m
        # Yellow bold = \033[93m\033[1m
        # Normal      = \033[0m

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
        self.progress = self.out_dict.add_to_queue(msg1='Starting FlickrAPI and database connection')
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
        self.progress = self.out_dict.add_to_queue(msg2='FlickrUpload: Initate Flickr2SQLite module')
        self.db = FlickrDatabase(flickr=self.flickr,
                                 out_dict=self.out_dict,
                                 user=user)
        # print('\n')

    def __del__(self):
        self.progress = self.out_dict.add_to_queue(msg1='Uploadr Thread died...')
        self.logger.info('Uploadr Thread died...')
        self.progress = self.out_dict.add_to_queue(exitFlag=True)

    def run(self):
        if self.method == 'update_remote':
            self.logger.debug('Running Uploadr => remote_update')
            # print('\t\t{}'.format(self.mkwargs))
            self.update_remote(**self.mkwargs)
        elif self.method == 'update_db':
            self.logger.debug('Running Uploadr => update_db')
            self.update_db()
        elif self.method == '':
            self.logger.warning('Running Uploadr => No method specified!')
            exit()
        else:
            self.logger.warning('Running Uploadr => Method not available')
            exit()

    def get_progress(self):
        d = self.queue.get()
        return d

    def callback(self, progress):
        print('\rUploading: {:3}%'.format(progress))
        self.progress = self.out_dict.add_to_queue(upload_progress=progress)

    def update_db(self):
        self.logger.info('Rebuilding database')
        self.progress = self.out_dict.add_to_queue(msg1='Rebuilding database')

        self.db.rebuild_database()

        self.progress = self.out_dict.clear()
        self.logger.info('Uploadr Thread died...')
        self.progress = self.out_dict.add_to_queue(msg1='Uploadr Thread died...')
        self.progress = self.out_dict.add_to_queue(exitFlag=True)

    def find_photo(self, md5):
        photo_id, photo = self.find_local_photo(md5)
        if photo_id is False:
            photo_id, photo = self.find_flickr_photo(md5)
        return photo_id, photo

    def find_local_photo(self, md5):
        query = "SELECT * FROM photos WHERE md5='{}'".format(md5)
        result = self.db.sql(query).fetchone()
        '''OUTPUT FROM SQLite query:
               0 = id
               1 = title
               2 = md5
               3 = sha1
               4 = public
               5 = friend
               6 = family
               7 = date_taken'''
        if result is None:
            return False, False
        else:
            data_dict = dict()
            data_dict['photo_id'] = result[0]
            data_dict['photo_title'] = result[1]
            data_dict['md5'] = result[2]
            data_dict['sha1'] = result[3]
            data_dict['public'] = result[4]
            data_dict['friend'] = result[5]
            data_dict['family'] = result[6]
            data_dict['date_taken'] = result[7]
            return result[0], data_dict

    def find_flickr_photo(self, md5, write_to_db=True):
        # Check flickr database
        if common.MD5_MACHINE_TAG_PREFIX not in md5:
            md5 = common.MD5_MACHINE_TAG_PREFIX + md5

        photo_list = self.flickr.photos_search(user_id="me",
                                               tags=str(md5),
                                               extras="date_taken,machine_tags,description")

        photo_elements = photo_list.getchildren()[0]

        # Check if there are any results
        if len(photo_elements) == 0:
            return False, False
        else:
            # Check if the md5 hash is found more than once.
            if len(photo_elements) > 1:
                # Mark all photos for removal except first one
                for i, elem in enumerate(photo_elements[1:]):
                    self.logger.debug('Marking photo with id "{}" for removal'.format(photo_elements[0].attrib['id']))
                    self.progress = self.out_dict.add_to_queue(msg2='Marking photo with id "{}" for removal'.format(photo_elements[0].attrib['id']))

                    self.flickr.photos.addTags(photo_id=photo_elements[0].attrib['id'],
                                               tags='ToDelete')

            # Add the first photo to the local database
            if write_to_db:
                self.db.write_flickr_photo(obj_photo=photo_elements[0], table='photos')
            return photo_elements[0].attrib['id'], photo_elements[0]

    def find_album(self, album_title):
        # Search for album_title in local database
        album_id = self.find_local_album(album_title)
        if album_id is False:
            # Album is not found in local database
            # Update local database and try again
            album_id = self.find_flickr_album(album_title)
            if album_id is False:
                self.logger.info('Album "{}" not found in updated database'.format(album_title))
                self.progress = self.out_dict.add_to_queue(msg1='Album not found in updated database')
        return album_id

    def find_local_album(self, album_title):
        query = "SELECT id FROM albums WHERE album_title ='{}'".format(album_title)
        id = self.db.sql(query).fetchone()

        if id is None:
            return False
        else:
            return id[0]

    def find_flickr_album(self, album_title):
        if self.album_up2date is False:
            self.logger.info('Updating album database')
            self.progress = self.out_dict.add_to_queue(msg1='Updating album database')
            self.db.list_albums(update=False, verbose=False)
            self.album_up2date = True
        return self.find_local_album(album_title)

    def photo_to_dict(self, photo):
        data_dict = dict()
        machine_tags = photo.attrib['machine_tags'].split(' ')

        data_dict['photo_id'] = photo.attrib['id']
        data_dict['photo_title'] = photo.attrib['title']
        data_dict['md5'] = machine_tags[0].replace(common.MD5_MACHINE_TAG_PREFIX, '')
        data_dict['sha1'] = machine_tags[1].replace(common.SHA1_MACHINE_TAG_PREFIX, '')
        data_dict['public'] = photo.attrib['ispublic']
        data_dict['friend'] = photo.attrib['isfriend']
        data_dict['family'] = photo.attrib['isfamily']
        data_dict['date_taken'] = common.flickr_date_taken(photo)
        return data_dict

    def add_to_album(self, data_dict, photo_dict):
        """Dictionary of photo data.

        data_dict should contain the following key:value pairs:
            photo_id
            photo_title
            md5
            sha1
            public
            friend
            family
            date_taken
        """
        photo_dict[data_dict['photo_id']] = data_dict
        return photo_dict

    def add_to_album2(self, item, datetaken, photo_list):
        # Make set of photos
        photos = set(photo_list)
        # Search set for existing id;
        # add item to list if not found (preventing duplicates)
        if item not in photos:
            photos.add((item, datetaken))
        return list(photos)

    def sort_album_photos(self, album_id):
        sorted_photos = list()
        id_list = self.db.retrieve_album_photos().fetchall()

        for item in id_list:
            sorted_photos.append(item[0])

        sorted_ids = ','.join([str(x) for x in sorted_photos])
        self.flickr.photosets.reorderPhotos(photoset_id=str(album_id), photo_ids=str(sorted_ids))

        return sorted_photos

    def sort_albums(self, sort_photos=False, per_page=500):
        albums = dict()
        sorted_id = list()

        # Retrieve total number of albums in Flickr database
        total_albums = self.flickr.photosets_getList(per_page=str(per_page),
                                                     page="1")

        # Retrieve total number of pages to be looped over
        total_album_pages = int(total_albums.getchildren()[0].attrib['pages'])

        # Retrieve total sets
        total_albums = int(total_albums.getchildren()[0].attrib['total'])
        self.progress = self.out_dict.add_to_queue(total_albums=total_albums)

        # number of processed sets
        set_cnt = 0
        self.progress = self.out_dict.add_to_queue(actual_albums=set_cnt)

        self.progress = self.out_dict.add_to_queue(msg1='Sorting {} albums'.format(total_albums))
        self.logger.debug('Sorting {} albums'.format(total_albums))

        # Loop over all albums and retrieve ID, title and the number of photo's and video's
        for set_page in range(total_album_pages):
            # Overcome 0-based indexing
            set_page += 1

            set_list = self.flickr.photosets_getList(per_page=str(per_page),
                                                     page=str(set_page))

            # Retrieve sets from Flickr query
            set_elements = set_list.getchildren()[0]

            # Loop over sets from Flickr query
            for set in set_elements:
                set_cnt += 1
                self.progress = self.out_dict.add_to_queue(album_title=set.getchildren()[0].text, actual_albums=set_cnt)
                self.logger.debug('{} - Setname {}'.format(set_cnt, set.getchildren()[0].text))
                albums[set.getchildren()[0].text] = set.attrib['id']

            # Page exhausted
            set_page += 1

        self.logger.info('Sorting albums')
        self.progress = self.out_dict.add_to_queue(msg1='Sorting albums')

        for key in sorted(albums, reverse=True):
            # print("{}:{}".format(key, albums[key]))
            sorted_id.append(albums[key])

            # Sort album photos
            if sort_photos is True:
                self.logger.info('Reorder album photos for "{}"'.format(key))
                self.progress = self.out_dict.add_to_queue(msg2='Reorder album photos for "{}"'.format(key))
                self.sort_album_photos(albums[key])

        sorted_ids = ','.join([str(x) for x in sorted_id])

        self.logger.info('Reorder albums')
        self.flickr.photosets.orderSets(photoset_ids=sorted_ids)
        self.logger.debug('Finished reording photos')

    def upload_file(self, fname, file, tags, public, family, friends):
        """Check filesize before starting upload.

        Max filesize for pictures = 200 MB
        Max filesize for videos   =   1 GB
        """
        photo_id = True

        b = os.path.getsize(fname)
        self.logger.debug('filesize = ~{:.2f} MB'.format(b // 1000000))

        if common.normalize(file.rsplit(".", 1)[-1]) in self.photo_ext and b >= 209715200:
            self.logger.warning('Upload of "{}" failed'.format(file))
            self.logger.warning('Filesize of photo exceeds Flickr limit (200 MB)')

            self.progress = self.out_dict.add_to_queue(msg1='Upload failed.',
                                                       msg2='Filesize of photo exceeds Flickr limit (200 MB)')
            photo_id = False
            photo = False

        if common.normalize(file.rsplit(".", 1)[-1]) in self.video_ext and b >= 1073741824:
            self.logger.warning('Upload of "{}" failed'.format(file))
            self.logger.warning('Filesize of video exceeds Flickr limit (1 GB)')

            self.progress = self.out_dict.add_to_queue(msg1='Upload failed.',
                                                       msg2='Filesize of video exceeds Flickr limit (1 GB)')
            photo_id = False
            photo = False

        if photo_id is True:
            photo_id = False
            self.logger.info('Uploading "{}"'.format(file))
            self.progress = self.out_dict.add_to_queue(msg1='Uploading {}'.format(file))

            fileobj = common.FileWithCallback(fname, self.callback)

            self.flickr.upload(filename=fname,
                               fileobj=fileobj,
                               title=file,
                               tags=tags,
                               is_public=int(public),
                               is_family=int(family),
                               is_friend=int(friends))

            self.logger.debug('Waiting for Flickr response')
            self.progress = self.out_dict.add_to_queue(msg2='Waiting for Flickr response...')

            # photo_id = result.getchildren()[0].text
            md5 = tags.split(' ')[0]
            wcnt = 0

            # Wait until flickr has processed file
            while True:
                wcnt += 1
                ret = self.find_flickr_photo(md5=md5)
                self.logger.debug('Waiting for Flickr response ({}s)'.format(wcnt))

                self.progress = self.out_dict.add_to_queue(msg2='Waiting for Flickr response ({}s)'.format(wcnt))
                if ret[0] is not False:
                    photo_id = ret[0]
                    photo = ret[1]
                    break
                sleep(1)
        return photo_id, photo

    def check_folder(self, dirname='', filelist=''):
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
            self.progress = self.out_dict.add_to_queue(total_images=img_cnt)

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

                self.progress = self.out_dict.add_to_queue(album=album_title,
                                                           total_images=img_cnt,
                                                           album_id=album_id)
            else:
                photo_dict = {}

            return {'album_title': album_title,
                    'album_id': album_id,
                    'photo_dict': photo_dict,
                    'filtered_file_list': img_list}

    def check_datetaken(self, fname=''):
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

    def create_album(self, album_title, photo_dict):
        self.logger.info('Creating album "{}"'.format(album_title))
        self.progress = self.out_dict.add_to_queue(msg1='Creating new album')

        self.logger.debug('Finding primary photo')
        self.logger.debug(photo_dict)
        self.logger.debug(list(photo_dict.keys()))
        primary_photo_id = list(photo_dict.keys())[0]

        # Create new album on Flickr
        self.logger.debug('Make flickr request')
        album_id = self.flickr.photosets.create(title=album_title,
                                                description="",
                                                primary_photo_id=primary_photo_id)

        # Retrieve album_id from Flickr response
        album_id = album_id.getchildren()[0].attrib['id']

        self.logger.debug('Creating database table "{}"'.format(album_id))
        self.progress = self.out_dict.add_to_queue(msg2='Creating database table "{}"'.format(album_id))
        self.db.create_album_table(album_id)
        return album_id

    def update_album(self, album_id, album_title, photo_dict):
        self.logger.info('Updating album "{}" ({}) with {} items.'.format(album_title, album_id, len(photo_dict)))
        self.progress = self.out_dict.add_to_queue(msg1='Updating album "{}" ({})'.format(album_title, album_id),
                                                   msg2='with {} items'.format(len(photo_dict)))

        self.logger.debug('Loop over photos; add to db')
        for photo_id, photo in photo_dict.items():
            self.db.write_flickr_photo(dict_photo=photo, table=album_id)

        self.logger.info('Add photos to album at Flickr')
        self.progress = self.out_dict.add_to_queue(msg2='Add photos to album at Flickr')

        query = "SELECT id FROM '{}' ORDER BY date_taken ASC".format(album_id)
        rsp = self.db.sql(query)
        id_list = rsp.fetchall()
        sorted_id = list()
        for item in id_list:
            sorted_id.append(item[0])

        sorted_ids = ','.join([str(x) for x in sorted_id])
        while True:
            try:
                self.logger.debug('Make flickr request to update album photos')
                self.flickr.photosets.editPhotos(photoset_id=str(album_id),
                                                 primary_photo_id=sorted_id[0],
                                                 photo_ids=str(sorted_ids))
            except flickrapi.exceptions.FlickrError as e:
                self.logger.error('{}'.format(e))
                continue
            break

    def find(self, search_key, search_value, search_dict):
        for key, value in search_dict.items():
            if value[search_key] == search_value:
                return key

    def update_hashtag(self, photo_id='', real_md5sum='', real_sha1sum=''):
        # Retrieve tag_id from flickr for removal
        info_result = self.flickr.photos_getInfo(photo_id=photo_id)

        for t in info_result.getchildren()[0].find('tags'):
            if re.search('^' + common.MD5_MACHINE_TAG_PREFIX, t.attrib['raw']):
                m_md5 = t.attrib['id']
                self.flickr.photos.removeTag(tag_id=m_md5)

            if re.search('^' + common.SHA1_MACHINE_TAG_PREFIX, t.attrib['raw']):
                m_sha1 = t.attrib['id']

                self.logger.debug("Removing old SHA1 tag (" + m_sha1 + ")")
                self.flickr.photos.removeTag(tag_id=m_sha1)

        self.logger.debug("Setting MD5 tag = " + real_md5sum)
        self.flickr.photos.addTags(photo_id=photo_id, tags=common.MD5_MACHINE_TAG_PREFIX + real_md5sum)

        self.logger.debug("Setting SHA1 tag = " + real_sha1sum)
        self.flickr.photos.addTags(photo_id=photo_id, tags=common.SHA1_MACHINE_TAG_PREFIX + real_sha1sum)

    def update_flickr_hashes(self):
        local_dict = self.db.retrieve_album_photos('local')
        flickr_dict = self.db.retrieve_album_photos('photos')

        # Loop over all flickr photos
        for photo_id, data_dict in flickr_dict.items():
            if data_dict['photo_title'] != '':
                local_id = self.find(search_key='photo_title',
                                     search_value=data_dict['photo_title'],
                                     search_dict=local_dict
                                     )
                if local_id is not None:
                    flickr_md5 = data_dict['md5']
                    flickr_date_taken = data_dict['date_taken']

                    local_md5 = local_dict[local_id]['md5']
                    local_sha1 = local_dict[local_id]['sha1']
                    local_date_taken = local_dict[local_id]['date_taken']

                    if flickr_md5 != local_md5 and flickr_date_taken == local_date_taken:
                        self.logger.error('Local and remote hash do not match {}'.format(data_dict['photo_title']))
                        self.logger.error('Flickr hash = {}'.format(flickr_md5))
                        self.logger.error('Local hash = {}'.format(local_md5))

                        self.update_hashtag(photo_id=data_dict['photo_id'],
                                            real_md5sum=local_md5,
                                            real_sha1sum=local_sha1)

    def update_remote(self, main_dir='', subdir='', public=False, family=False, friends=False, update=False):
        """Check input
        If no main_dir is provided only on update of the users database
        is possible. If update parameter is False (or empty) the function
        will exit without any action. If update is True the databse will
        be updated and the function will exit."""
        if main_dir == '' and update is False:
            exit()
            self.progress = self.out_dict.add_to_queue(exitFlag=True)

        if main_dir == '' and update is True:
            self.logger.info('Make local copy of Flickr database')
            self.progress = self.out_dict.add_to_queue(msg1='Make local copy of Flickr database')
            # Rebuild database
            self.db.rebuild_database()

            # Clear out_dict
            self.out_dict.clear()

            # Tell GUI update is finished
            self.progress = self.out_dict.add_to_queue(exitFlag=True)
            # Exit function
            exit()

        if main_dir != '' and update is True:
            self.logger.info('Make local copy of Flickr database')
            self.progress = self.out_dict.add_to_queue(msg1='Make local copy of Flickr database')
            # Rebuild database
            self.db.rebuild_database()

            # Clear out_dict
            self.out_dict.clear()

        if main_dir != '':
            # Start the upload process
            if subdir != '':
                main_dir = os.path.join(main_dir, subdir, '')
            self.logger.info('Start upload of main_dir = {}'.format(main_dir))
            self.progress = self.out_dict.add_to_queue(msg1='Start upload of main_dir =',
                                                       msg2=main_dir)

            # Determine the number of folders in main_dir
            total_folders = len(list(os.walk(main_dir)))
            self.progress = self.out_dict.add_to_queue(total_albums=total_folders)

            # Set the number of processed folders
            folder_count = 0

            # Start of dirloop
            for dirname, subdirlist, filelist in os.walk(main_dir, topdown=True):
                subdirlist[:] = [d for d in subdirlist if d not in self.exclude_folders]
                folder_count += 1

                # Check if folder needs processing
                cf = self.check_folder(dirname=dirname, filelist=filelist)
                if cf is not None:
                    album_title = cf['album_title']
                    album_id = cf['album_id']
                    photo_dict = cf['photo_dict']
                    filtered_file_list = cf['filtered_file_list']

                    self.progress = self.out_dict.add_to_queue(album=os.path.basename(dirname),
                                                               total_albums=total_folders,
                                                               actual_album=folder_count)

                    # Loop over filtered filelist
                    total_images = len(filtered_file_list)
                    photo_count = 0
                    for file in filtered_file_list:
                        photo_count += 1
                        print('\tChecking file: {}'.format(file), end='\r')
                        # Set full path of image file
                        fname = os.path.join(dirname, file)

                        # Calculate checksum of file
                        real_md5 = common.md5sum(fname)
                        real_sha1 = common.sha1sum(fname)

                        # Generate machine tags
                        tags = '{md5_prefix}{md5} {sha1_prefix}{sha1}'.format(md5_prefix=common.MD5_MACHINE_TAG_PREFIX,
                                                                              sha1_prefix=common.SHA1_MACHINE_TAG_PREFIX,
                                                                              md5=real_md5,
                                                                              sha1=real_sha1)

                        self.logger.debug('Processing {} of {}'.format(photo_count, total_images))
                        self.progress = self.out_dict.add_to_queue(actual_image=photo_count,
                                                                   total_images=total_images,
                                                                   filename=file,
                                                                   md5=real_md5,
                                                                   sha1=real_sha1)

                        # Check local and remote databse for photo
                        photo_id, photo = self.find_photo(real_md5)
                        datetaken = self.check_datetaken(fname)

                        if photo_id is False:
                            self.logger.info('Nothing found in local or remote database')
                            self.progress = self.out_dict.add_to_queue(msg1='Nothing found in local or remote database',
                                                                       msg2='Uploading photo...')

                            # Start upload of new photo
                            retry = False
                            while True:
                                try:
                                    self.logger.debug('Trying to upload "{}" to Flickr'.format(file))
                                    self.logger.debug(' MD5 = {}'.format(real_md5))
                                    self.logger.debug('SHA1 = {}'.format(real_sha1))
                                    photo_id, photo = self.upload_file(fname, file, tags, public, family, friends)
                                    self.logger.debug('photo_id = {}'.format(photo_id))
                                    self.logger.debug('photo = {}'.format(photo))
                                except flickrapi.exceptions.FlickrError as e:
                                    if e == 'Error: 5: Filetype was not recognised' and retry is False:
                                        self.progress = self.out_dict.add_to_queue(msg2='Retry upload of {}'.format(file))
                                        self.logger.info('Retry upload of "{}"'.format(file))
                                        retry = True
                                        continue
                                    elif e == 'Error: 5: Filetype was not recognised' and retry is True:
                                        self.logger.info('Already retried upload of "{}"'.format(file))
                                        self.logger.info('Skipped upload of "{}"'.format(file))
                                        self.progress = self.out_dict.add_to_queue(msg2='Already retried upload of {}'.format(file))
                                        # exit while True loop
                                        break
                                # exit while True loop
                                break

                            # If photo is correctly uploaded a photo_id is provided by Flickr
                            if photo_id is not False:
                                self.logger.info('Photo uploaded to Flickr with id: {}'.format(photo_id))
                                self.progress = self.out_dict.add_to_queue(msg1='Photo uploaded to Flickr',
                                                                           msg2='')

                                # Add newly uploaded photo to photolist
                                self.logger.debug('Adding photo to dict after upload')
                                self.logger.debug(self.photo_to_dict(photo), photo_dict)
                                photo_dict = self.add_to_album(self.photo_to_dict(photo), photo_dict)

                        if photo_id is not False:
                            # Photo already uploaded
                            if type(photo) is dict:
                                # # print('already uploaded: {}'.format(photo))
                                photo_dict = self.add_to_album(photo, photo_dict)
                            else:
                                # self.logger.info('already uploaded: {}'.format(self.photo_to_dict(photo)))
                                photo_dict = self.add_to_album(self.photo_to_dict(photo), photo_dict)

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

                        # Check for an exifFlag to exit the file loop
                        if self.progress['stop'] is True:
                            self.logger.warning('ExitFlag recieved')
                            self.logger.warning('Breaking out file loop')

                            self.progress = self.out_dict.add_to_queue(msg1='ExitFlag recieved',
                                                                       msg2='Breaking out file loop...')
                            break
                    # End of file loop

                    # Create album
                    if album_id is False:
                        self.progress = self.out_dict.add_to_queue(msg1='Creating new album')
                        album_id = self.create_album(album_title=album_title, photo_dict=photo_dict)

                    # Update album
                    self.logger.info('Updating album "{}"'.format(album_title))
                    self.progress = self.out_dict.add_to_queue(msg1='Updating album')
                    self.update_album(album_id=album_id, album_title=album_title, photo_dict=photo_dict)

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
                        self.progress = self.out_dict.add_to_queue(msg1='ExitFlag recieved',
                                                                   msg2='Breaking out file loop...')
                        break

                    # Clear output dict
                    self.progress = self.out_dict.clear()

            self.progress = self.out_dict.clear()

            self.logger.info('Finished processing all local folders')
            self.progress = self.out_dict.add_to_queue(msg1='Finished processing all local folders')

            self.progress = self.out_dict.add_to_queue(msg2='Sorting albums')
            self.sort_albums()

            self.logger.info('Finished sorting albums.')
            self.progress = self.out_dict.add_to_queue(msg2='Finished sorting albums.')

        self.progress = self.out_dict.clear()
        self.logger.info('Uploadr Thread died...')
        self.progress = self.out_dict.add_to_queue(msg1='Uploadr Thread died...')
        self.progress = self.out_dict.add_to_queue(exitFlag=True)

    def update_local(self, main_dir=''):
        """Check input
        If no main_dir is provided only on update of the users database
        is possible. If update parameter is False (or empty) the function
        will exit without any action. If update is True the databse will
        be updated and the function will exit."""
        if main_dir != '':

            # Determine the number of folders in main_dir
            # total_folders = len(list(os.walk(main_dir)))

            # Set the number of processed folders
            folder_count = 0

            photo_id = 0
            # Start of dirloop

            # Create table with all local photos
            self.db.create_album_table('local')

            for dirname, subdirlist, filelist in os.walk(main_dir, topdown=False):
                folder_count += 1

                # Check if folder needs processing
                cf = self.check_folder(dirname=dirname, filelist=filelist)
                if cf is not None:
                    filtered_file_list = cf['filtered_file_list']

                    # Loop over filtered filelist
                    # total_images = len(filtered_file_list)
                    photo_count = 0
                    for file in filtered_file_list:
                        photo_id += 1
                        photo_count += 1
                        # Set full path of image file
                        fname = os.path.join(dirname, file)

                        # Calculate checksum of file
                        real_md5 = common.md5sum(fname)
                        real_sha1 = common.sha1sum(fname)

                        self.logger.info('\t{}'.format(fname))

                        # Determine datetaken
                        datetaken = self.check_datetaken(fname)

                        # Add photo to photo_dict
                        data_dict = {'photo_id': photo_id,
                                     'photo_title': file,
                                     'md5': real_md5,
                                     'sha1': real_sha1,
                                     'public': '0',
                                     'friend': '0',
                                     'family': '0',
                                     'date_taken': datetaken}

                        self.db.write_flickr_photo(dict_photo=data_dict, table='local')
        self.logger.info('Finished updating local table')
        self.progress = self.out_dict.clear()
        self.progress = self.out_dict.add_to_queue(msg1='Uploadr Thread died...')
        self.progress = self.out_dict.add_to_queue(exitFlag=True)
        self.logger.info('Uploadr Thread died...')


if __name__ == "__main__":
    # Initiate Uploadr class
    queue = Queue()

    # Setup class
    uploader = Uploadr(user='gvandewiel',
                       queue=queue,
                       method='update_remote',
                       mkwargs={'main_dir': '/Users/gvandewiel/Pictures/Prive/',
                                'public': False,
                                'family': True,
                                'friends': True,
                                'update': False})
    uploader.start()
    uploader.join()
