"""Main module.

Detailled explination to follow.
"""

import os
import traceback
import re

import flickrapi
import exifread
import unicodedata

from common import *

from time import sleep
from datetime import datetime

import sqlite3 as sqlite

from photos_to_sqlite import Flickr_To_SQLite
from config import users

import requests


class output_dictionary():
    """Summary

    Attributes:
        out_dict (dict): Description
        queue (TYPE): Description
    """

    def __init__(self, queue=None):
        """Summary

        Args:
            queue (None, optional): Description
        """
        if queue is not None:
            print('FlickrUpload: Recieved queue pointer')
        self.queue = queue
        self.out_dict = {}
        self.out_dict = {'album': '',
                         'album_id': '',
                         'filename': '',
                         'actual_image': 0,
                         'total_images': 0,
                         'md5': '',
                         'sha1': '',
                         'msg1': '',
                         'msg2': '',
                         'total_albums': 0,
                         'actual_album': 0,
                         'upload_progress': 0,
                         'exitFlag': False
                         }

    def add_to_queue(self, **kwargs):
        """Summary

        Args:
            **kwargs: Description
        """
        for key, value in kwargs.items():
            self.out_dict[key] = value

        if self.queue is None:
            print('out_dict={}'.format(self.out_dict))
        else:
            self.queue.put(self.out_dict)

    def clear(self):
        """Clear output dictionary."""
        self.out_dict = {'album': '',
                         'album_id': '',
                         'filename': '',
                         'actual_image': 0,
                         'total_images': 0,
                         'md5': '',
                         'sha1': '',
                         'msg1': '',
                         'msg2': '',
                         'total_albums': 0,
                         'actual_album': 0,
                         'upload_progress': 0,
                         'exitFlag': False
                         }


def normalize(text):
    """Normalize a string to lowercase.

    To used when performing string comparisson
    """
    return unicodedata.normalize("NFKD", text.casefold())


def init(user=None, queue=None):
    """Summary

    Args:
        user (None, optional): Description
        queue (None, optional): Description

    Returns:
        TYPE: Description
    """
    print('FlickrUpload: Starting output_dictionary')
    global q
    q = output_dictionary(queue)

    configuration = {}
    if user in users:
        configuration['api_key'] = users[user]['api_key']
        configuration['api_secret'] = users[user]['api_secret']
    else:
        print('no user ' + user + ' found in dictionary')

    print('FlickrUpload: Starting connection to FlickrAPI')
    global flickr
    flickr = flickrapi.FlickrAPI(configuration['api_key'], configuration['api_secret'])
    flickr.authenticate_via_browser(perms='delete')

    print('FlickrUpload: Starting database connection')
    global con, cur
    con = sqlite.connect(str(user) + '_flickr.sqlite')
    cur = con.cursor()

    print('FlickrUpload: Initate Flickr2SQLite module')
    global db
    db = Flickr_To_SQLite(flickr=flickr,
                          connection=con,
                          cursor=cur,
                          out_dict=q)
    print('\n')
    return q, flickr, con, cur, db


def find_photo(md5, cursor):
    """Summary

    Args:
        md5 (TYPE): Description
        cursor (TYPE): Description

    Returns:
        TYPE: Description
    """
    flp = find_local_photo(md5, cursor)
    if flp is False:
        return find_flickr_photo(md5, cursor)
    else:
        return flp


def find_local_photo(md5, cursor):
    """Summary

    Args:
        md5 (TYPE): Description
        cursor (TYPE): Description

    Returns:
        TYPE: Description
    """
    # Check local databse
    cursor.execute("SELECT id FROM photos WHERE md5=\'" + md5 + "\'")
    id = cursor.fetchone()
    if id is None:
        return False
    else:
        return id[0]


