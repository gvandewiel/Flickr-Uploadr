class Photos(flickr):
    def __init__(self, flickr):
        self.flickr = flickr
        
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
