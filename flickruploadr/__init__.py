# Semi-standard module versioning.
__version__ = '2.0.2'

from uploader import FlickrCore

import configparser
import toga
import os
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from toga.sources import Source
from pprint import pprint
import asyncio

class Movie:
    # A class to wrap individual
    def __init__(self, path):
        self.subfolder = path


class Decade:
    # A class to wrap
    def __init__(self, decade):
        self.subfolder = decade
        self._data = []

    # Display values for the decade in the tree.
    @property
    def year(self):
        return "{}0's".format(self.subfolder)

    # Methods required for the data source interface
    def __len__(self):
        return len(self._data)

    def __getitem__(self, index):
        return self._data[index]

    def can_have_children(self):
        return True


class DecadeSource(Source):
    def __init__(self):
        super().__init__()
        self._decades = []

    def __len__(self):
        return len(self._decades)

    def __getitem__(self, index):
        return self._decades[index]

    def create_tree(self, path):
        for root, dirs, files in os.walk(path, topdown=True):
            self.add(root, sorted(dirs))
            break

    def add(self, rootdir, dirs):
        decade = rootdir
        for entry in dirs:
            try:
                decade_root = {
                    root.subfolder: root
                    for root in self._decades
                }[decade]
            except KeyError:
                decade_root = Decade(decade)
                self._decades.append(decade_root)
                self._decades.sort(key=lambda v: v.subfolder)
            movie = Movie(entry)
            decade_root._data.append(movie)
            self._notify('insert', parent=decade_root, index=len(decade_root._data) - 1, item=movie)
            #self.create_tree(os.path.join(rootdir,entry))


