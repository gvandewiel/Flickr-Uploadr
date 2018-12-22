import os
import re
from . import common

class Parser(object):
    def __init__(self, obj):
        self.flickrcore = obj
        self.logger = common.create_logger('FlickrParser')
        self.logger.info('Starting FlickrParser')
        self.progress(msg1='Starting FlickrParser')

    def __getattr__(self, attr):
        return getattr(self.flickrcore, attr)

    def __call__(self, main_dir='', subdir='', public=False, family=False, friends=False, update=False):
        """Check input
        If no main_dir is provided only on update of the users database
        is possible. If update parameter is False (or empty) the function
        will exit without any action. If update is True the databse will
        be updated and the function will exit."""

        self.public = public
        self.family = family
        self.friends = friends

        if not main_dir and not update:
            self.logger.warning('No directory or update parameter passed.\nExiting...')
            self.progress(exitFlag=True)

        elif update:
            self.logger.info('Make local copy of Flickr database')
            self.progress(msg1='Make local copy of Flickr database')

            # Rebuild database
            self.db.rebuild_database()

            # Clear out_dict
            self.progress.clear()

            if not main_dir:
                # Tell GUI update is finished
                self.progress(exitFlag=True)
            else:
                self.__proc_dir__(main_dir=main_dir, subdir=subdir, public=public, family=family, friends=friends, update=update)
        elif main_dir and not update:
            self.__proc_dir__(main_dir=main_dir, subdir=subdir, public=public, family=family, friends=friends, update=update)


    def __check_datetaken__(self, fname=''):
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

    def __check_folder__(self, dirname='', filelist=''):
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
            self.progress(total_images=img_cnt)

            # # print out excluded files
            for file in filelist:
                if file.startswith(".") or \
                    (common.normalize(file.rsplit(".", 1)[-1]) not in self.photo_ext and
                     common.normalize(file.rsplit(".", 1)[-1]) not in self.video_ext):
                    self.logger.debug('Skipped file: {}'.format(file))
                    pass

            # Find album id (if any)
            album_id = self.albums.find_album(album_title)

            # Retrieve photo_id's from the local database
            if album_id is not False:
                photo_dict = self.db.retrieve_album_photos(album_id)

                self.progress(album=album_title,
                              total_images=img_cnt,
                              album_id=album_id)
            else:
                photo_dict = {}

            return (album_title, album_id, photo_dict, img_list)

    def __clean_locals__(self, photo=False, album=False):
        if photo:
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
        if album:
            if 'album_id' in locals():
                del album_id
            if 'album_title' in locals():
                del album_title
            if 'photo_dict' in locals():
                del photo_dict
            if 'filtered_file_list' in locals():
                del filtered_file_list

    def __proc_dir__(self, main_dir='', subdir='', public=False, family=False, friends=False, update=False):
        # Start the upload process
        if subdir:
            main_dir = os.path.join(main_dir, subdir, '')

        self.logger.info('Start upload of main_dir = {}'.format(main_dir))
        self.progress(msg1='Start upload of main_dir =',
                      msg2=main_dir)

        # Determine the number of folders in main_dir
        self.total_folders = len(list(os.walk(main_dir)))
        self.progress(total_albums = self.total_folders)

        # Set the number of processed folders
        self.folder_count = 0

        # Start of dirloop
        for dirname, subdirlist, filelist in os.walk(main_dir, topdown=True):
            subdirlist[:] = [d for d in subdirlist if d not in self.exclude_folders]
            self.folder_count += 1

            # Process subdir "dirname" and corresponding files "filelist"
            self.__proc_subdir__(dirname, filelist)

            self.logger.debug(self.progress.dict)

            # Check for an exifFlag to exit the dir loop
            if self.progress.dict['stop'] is True:
                print('')
                self.logger.warning('ExitFlag recieved')
                self.logger.warning('Breaking out file loop')
                self.progress(msg1='ExitFlag recieved',
                              msg2='Breaking out file loop...')
                break
            else:
                # Clear output dict
                self.progress.clear()

        self.logger.info('Finished processing all local folders')
        self.progress(msg1='Finished processing all local folders')

        self.progress(msg2='Sorting albums')
        self.albums.sort()

        self.logger.info('Finished sorting albums.')
        self.progress(msg2='Finished sorting albums.')

        self.progress.clear()
        self.progress(exitFlag=True)

    def __proc_subdir__(self, dirname, filelist):
            # Check if folder needs processing
            folder_check = self.__check_folder__(dirname=dirname, filelist=filelist)

            if folder_check:
                album_title, album_id, photo_dict, filtered_file_list = folder_check

                self.progress(album=os.path.basename(dirname),
                              total_albums=self.total_folders,
                              actual_album=self.folder_count)

                # Loop over filtered filelist
                photo_dict = self.__photos__(dirname, photo_dict, filtered_file_list)

                # Album management
                self.__album__(album_id, album_title, photo_dict)

    def __photos__(self, dirname, photo_dict, filtered_file_list):

        total_images = len(filtered_file_list)
        photo_count = 0

        for file in filtered_file_list:
            photo_count += 1

            # Set full path of image file
            fname = os.path.join(dirname, file)

            self.logger.debug('Checking file: {}'.format(file))

            # Calculate checksum of file
            real_md5 = common.md5sum(fname)
            real_sha1 = common.sha1sum(fname)

            self.logger.debug('Processing {} of {}'.format(photo_count, total_images))

            self.progress(actual_image=photo_count,
                          total_images=total_images,
                          filename=file,
                          md5=real_md5,
                          sha1=real_sha1)

            # Check local and remote databse for photo
            photo_id, photo = self.photos.find(real_md5)
            datetaken = self.__check_datetaken__(fname)

            '##### Photo management #####'
            # Photo not uploaded
            if photo_id is False:
                self.logger.info('Nothing found in local or remote database')
                self.progress(msg1='Nothing found in local or remote database',
                              msg2='Uploading photo...')

                # Start upload of new photo
                if not self.dry_run:
                    photo_id, photo = self.uploader(fname, file, real_md5, real_sha1, self.public, self.family, self.friends)

                # If photo is correctly uploaded a photo_id is provided by Flickr
                if photo_id is not False:
                    self.logger.info('Photo uploaded to Flickr with id: {}'.format(photo_id))
                    self.progress(msg1='Photo uploaded to Flickr',
                                  msg2='')

                    # Add newly uploaded photo to photolist
                    self.logger.debug('Adding photo to dict after upload')
                    self.logger.debug(self.photos.to_dict(photo), photo_dict)
                    photo_dict = self.photos.to_album(self.photos.to_dict(photo), photo_dict)

            # Photo already uploaded
            elif photo_id is not False:
                if type(photo) is dict:
                    photo_dict = self.photos.to_album(photo, photo_dict)
                else:
                    photo_dict = self.photos.to_album(self.photos.to_dict(photo), photo_dict)

            # Delete all photo variables
            self.__clean_locals__(photo=True)

            'Check for an exifFlag to exit the file loop'
            if self.progress.dict['stop'] is True:
                print('')
                self.logger.warning('ExitFlag recieved')
                self.logger.warning('Breaking out file loop')

                self.progress(msg1='ExitFlag recieved',
                              msg2='Breaking out file loop...')
                break
        # End of file loop

        return photo_dict

    def __album__(self, album_id, album_title, photo_dict):
        # Create album
        if album_id is False:
            self.progress(msg1='Creating new album')
            album_id = self.albums.create(album_title=album_title, photo_dict=photo_dict)

        # Update album
        self.progress(msg1='Updating album')
        self.albums.update(album_id=album_id, album_title=album_title, photo_dict=photo_dict)

        # Delete all album variables
        self.__clean_locals__(album=True)
