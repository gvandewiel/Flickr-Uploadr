import os
import re


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
