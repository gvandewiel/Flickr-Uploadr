from time import sleep

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

class Uploader(object):
    """Uploader class for FlickrCore
    """
    def __init__(self, obj):
        self.flickrcore = obj
        
    def __getattr__(self, attr):
        return getattr(self.flickrcore, attr)
        
    def get_progress(self):
        d = self.queue.get()
        return d

    def callback(self, progress):
        print('\rUploading: {:3}%'.format(progress))
        self.progress = self.out_dict(upload_progress=progress)

    def _check_size(self,fname, file):
        b = os.path.getsize(fname)
        self.logger.debug('filesize = ~{:.2f} MB'.format(b // 1000000))

        if common.normalize(file.rsplit(".", 1)[-1]) in self.photo_ext and b >= 209715200:
            self.logger.warning('Upload of "{}" failed'.format(file))
            self.logger.warning('Filesize of photo exceeds Flickr limit (200 MB)')

            self.progress = self.out_dict(msg1='Upload failed.',
                                                       msg2='Filesize of photo exceeds Flickr limit (200 MB)')
            return False

        if common.normalize(file.rsplit(".", 1)[-1]) in self.video_ext and b >= 1073741824:
            self.logger.warning('Upload of "{}" failed'.format(file))
            self.logger.warning('Filesize of video exceeds Flickr limit (1 GB)')

            self.progress = self.out_dict(msg1='Upload failed.',
                                                       msg2='Filesize of video exceeds Flickr limit (1 GB)')
            return False
        return True

    def __call__(self, fname, file, real_md5, real_sha1, public, family, friends):
        """Check filesize before starting upload.

        Max filesize for pictures = 200 MB
        Max filesize for videos   =   1 GB
        """

                            # Generate machine tags
        tags = '{md5_prefix}{md5} {sha1_prefix}{sha1}'.format(md5_prefix=common.MD5_MACHINE_TAG_PREFIX,
                                                              sha1_prefix=common.SHA1_MACHINE_TAG_PREFIX,
                                                              md5=real_md5,
                                                              sha1=real_sha1)

        retry = False
        while True:
            try:
                self.logger.debug('Trying to upload "{}" to Flickr'.format(file))
                self.logger.debug(' MD5 = {}'.format(real_md5))
                self.logger.debug('SHA1 = {}'.format(real_sha1))

                if self._check_size(fname, file):
                    self.logger.info('Uploading "{}"'.format(file))
                    self.progress = self.out_dict(msg1='Uploading {}'.format(file))

                    fileobj = common.FileWithCallback(fname, self.callback)

                    self.flickr.upload(filename=fname,
                                       fileobj=fileobj,
                                       title=file,
                                       tags=tags,
                                       is_public=int(public),
                                       is_family=int(family),
                                       is_friend=int(friends))

                    self.logger.debug('Waiting for Flickr response')
                    self.progress = self.out_dict(msg2='Waiting for Flickr response...')

                    md5 = tags.split(' ')[0]
                    wcnt = 0

                    # Wait until flickr has processed file
                    while True:
                        wcnt += 1
                        ret = self.photos.find_flickr_photo(md5=md5)
                        self.logger.debug('Waiting for Flickr response ({}s)'.format(wcnt))

                        self.progress = self.out_dict(msg2='Waiting for Flickr response ({}s)'.format(wcnt))
                        if ret[0] is not False:
                            photo_id = ret[0]
                            photo = ret[1]
                            break
                        sleep(1)

                return photo_id, photo

                self.logger.debug('photo_id = {}'.format(photo_id))
                self.logger.debug('photo = {}'.format(photo))

            except flickrapi.exceptions.FlickrError as e:
                if e == 'Error: 5: Filetype was not recognised' and retry is False:
                    self.progress = self.out_dict(msg2='Retry upload of {}'.format(file))
                    self.logger.info('Retry upload of "{}"'.format(file))
                    retry = True
                    continue

                elif e == 'Error: 5: Filetype was not recognised' and retry is True:
                    self.logger.info('Already retried upload of "{}"'.format(file))
                    self.logger.info('Skipped upload of "{}"'.format(file))
                    self.progress = self.out_dict(msg2='Already retried upload of {}'.format(file))
                    # exit while True loop
                    break
            # exit while True loop
            break