def find_flickr_photo(md5, cursor):
    """Summary

    Args:
        md5 (TYPE): Description
        cursor (TYPE): Description

    Returns:
        TYPE: Description
    """
    global md5_machine_tag_prefix
    # Check flickr database
    photos = flickr.photos_search(
        user_id="me", tags=md5_machine_tag_prefix + md5, extras="date_taken,machine_tags")
    photo_elements = photos.getchildren()[0]

    if len(photo_elements) == 0:
        return False
    else:
        if len(photo_elements) > 1:
            # Mark all photos for removal except first one
            for i, elem in enumerate(photo_elements[1:]):
                print('\tMarking photo with id "{}" for removal'.format(
                    photo_elements[0].attrib['id']))
                result = flickr.photos.addTags(photo_id=elem, tags='ToDelete')

        db.write_photo_to_photo_db(photo_elements[0])
        con.commit
        return photo_elements[0].attrib['id']


def find_album(title, cursor):
    """Summary

    Args:
        title (TYPE): Description
        cursor (TYPE): Description

    Returns:
        TYPE: Description
    """
    fla = find_local_album(title, cursor)
    if fla is False:
        return False
        # return find_flickr_album(title)
    else:
        return fla


def find_local_album(title, cursor):
    """Summary

    Args:
        title (TYPE): Description
        cursor (TYPE): Description

    Returns:
        TYPE: Description
    """
    # Check local databse
    cursor.execute("SELECT id FROM albums WHERE Title =\'" + title + "\'")
    id = cursor.fetchone()
    if id is None:
        return False
    else:
        return id[0]


def find_flickr_album(title):
    """Summary

    Args:
        title (TYPE): Description

    Returns:
        TYPE: Description
    """
    # seems impossible
    db.list_albums()
    return find_local_album(title)


def retrieve_ids_from_album(id, cursor):
    """Summary

    Args:
        id (TYPE): Description
        cursor (TYPE): Description

    Returns:
        TYPE: Description
    """
    try:
        result = cursor.execute("SELECT Id FROM \'" + str(album_id) + "\'")
        photo_list = []
        for row in result:
            photo_list.append(row[0])
    except:
        # Return empty list
        photo_list = []

    return photo_list


def add_to_album(item, datetaken, photo_list):
    """Summary

    Args:
        item (TYPE): Description
        photo_list (TYPE): Description

    Returns:
        TYPE: Description
    """
    # Make set of photos
    photos = set(photo_list)
    # Search set for existing id;
    # add item to list if not found (preventing duplicates)
    if item not in photos:
        photos.add((item, datetaken))
    return list(photos)


def sort_album_photos(album_id):
    """Summary

    Args:
        album_id (TYPE): Description
    """
    global cur
    cur.execute("SELECT id FROM \'" + str(album_id) + "\' ORDER BY date_taken ASC")
    id_list = cur.fetchall()

    sorted_id = list()
    for item in id_list:
        sorted_id.append(item[0])

    sorted_ids = ','.join([str(x) for x in sorted_id])
    flickr.photosets.reorderPhotos(photoset_id=str(album_id), photo_ids=str(sorted_ids))


def sort_albums(sort_photos=False):
    """Summary

    Args:
        sort_photos (bool, optional): Description
    """
    albums = dict()
    sorted_id = list()

    # Counter of set pages
    spage = 0
    # counter of processed albums
    s_cnt = 0
    # Retrieve total number of albums in Flickr database
    total_albums = int(flickr.photosets_getList(per_page="1", page="1").getchildren()[0].attrib['total'])
    print('Total number of albums: {}'.format(total_albums))
    while s_cnt < total_albums:
        spage += 1
        sets = flickr.photosets_getList(per_page="500", page=str(spage))
        set_elements = sets.getchildren()[0]
        for s in set_elements:
            s_cnt += 1
            print('{} - Setname {}'.format(s_cnt, s.getchildren()[0].text))
            albums[s.getchildren()[0].text] = s.attrib['id']

    print('Sorting albums')
    for key in sorted(albums, reverse=True):
        print("{}:{}".format(key, albums[key]))
        sorted_id.append(albums[key])

        # Sort album photos
        if sort_photos is True:
            print('\tReorder album photos for {}'.format(key))
            sort_album_photos(albums[key])

    sorted_ids = ','.join([str(x) for x in sorted_id])

    print('Reorder albums')
    flickr.photosets.orderSets(photoset_ids=sorted_ids)
    print('Finished reording photos')