class UploaderGui(toga.App):
    def startup(self):
        """
        Construct and show the Toga application.
        """

        self.username = ''
        self.main_dir = ''
        self.subdir = ''
        self.public = False
        self.family = False
        self.friends = False
        self.update = True
        self.action = ''


        elem_style = Pack(padding=10, flex=1)

        # Backup settings
        self.main_window = toga.MainWindow(title=self.name)

        config = self.get_user()
        config.insert(0, '')
        self.user = toga.Selection(items=config, on_select=self.user_select, style=elem_style)
        self.rootdir = toga.Label(text='Rootdir', style=elem_style)
        self.dirtree = toga.Tree(['Subfolder'], style=Pack(padding=10, flex=1, height=350), data=DecadeSource(), on_select=self.tree_handler)
        self.action = toga.Selection(items=["Upload new photos to Flickr", "Only update database"],
                                     on_select=self.action_select, style=elem_style)
        
        self.top_row = toga.Box(
            children=[
                self.user,
                self.rootdir,
                self.dirtree
            ],
            style=Pack(
                flex=1,
                direction=COLUMN,
                padding=0
            )
        )

        self.subdir = toga.Label(text='Subdir (optional)', style=elem_style)

        switch_style = Pack(flex=1, padding=5)
        # Update database before upload?
        self.update = toga.Switch('Update database before upload?', is_on=True, enabled=True, on_toggle=self.toggle_update, style=switch_style)
        
        # Uploaded photos are public?
        self.public = toga.Switch('Uploaded photos are public?', is_on=False, enabled=True, on_toggle=self.toggle_public, style=switch_style)
        
        # Uploaded photos are visible for friends?
        self.friends = toga.Switch('Uploaded photos are visible for friends?', is_on=False, enabled=True, on_toggle=self.toggle_family, style=switch_style)
        
        # Uploaded photos are visible for family?
        self.family = toga.Switch('Uploaded photos are visible for family?', is_on=False, enabled=True, on_toggle=self.toggle_friends, style=switch_style)

        self.options = toga.Box(
            children=[
                self.update,
                self.public,
                self.friends,
                self.family
            ],
            style=Pack(
                flex=1,
                direction=COLUMN,
                padding=0
            )
        )

        # Album progressbar
        self.apb_label = toga.Label('Album progress')
        self.apb = toga.ProgressBar(max=100)

        # Photos progressbar
        self.ppb_label = toga.Label('Photos progress')
        self.ppb = toga.ProgressBar(max=100)

        self.apb_box = toga.Box(
            children = [self.apb_label, self.apb],
            style = Pack(flex=1, direction=COLUMN, padding=10)
        )

        self.ppb_box = toga.Box(
            children = [self.ppb_label, self.ppb],
            style = Pack(flex=1, direction=COLUMN, padding=10)
        )

        # Progressbars
        self.pbs = toga.Box(
            children=[
                self.apb_box,
                self.ppb_box
                ],
            style=Pack(
                flex=1,
                direction=COLUMN,
                padding=10
            )
        )
        
        btn_style = Pack(flex=1)
        self.btn_start = toga.Button('Start', on_press=self.start, style=btn_style)

        self.right_box = toga.Box(
            children = [
                self.action,
                self.subdir,
                self.options,
                self.pbs,
                self.btn_start
            ],
            style=Pack(
                flex = 1,
                direction = COLUMN,
                padding=0
            )
        )

        # Main box
        self.main_box = toga.Box(
            children=[
                self.top_row,
                self.right_box
            ],
            style=Pack(
                flex=1,
                direction = ROW,
                padding=10
            )
        )

        '''
        # Main box
        self.main_box = toga.Box(
            children=[
                self.top_row,
                self.options,
                self.pbs
            ],
            style=Pack(
                flex=1,
                direction=COLUMN,
                padding=10
            )
        )
        '''
        
        self.main_window.content = self.main_box
        self.main_window.size = (350,500)
        self.main_window.show()

    def get_user(self, username=""):
        """Retrieve Flickr User from config file

        If no username is provided a list of sections from the config file are returned.
        Otherwise the corresponding data for the particular user are provided.

        Args:
            username (string; optional)

        Returns:
            configuration (dict)
        """
        config = configparser.ConfigParser()
        try:
            config.read(os.path.join(os.path.expanduser("~"), 'flickr', 'config.ini'))
        except:
            raise IOError('"{}" file not found.'.format(os.path.join(os.path.expanduser("~"), 'flickr', 'config.ini')))

        if len(config.sections()) is 0:
            raise ValueError('No configuration provided in file')
        configuration = {}
        if username == "":
            configuration = list(config.sections())
        elif username in config.sections():
            configuration['api_key'] = config.get(username, "api_key")
            configuration['api_secret'] = config.get(username, 'api_secret')
            configuration['main_dir'] = config.get(username, 'root_dir')
            configuration['dirs'] = sorted([f for f in os.listdir(config.get(username, 'root_dir')) if not f.startswith('.')], key=lambda f: f.lower())
        else:
            configuration = False
        #logger.debug(configuration)
        return configuration

    def user_select(self, selection):
        # get the current value of the slider with `selection.value`
        self.username = str(selection.value)
        self.config = self.get_user(username=self.username)
        self.main_dir = self.config['main_dir']
        
        self.rootdir.text = self.main_dir
        self.dirtree.data.create_tree(self.main_dir)

    def action_select(self, selection):
        if selection.value == "Upload new photos to Flickr":
            self.action = 'update_remote'
        if selection.value == "Only update database":
            self.action = 'update_db'

    def tree_handler(self, widget, node):
        if node and hasattr(node,'subfolder'):
            if node.subfolder != self.config['main_dir']:
                # self.dir = os.path.join(self.config['main_dir'], node.subfolder)
                self.subdir.text = node.subfolder
            else:
                self.subdir.text = ''
        else:
            self.subdir.text = ''

    def toggle_update(self, switch):
        # Some action when you hit the switch
        #   In this case the label will change
        self.update = switch.is_on

    def toggle_public(self, switch):
        # Some action when you hit the switch
        #   In this case the label will change
        self.public = switch.is_on

    def toggle_family(self, switch):
        # Some action when you hit the switch
        #   In this case the label will change
        self.family = switch.is_on

    def toggle_friends(self, switch):
        # Some action when you hit the switch
        #   In this case the label will change
        self.friends = switch.is_on

    async def start(self, widget):
        global thread_id
        threads = dict()
        nargs = {}
        # print(post_data)
        nargs['main_dir'] = self.main_dir
        nargs['subdir'] = self.subdir
        nargs['public'] = self.public
        nargs['family'] = self.family
        nargs['friends'] = self.friends
        nargs['update'] = self.update

        username = self.username
        method = self.action

        #thread_id = self.startThread(username=username, method=method, nargs=nargs)
        q = asyncio.Queue()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.__async__run(user=username, queue=q, method=method, mkwargs=nargs))

    async def __async__run(self, user, queue, method, mkwargs):
        async with FlickrCore(user=user, queue=queue, method=method, dry_run=True, mkwargs=mkwargs) as self.flickrthread:
            await self.flickrthread.run()
            await self.update_monitor()

    async def update_monitor(self):
        """
        'actual_album': 0,
        'actual_image': 0,
        'album': '',
        'album_id': '',
        'exitFlag': False,
        'filename': '',
        'md5': '',
        'msg1': 'Rebuilding database',
        'msg2': 'Updating albums',
        'sha1': '',
        'stop': False,
        'total_albums': 190,
        'total_images': 0,
        'upload_progress': 0
        """

        progress = self.flickrthread.progress.dict
        while progress['exitFlag'] is False:
            try:
                self.apb.value = int((progress['actual_album'] / progress['total_albums']) * 100)
                self.ppb.value = int((progress['actual_image'] / progress['total_images']) * 100)
            except:
                pass


    def stop_thread(self, thread_id):
        global exporting_threads
        if thread_id in exporting_threads:
            exporting_threads[thread_id].progress.dict['stop'] = True
        else:
            exit(0)


def main():
    global exporting_threads
    global thread_id
    exporting_threads = {}
    thread_id = 0
    
    return UploaderGui('FlickrUploadr', 'com.FlickrUploadr.Gui')

if __name__ == '__main__':
    app = main()
    app.main_loop()