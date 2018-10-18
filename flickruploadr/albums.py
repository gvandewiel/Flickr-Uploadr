class Albums():
    def __init__(self, obj):
        self.flickrcore = obj
        
    def __getattr__(self, attr):
        return getattr(self.flickrcore, attr)
        
    def find_album(self, album_title):
        # Search for album_title in local database
        album_id = self.find_local_album(album_title)
        if album_id is False:
            # Album is not found in local database
            # Update local database and try again
            album_id = self.find_flickr_album(album_title)
            if album_id is False:
                self.logger.info('Album "{}" not found in updated database'.format(album_title))
                self.progress = self.out_dict(msg1='Album not found in updated database')
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
            self.progress = self.out_dict(msg1='Updating album database')
            self.db.list_albums(update=False, verbose=False)
            self.album_up2date = True
        return self.find_local_album(album_title)
        
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
        self.progress = self.out_dict(total_albums=total_albums)

        # number of processed sets
        set_cnt = 0
        self.progress = self.out_dict(actual_albums=set_cnt)

        self.progress = self.out_dict(msg1='Sorting {} albums'.format(total_albums))
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
                self.progress = self.out_dict(album_title=set.getchildren()[0].text, actual_albums=set_cnt)
                self.logger.debug('{} - Setname {}'.format(set_cnt, set.getchildren()[0].text))
                albums[set.getchildren()[0].text] = set.attrib['id']

            # Page exhausted
            set_page += 1

        self.logger.info('Sorting albums')
        self.progress = self.out_dict(msg1='Sorting albums')

        for key in sorted(albums, reverse=True):
            # print("{}:{}".format(key, albums[key]))
            sorted_id.append(albums[key])

            # Sort album photos
            if sort_photos is True:
                self.logger.info('Reorder album photos for "{}"'.format(key))
                self.progress = self.out_dict(msg2='Reorder album photos for "{}"'.format(key))
                self.sort_album_photos(albums[key])

        sorted_ids = ','.join([str(x) for x in sorted_id])

        self.logger.info('Reorder albums')
        self.flickr.photosets.orderSets(photoset_ids=sorted_ids)
        self.logger.debug('Finished reording photos')
        
    def create_album(self, album_title, photo_dict):
        self.logger.info('Creating album "{}"'.format(album_title))
        self.progress = self.out_dict(msg1='Creating new album')

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
        self.progress = self.out_dict(msg2='Creating database table "{}"'.format(album_id))
        self.db.create_album_table(album_id)
        return album_id

    def update_album(self, album_id, album_title, photo_dict):
        self.logger.info('Updating album "{}" ({}) with {} items.'.format(album_title, album_id, len(photo_dict)))
        self.progress = self.out_dict(msg1='Updating album "{}" ({})'.format(album_title, album_id),
                                      msg2='with {} items'.format(len(photo_dict)))

        self.logger.debug('Loop over photos; add to db')
        for photo_id, photo in photo_dict.items():
            self.db.write_flickr_photo(dict_photo=photo, table=album_id)

        self.logger.info('Add photos to album at Flickr')
        self.progress = self.out_dict(msg2='Add photos to album at Flickr')

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