###############################################################################

def PostedToTaken(user=None, queue=None):
    """Summary

    Args:
        user (None, optional): Description
        queue (None, optional): Description
    """
    q, flickr, con, cur, db = init(user=user, queue=queue)
    all_photos = []

    print('-----> Fetching all photos')

    total_pages = 1
    page = 1
    while page <= total_pages:
        print('       Fetching page {} out of {}'.format(page, total_pages))
        res = json.loads(flickr.photos_search(user_id='me', page=page,
                                              per_page=500, extras='date_upload,date_taken')[14:-1])
        total_pages = res['photos']['pages']
        page = res['photos']['page'] + 1
        photos = res['photos']['photo']
        all_photos.extend(photos)

    print('-----> Updating dates')

    for photo in all_photos:
        date_taken = photo['datetaken']
        date_taken = datetime.strptime(date_taken, '%Y-%m-%d %H:%M:%S')
        date_posted = int(photo['dateupload'])
        date_posted = datetime.fromtimestamp(date_posted)
        if date_posted != date_taken:
            print('       Updating "{}": change date posted from {} to {}'.format(
                photo['id'], date_posted, date_taken))
            new_date_posted = datetime.strftime(date_taken, '%s')
            flickr.photos_setDates(photo_id=photo['id'], date_posted=new_date_posted)
        else:
            print('       Skipping "{}": dates match'.format(photo['id']))

    print('-----> Done!')


def Order_Photos_Albums(user=None, queue=None, sort_photos=False):
    """Summary

    Args:
        user (None, optional): Description
        queue (None, optional): Description
        sort_photos (bool, optional): Description
    """
    q, flickr, con, cur, db = init(user=user, queue=queue)

    q.add_to_queue(msg1='Sorting albums')
    sort_albums(sort_photos=sort_photos)

###############################################################################


