"""Output dictionary

Dictionary used to store all variables for progress
monitoring in GUI.
"""


class OutDict():
    """Summary

    Attributes:
        out_dict (dict): Dictionary containing all the information
                         used for setting all the variables in the GUI.
        queue (TYPE): queue object
    """

    def __init__(self, queue=None):
        """Summary

        Args:
            queue (None, optional): queue object
        """

        self.queue = queue

        self.dict = {}
        self.dict = {'album': '',
                         'album_id': '',
                         'filename': '',
                         'actual_image': 0,
                         'total_images': 0,
                         'md5': '',
                         'sha1': '',
                         'msg1': '-',
                         'msg2': '-',
                         'total_albums': 0,
                         'actual_album': 0,
                         'upload_progress': 0,
                         'stop': False,
                         'exitFlag': False
                         }

        if queue is not None:
            self.queue.put(self.dict)

    def __call__(self, **kwargs):
        """Add **kwargs to dictionary

        If **kwars does not exist it is created.
        Args:
            **kwargs: key:value pair
        """
        for key, value in kwargs.items():
            self.dict[key] = value

        if self.queue is None:
            # print('out_dict={}'.format(self.out_dict))
            pass
        else:
            self.queue.put(self.dict)

        if self.dict['msg1'] == '':
            self.dict['msg1'] = '-'

        if self.dict['msg2'] == '':
            self.dict['msg2'] = '-'

        if 'exitFlag' not in self.dict:
            self.dict['exitFlag'] = False

        return self

    def clear(self):
        """Clear output dictionary."""
        self.dict = {'album': '',
                         'album_id': '',
                         'filename': '',
                         'actual_image': 0,
                         'total_images': 0,
                         'md5': '',
                         'sha1': '',
                         'msg1': '-',
                         'msg2': '-',
                         'total_albums': 0,
                         'actual_album': 0,
                         'upload_progress': 0,
                         'stop': False,
                         'exitFlag': False
                         }
        return self
