import logging
import re
import tempfile
from subprocess import call, Popen, PIPE
from datetime import datetime
import sqlite3 as sqlite
from . import common
import os


class FlickrDatabase():
    def __init__(self, flickr, out_dict, user):
        # Export progress values
        self.progress = {}

        # Setup logging
        self.logger = logging.getLogger('Flickr2SQLite')
        # self.logger.setLevel(logging.INFO)

        # Retrieve overall output dictionary
        self.out_dict = out_dict
        self.progress = self.out_dict.add_to_queue(msg1='Updating database...')
        # Retrieve flickr instance
        self.logger.info('Starting Flickr instance')
        self.flickr = flickr

        # Start connection to database
        self.logger.info('Starting database connection')
        self.progress = self.out_dict.add_to_queue(msg2='Starting database connection')
        sql_path = os.path.join(os.path.expanduser("~"), 'flickr', str(user) + '_flickr.sqlite')

        self.connection = sqlite.connect(sql_path, check_same_thread=False)
        self.cursor = self.connection.cursor()

        # Setup database tables
        self.logger.info('Create database tables...')
        self.progress = self.out_dict.add_to_queue(msg2='Creating database tables')
        self.__setup_photos_table__()
        self.__setup_albums_table__()

    def rebuild_database(self, local=False):
        if local:
            # Delete all tables in database
            queries = ["PRAGMA writable_schema = 1;",
                       "delete from sqlite_master where type in ('table', 'index', 'trigger') and name != 'local';",
                       "PRAGMA writable_schema = 0;",
                       "VACUUM;",
                       "PRAGMA INTEGRITY_CHECK;"]
        else:
            # Delete all flickr tables
            queries = ["PRAGMA writable_schema = 1;",
                       "DELETE FROM sqlite_master WHERE type IN ('table', 'index', 'trigger');",
                       "PRAGMA writable_schema = 0;",
                       "VACUUM;"]

        for query in queries:
            self.sql(query)

        # Setup two default tables (photos and albums)
        self.logger.info('Setup photos table')
        self.progress = self.out_dict.add_to_queue(msg2='Setup photos table')
        self.__setup_photos_table__()
        self.logger.info('Setup albums table')
        self.progress = self.out_dict.add_to_queue(msg2='Setup albums table')
        self.__setup_albums_table__()

        # Update photos table
        self.logger.info('Listing all Flickr photos')
        self.progress = self.out_dict.add_to_queue(msg2='Listing all Flickr photos')
        self.list_photos()

        # Update albums table and create all separate album tables
        self.logger.info('Listing all Flickr sets')
        self.progress = self.out_dict.add_to_queue(msg2='Listing all Flickr sets')
        self.list_albums(update=True)

        # Tell the gui that the rebuild has finished
        self.logger.info('Finished updating database')
        self.progress = self.out_dict.add_to_queue(msg2='Finished updating database')
        return True

    def sql(self, query='', data=''):
        self.cursor.execute(query, data)
        self.connection.commit()
        return self.cursor

    def __setup_photos_table__(self):
        query = "CREATE TABLE IF NOT EXISTS photos (id INT, photo_title TEXT, md5 TEXT, sha1 TEXT, public INT, friend INT, family INT, date_taken TEXT, PRIMARY KEY(id))"
        self.sql(query)

    def __setup_albums_table__(self):
        query = "CREATE TABLE IF NOT EXISTS albums (id INT, album_title TEXT, photos INT, videos INT, PRIMARY KEY(id))"
        self.sql(query)

    def create_album_table(self, album_id):
        # Delete existing ablum table
        query = "DROP TABLE IF EXISTS '{tn}'".format(tn=album_id)
        self.sql(query)

        # Create new album table
        query = "CREATE TABLE '{tn}' (id INT, photo_title TEXT, md5 TEXT, sha1 TEXT, public INT, friend INT, family INT, date_taken TEXT, PRIMARY KEY(id))".format(tn=album_id)
        self.sql(query)

    def flickr_date_taken(self, photo):
        date_taken = self.datestr(datetime.strptime(photo.attrib['datetaken'], '%Y-%m-%d %H:%M:%S'))
        return date_taken

    def datestr(self, date):
        """Return a flat string showing the datetaken from Flickr

        Requires the date input in the form 'Y-m-d H:M:S'
        """
        return '{:02d}{:02d}{:02d}{:02d}{:02d}{:02d}'.format(date.year,
                                                             date.month,
                                                             date.day,
                                                             date.hour,
                                                             date.minute,
                                                             date.second
                                                             )

    def check_machine_tags(self, photo):
        photo_id = photo.attrib['id']
        md5 = ''
        sha1 = ''
        try:
            machine_tags = photo.attrib['machine_tags'].split(' ')

            if md5 == '' and 'checksum:md5=' in machine_tags[0]:
                md5 = machine_tags[0].replace('checksum:md5=', '')

            if sha1 == '' and 'checksum:sha1=' in machine_tags[0]:
                sha1 = machine_tags[0].replace('checksum:sha1=', '')

            if md5 == '' and 'checksum:md5=' in machine_tags[1]:
                md5 = machine_tags[1].replace('checksum:md5=', '')

            if sha1 == '' and 'checksum:sha1=' in machine_tags[1]:
                sha1 = machine_tags[1].replace('checksum:sha1=', '')

            # Check for malformed checksum
            if self.check_hash(md5, 'md5') is False or self.check_hash(sha1, 'sha1') is False:
                self.logger.info("Malformed tags, downloading photo from flickr")
                # print(photo_id)
                self.progress = self.out_dict.add_to_queue(msg1='Malformed tags', msg2='Downloading photo from flickr')
                md5, sha1 = self.download_flickr_photo(photo_id)

            # Incomplete checksums
            if md5 == '' or sha1 == '':
                self.logger.info("Incomplete tags, downloading photo from flickr")
                # print(photo_id)
                self.progress = self.out_dict.add_to_queue(msg1='Incomplete tags', msg2='Downloading photo from flickr')
                md5, sha1 = self.download_flickr_photo(photo_id)

        # No machine tags available
        except:
            self.logger.info("No tags found, downloading photo from flickr")
            # print(photo_id)
            self.progress = self.out_dict.add_to_queue(msg1='No tags found', msg2='Downloading photo from flickr')
            md5, sha1 = self.download_flickr_photo(photo_id)

        return md5, sha1

    def check_hash(self, hash, type):
        if type == 'md5':
            if not re.search('^' + common.CHECKSUM_PATTERN + '$', hash):
                self.logger.info("Malformed MD5")
                self.progress = self.out_dict.add_to_queue(msg1="The MD5sum ('" + hash + "') was malformed.\n\nIt must be 32 letters long, each one of 0-9 or a-f.")
                return False

        if type == 'sha1':
            if not re.search('^' + common.CHECKSUM_PATTERN + '$', hash):
                self.logger.info("Malformed SHA1")
                self.progress = self.out_dict.add_to_queue(msg1="The SHA1sum ('" + hash + "') was malformed.\n\nIt must be 40 letters long, each one of 0-9 or a-f.")
                return False

    def download_flickr_photo(self, photo_id, temp=True, folder=''):
        self.progress = self.out_dict.add_to_queue(msg1='Downloading photo to determine checksum...')
        info_result = self.flickr.photos_getInfo(photo_id=photo_id)
        farm_url = common.info_to_url(info_result, 'o')

        # Make temporary file to download photo into
        if temp:
            f = tempfile.NamedTemporaryFile()
            f.close()

            # Download photo to temporary file
            self.logger.info("Downloading photo from flickr")
            self.progress = self.out_dict.add_to_queue(msg2='Downloading photo from Flickr')
            p = Popen(["curl", "--location", "-o", f.name, farm_url], stdout=PIPE, stderr=PIPE)
            out, err = p.communicate()

            # Calculate checksums
            real_md5sum = common.md5sum(f.name)
            real_sha1sum = common.sha1sum(f.name)

            # Add tags to photos
            for t in info_result.getchildren()[0].find('tags'):
                if re.search('^' + common.MD5_MACHINE_TAG_PREFIX, t.attrib['raw']):
                    m_md5 = t.attrib['id']

                    self.logger.info("Removing old MD5 tag (" + m_md5 + ")")
                    self.flickr.photos.removeTag(tag_id=m_md5)

                    self.logger.info("Setting MD5 tag = " + real_md5sum)
                    self.flickr.photos.addTags(photo_id=photo_id,
                                               tags=common.MD5_MACHINE_TAG_PREFIX + real_md5sum)

                if re.search('^' + common.SHA1_MACHINE_TAG_PREFIX, t.attrib['raw']):
                    m_sha1 = t.attrib['id']
                    self.logger.info("Removing old SHA1 tag (" + m_sha1 + ")")
                    self.flickr.photos.removeTag(tag_id=m_sha1)

                    self.logger.info("Setting SHA1 tag = " + real_sha1sum)
                    self.flickr.photos.addTags(photo_id=photo_id,
                                               tags=common.SHA1_MACHINE_TAG_PREFIX + real_sha1sum)

            # Remove temporary file
            self.logger.info("Removing temporary file.")
            call(["rm", f.name])

            return real_md5sum, real_sha1sum
        else:
            if not os.path.exists(folder):
                os.makedirs(folder)

            file = photo_id
            ext = common.normalize(farm_url.rsplit(".", 1)[-1])
            filename = os.path.join(folder, '{file}.{ext}'.format(file=file, ext=ext))

            self.logger.info("Downloading photo from flickr")
            p = Popen(["curl", "--location", "-o", filename, farm_url], stdout=PIPE, stderr=PIPE)
            out, err = p.communicate()

    def write_flickr_photo(self, obj_photo=None, dict_photo=None, table=''):
        if obj_photo is not None:
            # Retrieve photo information
            photo_id = obj_photo.attrib['id']
            photo_title = obj_photo.attrib['title']
            description = obj_photo.getchildren()[0].text

            if photo_title == '' and description is not None:
                self.logger.info('Setting "{}" description ("{}") as title'.format(photo_id, description))
                self.progress = self.out_dict.add_to_queue(msg2='Setting "{}" description ("{}") as title'.format(photo_id, description))
                photo_title = description
                self.flickr.photos.setMeta(photo_id=photo_id,
                                           title=photo_title,
                                           description='')

            date_taken = self.flickr_date_taken(obj_photo)
            public = obj_photo.attrib['ispublic']
            friend = obj_photo.attrib['isfriend']
            family = obj_photo.attrib['isfamily']

            '''Check for machine tags
                If None is returned the tags are missing, malformed or incomplete
                the photo is downloaded and the checksums are recalculated'''
            md5, sha1 = self.check_machine_tags(obj_photo)

            # Show checksums of photo
            self.progress = self.out_dict.add_to_queue(md5=md5, sha1=sha1)

            # Determine datetaken from flickr photo
            date_taken = self.flickr_date_taken(obj_photo)

        if dict_photo is not None:
            photo_id = dict_photo['photo_id']
            photo_title = dict_photo['photo_title']
            md5 = dict_photo['md5']
            sha1 = dict_photo['sha1']
            public = dict_photo['public']
            friend = dict_photo['friend']
            family = dict_photo['family']
            date_taken = dict_photo['date_taken']

        try:
            data = (photo_id, photo_title, md5, sha1, public, friend, family, date_taken)
            query = "INSERT OR REPLACE INTO '{tn}' VALUES ({dl})".format(tn=table, dl=','.join('?' * len(data)))
            self.sql(query, data)
        except KeyError:
            # print('obj_photo = {}'.format(obj_photo))
            # print('dict_photo = {}'.format(dict_photo))
            pass

    def write_flickr_album(self, obj_album=None, dict_album=None, update=True, verbose=True):
        if obj_album is not None:
            album_id = obj_album.attrib['id']
            album_title = obj_album.getchildren()[0].text
            album_photos = obj_album.attrib['photos']
            album_videos = obj_album.attrib['videos']

        if dict_album is not None:
            album_id = dict_album['album_id']
            album_title = dict_album['album_title']
            album_photos = dict_album['album_photos']
            album_videos = dict_album['album_videos']

        self.progress = self.out_dict.add_to_queue(album=album_title, album_id=album_id)
        # Write album into database
        if verbose:
            self.logger.info('Add album to albums table')
            pass

        data = (album_id, album_title, album_photos, album_videos)
        query = "INSERT OR REPLACE INTO '{tn}' VALUES ({dl})".format(tn='albums', dl=','.join('?' * len(data)))
        self.sql(query, data)
        if verbose:
            self.logger.info('Retrieve photos for {}'.format(album_title))
            self.progress = self.out_dict.add_to_queue(msg2='Retrieve photos for {}'.format(album_title))
            pass

        if update is True:
            self.logger.info('Updating photos in album "{}"'.format(album_title))
            self.progress = self.out_dict.add_to_queue(msg2='Updating photos in album "{}"'.format(album_title))
            update = self.write_photos_to_album(album_id=album_id)

    def write_photos_to_album(self, album_id, per_page=500):
        # Create table for album in the database
        self.create_album_table(album_id)

        # Make call to Flickr to get total photos and video's in set
        total_set_photos = self.flickr.photosets_getPhotos(photoset_id=album_id,
                                                           per_page=str(per_page),
                                                           page="1",
                                                           media="all")

        # Retrieve total number of pages to be looped over
        total_photo_pages = int(total_set_photos.getchildren()[0].attrib['pages'])

        # Retrieve total set photos
        total_set_photos = int(total_set_photos.getchildren()[0].attrib['total'])

        self.progress = self.out_dict.add_to_queue(total_images=total_set_photos, actual_image=0)
        # number of photos processed
        photo_count = 0

        # Loop over all album photos
        for photo_page in range(total_photo_pages):
            # Overcome 0-based indexing
            photo_page += 1

            photo_list = self.flickr.photosets_getPhotos(photoset_id=album_id,
                                                         per_page=str(per_page),
                                                         page=str(photo_page),
                                                         media="all",
                                                         extras="date_taken,machine_tags,description")
            # Retrieve photos from Flickr query
            photo_elements = photo_list.getchildren()[0]

            # Loop over photos from Flickr query
            for photo in photo_elements:
                photo_count += 1
                self.progress = self.out_dict.add_to_queue(actual_image=photo_count)
                self.logger.debug('Updating album photos {} of {}'.format(photo_count, total_set_photos))

                """Add photo to the correct album table.
                The function takes the entire photo object as input, al the
                processing of the information in the object is done in the
                write_flickr_photo function."""
                self.write_flickr_photo(obj_photo=photo, table=album_id)

            # Page exhausted, goto next page
            photo_page += 1
        # print('\n')

    def list_albums(self, per_page=500, update=True, verbose=True):
        if verbose:
            self.logger.info('Updating albums')
            pass

        # Retrieve total number of sets on Flickr
        total_albums = self.flickr.photosets_getList(per_page=str(per_page),
                                                     page="1")

        # Retrieve total number of pages to be looped over
        total_album_pages = int(total_albums.getchildren()[0].attrib['pages'])

        # Retrieve total sets
        total_albums = int(total_albums.getchildren()[0].attrib['total'])

        # number of processed sets
        set_count = 0

        # Update GUI
        self.progress = self.out_dict.add_to_queue(msg2='Updating albums', actual_album=set_count, total_albums=total_albums)

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
                set_count += 1

                if verbose:
                    self.logger.debug('Album {} of {}'.format(set_count, total_albums))
                    pass

                # Update GUI
                self.progress = self.out_dict.add_to_queue(msg2='Updating albums', actual_album=set_count)

                """Add album to albums table.
                    If update is True, a separate album table will be made
                    containing all the photos and videos belonging to the ablum.
                    The function takes the entire set object as input, al the
                    processing of the information in the object is done in the
                    write_flickr_album function."""
                self.progress = self.out_dict.add_to_queue(msg1='update sqlite database with album_id')
                self.write_flickr_album(obj_album=set, update=update, verbose=verbose)
            # Page exhausted, goto next page
            set_page += 1
        if verbose:
            self.logger.info('Finished updating albums')
            pass

    def list_photos(self, per_page=500):
        # Retrieve total number of photo's in Flickr database
        total_photos = self.flickr.photos_search(user_id="me",
                                                 per_page=str(per_page),
                                                 page="1",
                                                 media="all",
                                                 extras="date_taken,machine_tags,description")

        total_photo_pages = int(total_photos.getchildren()[0].attrib['pages'])
        total_photos = int(total_photos.getchildren()[0].attrib['total'])

        # Counter of processed photos
        photo_cnt = 0

        # Counter for pages
        photo_page = 0

        # Update GUI
        self.progress = self.out_dict.add_to_queue(msg2='Updating photos', actual_image=photo_cnt, total_images=total_photos)

        # Loop over all photos
        for photo_page in range(total_photo_pages):

            # Overcome 0-based indexing
            photo_page += 1

            photo_list = self.flickr.photos_search(user_id="me",
                                                   per_page=str(per_page),
                                                   page=str(photo_page),
                                                   media="all",
                                                   extras="date_taken,machine_tags,description")

            # Retrieve photos from Flickr query
            photo_elements = photo_list.getchildren()[0]

            for photo in photo_elements:
                photo_cnt += 1
                # self.logger.debug('Photo {} of {}'.format(photo_cnt, total_photos))
                print('\tPhoto {} of {}'.format(photo_cnt, total_photos), end='\r')

                # Update GUI
                self.progress = self.out_dict.add_to_queue(msg1='Updating photos', actual_image=photo_cnt)

                """Add photo to photos table.
                    The function takes the entire set object as input, al the
                    processing of the information in the object is done in the
                    write_flickr_photo function."""
                self.progress = self.out_dict.add_to_queue(msg1='Update sqlite database with photo_ids')
                self.write_flickr_photo(obj_photo=photo, table='photos')

            # Page exhausted, goto next page
            photo_page += 1
        self.logger.info('Finished updating photos')

    def retrieve_album_photos2(self, album_id):
        photo_list = []
        try:
            query = "SELECT * FROM {} ORDER BY date_taken ASC".format(album_id)
            result = self.sql(query)
            for row in result:
                photo_list.append(row[0])
        except:
            # Return empty list
            photo_list = []

        return photo_list

    def retrieve_album_photos(self, album_id):
        photo_dict = {}
        try:
            query = "SELECT * FROM '{}' ORDER BY date_taken ASC".format(album_id)
            result = self.sql(query)
            for row in result:
                data_dict = {'photo_id': row[0],
                             'photo_title': row[1],
                             'md5': row[2],
                             'sha1': row[3],
                             'public': row[4],
                             'friend': row[5],
                             'family': row[6],
                             'date_taken': row[7]
                             }
                photo_dict[row[0]] = data_dict
        except:
            # Return empty dict
            photo_dict = {}

        return photo_dict