class FileWithCallback(object):
    """Summary

    Attributes:
        callback (TYPE): Description
        file (TYPE): Description
        fileno (TYPE): Description
        len (TYPE): Description
        tell (TYPE): Description
    """

    def __init__(self, filename, callback):
        """Summary

        Args:
            filename (TYPE): Description
            callback (TYPE): Description
        """
        self.file = open(filename, 'rb')
        self.callback = callback
        # the following attributes and methods are required
        self.len = os.path.getsize(filename)
        self.fileno = self.file.fileno
        self.tell = self.file.tell

    def read(self, size):
        """Summary

        Args:
            size (TYPE): Description

        Returns:
            TYPE: Description
        """
        if self.callback:
            self.callback(self.tell() * 100 // self.len)
        return self.file.read(size)

    def __del__(self):
        """Destructor.

        Close the opened file in __init__
        """
        self.file.close()
        self.file = None


def callback(progress):
    """Summary

    Args:
        progress (TYPE): Description
    """
    global q
    q.add_to_queue(upload_progress=progress)

    if progress != 100:
        print('\tuploading photo {}\r'.format(progress), end="")
    else:
        print('\tuploading photo {}\r'.format(progress))


def upload_file(flickr, fname, file, tags, public, family, friends, queue, photo_ext, video_ext):
    """Check filesize before starting upload.

    Max filesize for pictures = 200 MB
    Max filesize for videos   =   1 GB
    """
    photo_id = True

    b = os.path.getsize(fname)
    print('\tfilesize = ~{:.2f} MB'.format(b // 1000000))

    if normalize(file.rsplit(".", 1)[-1]) in photo_ext and b >= 209715200:
        print('\t\tFilesize of photo exceeds Flickr limit (200 MB)')
        queue.add_to_queue(msg1='Upload failed.',
                           msg2='Filesize of photo exceeds Flickr limit (200 MB)'
                           )
        photo_id = False

    if normalize(file.rsplit(".", 1)[-1]) in video_ext and b >= 1073741824:
        print('\t\tFilesize of video exceeds Flickr limit (1 GB)')
        queue.add_to_queue(msg1='Upload failed.',
                           msg2='Filesize of video exceeds Flickr limit (1 GB)'
                           )
        photo_id = False

    if photo_id is True:
        fileobj = FileWithCallback(fname, callback)
        result = flickr.upload(filename=fname,
                               fileobj=fileobj,
                               title=file,
                               tags=tags,
                               is_public=int(public),
                               is_family=int(family),
                               is_friend=int(friends))

        photo_id = result.getchildren()[0].text
        fileobj = None
        result = None
    return photo_id


@profile
def start_upload(main_dir='', user=None, public=False, family=False, friends=False, update=False, queue=None):
    """Summary.

    Args:
        main_dir (str, optional): Description
        user (None, optional): Description
        public (bool, optional): Description
        family (bool, optional): Description
        friends (bool, optional): Description
        update (bool, optional): Description
        queue (None, optional): Description
    """
    # Initiate flickr instance
    q, flickr, con, cur, db = init(user=user, queue=queue)

    # Set exitFlag to False
    q.add_to_queue(exitFlag=False)

    """Check input
    If no main_dir is provided only on update of the users database
    is possible. If update parameter is False (or empty) the function
    will exit without any action. If update is True the databse will
    be updated and the function will exit."""
    if main_dir == '':
        if update is False:
            exit()
            q.add_to_queue(exitFlag=True)
        elif update is True:
            q.add_to_queue(msg1='Make local copy of Flickr database')
            db.update_sqlite()
            q.clear()
            q.add_to_queue(exitFlag=True)
            exit()

    """main_dir is provided.
    A check is made if the update parameter is True. And an update of the
    user database is made prior to any upload / update actions."""
    try:
        if update:
            q.add_to_queue(msg1='Make local copy of Flickr database')
            db.update_sqlite()

        # Start the upload process
        q.add_to_queue(msg1='Start upload of main_dir = ' + main_dir)

        # Determine the number of folders in main_dir
        mmax = len(list(os.walk(main_dir)))
        q.add_to_queue(total_albums=mmax)

        # Set the number of processed folders
        mcnt = 0

        # Start of dirloop
        for dirname, subdirlist, fileList in os.walk(main_dir, topdown=False):
            #FileEXT = '.*\.gif|.*\.png|.*\.jpg|.*\.jpeg|.*\.tif|.*\.tiff|.*\.mov|.*\.avi|.*\.mp4'
            photo_ext = '.*\.gif|.*\.png|.*\.jpg|.*\.jpeg|.*\.tif|.*\.tiff'
            video_ext = '.*\.mov|.*\.avi|.*\.mp4'
            mcnt += 1
            q.add_to_queue(album=os.path.basename(dirname),
                           total_albums=mmax,
                           actual_album=mcnt
                           )

            # Count images in folder (check if empty)
            photo_list = []
            img_cnt = len([name for name in fileList if not name.startswith(".") and (re.match(photo_ext, normalize(name)) or re.match(video_ext, normalize(name)))])

            # Check if the folder is NOT hidden and contains image files
            if (not re.match('^\.', os.path.basename(dirname)) and
                    not os.path.basename(dirname).upper() == 'RAW' and
                    not os.path.basename(dirname).upper() == 'REJECTS' and
                    img_cnt > 0):
                # Determine the title of the folder
                if os.path.basename(dirname) == '':
                    title = os.path.basename(os.path.normpath(dirname))
                else:
                    title = os.path.basename(dirname)

                # Message in CLI to show which folder is being processed
                print('\n\033[1m\033[92mProcessing: \033[0m{} ({} files)'.format(title, img_cnt))
                q.add_to_queue(total_images=img_cnt)

                # Find album id (if any)
                album_id = find_album(title, cur)

                # Retrieve photo_id's from the local database
                if album_id is not False:
                    photo_list = retrieve_ids_from_album(id, cur)
                    q.add_to_queue(album=title,
                                   total_images=img_cnt,
                                   album_id=album_id
                                   )

                # Loop over all files in directory
                pcnt = 0
                for file in fileList:
                    # Exclude hidden files and only upload image and video files
                    if not file.startswith(".") and (normalize(file.rsplit(".", 1)[-1]) in photo_ext or normalize(file.rsplit(".", 1)[-1]) in video_ext):
                        # Set full path of image file
                        fname = os.path.join(dirname, file)
                        real_sha1 = sha1sum(fname)
                        real_md5 = md5sum(fname)
                        tags = md5_machine_tag_prefix + \
                            str(real_md5) + ' ' + sha1_machine_tag_prefix + str(real_sha1)

                        pcnt += 1

                        print('\tProcessing {} of {}\r'.format(pcnt, img_cnt), end="")
                        q.add_to_queue(actual_image=pcnt,
                                       filename=file,
                                       md5=real_md5,
                                       sha1=real_sha1
                                       )

                        # Check local and remote databse for photo
                        photo_id = find_photo(real_md5, cur)

                        # Open image file for reading (binary mode)
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

                        if photo_id is False:
                            q.add_to_queue(msg1='Nothing found in local or remote database',
                                           msg2='Uploading photo...'
                                           )

                            # Start upload of new photo
                            while True:
                                try:
                                    print('\tTrying to upload ' + file + ' to Flickr...')
                                    photo_id = upload_file(flickr, fname, file, tags, public, family, friends, q, photo_ext, video_ext)

                                except requests.exceptions.Timeout:
                                    q.add_to_queue(msg1='Timeout occurd during upload',
                                                   msg2='Sleeping for 60 seconds...'
                                                   )
                                    print('\tTimeout occurd during upload')
                                    print('\tSleeping for 60 seconds...')
                                    sleep(60)
                                    continue
                                break

                            if photo_id is not False:
                                print('\tPhoto uploaded to Flickr with id: {}'.format(photo_id))
                                q.add_to_queue(msg1='Photo uploaded to Flickr',
                                               msg2='')

                                # Add photo to local database
                                cur.execute("INSERT INTO photos VALUES (?,?,?,?,?,?,?,?)", (photo_id, fname, real_md5, real_sha1, int(public), int(friends), int(family), datetaken))
                                con.commit()

                                photo_list = add_to_album(photo_id, datetaken, photo_list)
                        else:
                            # Photo already uploaded
                            cur.execute("SELECT public,friend,family FROM photos WHERE id=\'" + str(photo_id) + "\'")
                            db_public, db_friend, db_family = cur.fetchone()

                            photo_list = add_to_album(photo_id, datetaken, photo_list)
                    else:
                        print('\t\033[93m\033[1mSkipped file: \033[0m{}'.format(file))
                #### End of file loop ####

                # Create or update album
                if album_id is False:
                    primary_photo_id = photo_list[0][0]
                    album_id = flickr.photosets.create(title=title,
                                                       description="",
                                                       primary_photo_id=primary_photo_id).getchildren()[0].attrib['id']

                    print('\tCreating album "{}"'.format(title))
                    q.add_to_queue(msg1='Creating new album',
                                   msg2='',
                                   album=title,
                                   total_images=img_cnt,
                                   actual_image=pcnt,
                                   album_id=album_id,
                                   filename='',
                                   md5='',
                                   sha1=''
                                   )

                    print('\tCreating table "{}" with all photo_id\'s'.format(album_id))
                    cur.execute("DROP TABLE IF EXISTS \'" + str(album_id) + "\'")
                    cur.execute("CREATE TABLE \'" + str(album_id) + "\' (Id INT, date_taken TEXT)")

                    data = [(photo,) for photo in photo_list]
                    cur.executemany("INSERT INTO \'" + str(album_id) + "\' (Id, date_taken) VALUES (?, ?)", photo_list)

                    # Add album to local db albums
                    print('\tAdd "{}" to albums table'.format(album_id))
                    cur.execute("INSERT INTO albums VALUES (?,?,?,?)",
                                (album_id, title, len(photo_list), 0))

                    con.commit()

                # Update flickr photoset to show all photos.
                # Catching error when the album exists in the local DB but not on Flickr.
                while True:
                    try:
                        print('\tUpdating album with id: "{}"'.format(album_id))
                        q.add_to_queue(msg1='Updating album',
                                       msg2='',
                                       album=title,
                                       total_images=img_cnt,
                                       actual_image=pcnt,
                                       album_id=album_id,
                                       filename='',
                                       md5='',
                                       sha1=''
                                       )

                        print('\t\tAdd photos to album at Flickr')
                        primary_photo_id = photo_list[0][0]
                        sdl = ','.join([str(x[0]) for x in photo_list])
                        flickr.photosets.editPhotos(photoset_id=str(album_id), primary_photo_id=primary_photo_id, photo_ids=str(sdl))
                        break

                    except:
                        # Albums seems not to exist on flickr create and update again.
                        print('\t\tAlbums seems not to exist on flickr create and update again.')
                        primary_photo_id = photo_list[0][0]
                        album_id = flickr.photosets.create(title=title,
                                                           description="",
                                                           primary_photo_id=primary_photo_id).getchildren()[0].attrib['id']

                        print('\t\tCreating new album')
                        q.add_to_queue(msg1='Creating new album',
                                       msg2='Albums seems not to exist on Flickr, create and update again.',
                                       album=title,
                                       total_images=img_cnt,
                                       actual_image=pcnt,
                                       album_id=album_id,
                                       filename='',
                                       md5='',
                                       sha1=''
                                       )

                        print('\t\tCreating table "{}" with all photo_id\'s'.format(album_id))
                        cur.execute("DROP TABLE IF EXISTS \'" + str(album_id) + "\'")
                        cur.execute("CREATE TABLE \'" + str(album_id) + "\' (Id INT, date_taken TEXT)")

                        data = [(photo,) for photo in photo_list]
                        cur.executemany("INSERT INTO \'" + str(album_id) + "\' (Id, date_taken) VALUES (?, ?)", photo_list)
                        # cur.executemany("INSERT INTO \'" + str(album_id) + "\' VALUES (?, ?)", data)

                        # Add album to local db albums
                        print('\t\tAdd "{}" albums table'.format(album_id))
                        cur.execute("INSERT INTO albums VALUES (?,?,?,?)",
                                    (album_id, title, len(photo_list), 0))

                        con.commit()
                        # Retrun to top of while loop and try to update albums with all photo's

                print('\t\tReorder album photos on date-taken')
                q.add_to_queue(msg1='Reorder album photos on date-taken',
                               msg2='',
                               album=title,
                               total_images=img_cnt,
                               actual_image=pcnt,
                               album_id=album_id,
                               filename='',
                               md5='',
                               sha1=''
                               )
                sort_album_photos(album_id)
                q.clear()
            else:
                print('\n\033[91m\033[1mSkipped folder: \033[0m {}'.format(os.path.basename(dirname)))
        #### End of dir loop ####
        print('Sorting all albums')
        q.add_to_queue(msg1='Sorting all albums')
        sort_albums()

    except:
        q.clear()
        q.add_to_queue(exitFlag=True)
        q.add_to_queue(msg1='An error occured')

        print('TRACEBACK')
        traceback.print_exc()
    finally:
        q.add_to_queue(exitFlag=True)
