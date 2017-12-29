import os
import sys
import wx

from time import sleep
from pprint import pprint
import threading
from multiprocessing import Queue

import flickr_upload
from config import users

queue = Queue()
thread1 = ''
exitFlag = 0
path = ''


def startUpload(username='', root_dir='', subdir='', public=False, family=False, friends=False, update=False):
    global queue
    global thread1
    # Create new threads
    print('Thread objects currently alive: {}'.format(threading.activeCount()))
    print('Preparing thread1')

    # Set arguments for target function as keyword paramters
    nargs = {}
    if subdir == "":
        nargs['main_dir'] = root_dir
    else:
        nargs['main_dir'] = root_dir + '{}/'.format(subdir)

    nargs['user'] = username
    nargs['public'] = public
    nargs['family'] = family
    nargs['friends'] = friends
    nargs['update'] = update
    nargs['queue'] = queue

    print('Create thread1')
    thread1 = threading.Thread(target=flickr_upload.start_upload, name='Thread-1', kwargs=nargs)
    print('Thread objects currently alive: {}'.format(threading.activeCount()))

    print('Starting thread1')
    thread1.daemon = True
    thread1.start()
    print('Thread objects currently alive: {}'.format(threading.activeCount()))


def startUpdate(username=''):
    if username == '':
        print('=== No username given; exiting')
    else:
        global queue
        global thread1
        # Create new threads
        print('generating thread')

        # Set arguments for target function as keyword paramters
        nargs = {}

        nargs['main_dir'] = ''
        nargs['user'] = username
        nargs['public'] = False
        nargs['family'] = True
        nargs['friends'] = True
        nargs['update'] = True
        nargs['queue'] = queue

        pprint(nargs)

        print('Create thread')
        thread1 = threading.Thread(target=flickr_upload.start_upload, name='Thread-1', kwargs=nargs)

        print('starting thread')
        thread1.daemon = True
        thread1.start()
        print('Thread objects currently alive: {}'.format(threading.activeCount()))


class RedirectText(object):

    def __init__(self, aWxTextCtrl):
        self.out = aWxTextCtrl

    def write(self, string):
        if string[:1] != '{':
            wx.CallAfter(self.out.WriteText, string)


class MainFrame(wx.Frame):

    def __init__(self, parent):
        wx.Frame.__init__(self, parent, size=(650, 510))

        # Checkbox dict
        self.cb = {'public': False, 'family': False, 'friends': False}
        # Default positions and offsets
        h1 = 10
        h2 = 100
        h3 = 420
        vs = 5
        vo = 25

        # Add a panel so it looks the correct on all platforms
        self.panel = wx.Panel(self, wx.ID_ANY)

        # Add widgets
        self.l_user = wx.StaticText(self.panel,     label="Username",   pos=(h1,  vs + (0 * vo)),   size=(80, 25))
        self.l_dir = wx.StaticText(self.panel,      label="Root dir",   pos=(h1,  vs + (1 * vo)),   size=(80, 25))
        self.l_album = wx.StaticText(self.panel,    label="Album",      pos=(h1,  vs + (2 * vo)),   size=(80, 25))
        self.l_album_id = wx.StaticText(self.panel, label="Album_id",   pos=(h1,  vs + (3 * vo)),   size=(80, 25))
        self.l_fname = wx.StaticText(self.panel,    label="Filename",   pos=(h1,  vs + (4 * vo)),   size=(80, 25))
        self.l_prog = wx.StaticText(self.panel,     label="Progress",   pos=(h1,  vs + (5 * vo)),   size=(80, 25))
        self.l_MD5 = wx.StaticText(self.panel,      label="MD5",        pos=(h1,  vs + (6 * vo)),   size=(80, 25))
        self.l_SHA1 = wx.StaticText(self.panel,     label="SHA1",       pos=(h1,  vs + (7 * vo)),   size=(80, 25))
        self.l_msg = wx.StaticText(self.panel,      label="Message",    pos=(h1,  vs + (8 * vo)),   size=(80, 25))

        self.user = wx.ComboBox(self.panel,         name='userCombo',   pos=(h2, vs + (0 * vo)),    size=(300, 25), choices=list(users.keys()))
        self.dir = wx.StaticText(self.panel,        label="",           pos=(h2,  vs + (1 * vo)),   size=(300, 25), style=wx.TE_READONLY)
        self.album = wx.StaticText(self.panel,      label="",           pos=(h2,  vs + (2 * vo)),   size=(200, 25))
        self.album_id = wx.StaticText(self.panel,   label="",           pos=(h2,  vs + (3 * vo)),   size=(200, 25))
        self.filename = wx.StaticText(self.panel,      label="",           pos=(h2,  vs + (4 * vo)),   size=(200, 25))
        self.prog = wx.StaticText(self.panel,       label="",           pos=(h2,  vs + (5 * vo)),   size=(200, 25))
        self.MD5 = wx.StaticText(self.panel,        label="",           pos=(h2,  vs + (6 * vo)),   size=(200, 25))
        self.SHA1 = wx.StaticText(self.panel,       label="",           pos=(h2,  vs + (7 * vo)),   size=(200, 25))
        self.g_msg = wx.StaticText(self.panel,      label="",           pos=(h2,  vs + (8 * vo)),   size=(200, 25))
        self.u_msg = wx.StaticText(self.panel,      label="",           pos=(h2,  vs + (9 * vo)),   size=(200, 25))

        self.l_msg = wx.StaticText(self.panel,      label="Albums",     pos=(h1, vs + (10 * vo)),   size=(200, 20))
        self.g_albums = wx.Gauge(self.panel,                            pos=(h2, vs + (10 * vo)),   size=(300, 20), style=wx.GA_SMOOTH)

        self.l_msg = wx.StaticText(self.panel,      label="Photos",     pos=(h1, vs + (11 * vo)),   size=(200, 20))
        self.g_photos = wx.Gauge(self.panel,                            pos=(h2, vs + (11 * vo)),   size=(300, 20))

        self.l_msg = wx.StaticText(self.panel,      label="Upload",     pos=(h1, vs + (12 * vo)),   size=(200, 20))
        self.g_upl = wx.Gauge(self.panel,                            pos=(h2, vs + (12 * vo)),   size=(300, 20))

        self.listBox1 = wx.ListBox(choices=[],      name='listBox1',    pos=(h1, vs + (13 * vo)),   size=(400, 125), style=0, parent=self.panel)
        self.btnUpload = wx.Button(self.panel,      label="Upload",     pos=(5, vs + (18.25 * vo)), size=(200, 20))
        self.btnUpdate = wx.Button(self.panel,      label="Update",     pos=(275, vs + (18.25 * vo)), size=(125, 20))

        self.l_NewAlbum = wx.StaticText(self.panel, label="Permissions on new albums", pos=(h3, vs + (0 * vo)), size=(810, 25))
        self.chkNewPub = wx.CheckBox(self.panel,    label="public",     pos=(h3, vs + (1 * vo)),    size=(80, 25))
        self.chkNewFamily = wx.CheckBox(self.panel, label="family",     pos=(h3, vs + (2 * vo)),    size=(80, 25))
        self.chkNewFriend = wx.CheckBox(self.panel, label="friends",    pos=(h3, vs + (3 * vo)),    size=(80, 25))

        self.l_NoteNewAlbum = wx.StaticText(self.panel, label="This also includes all albums which have no permissions set in the database", pos=(h3, vs + (4 * vo)), size=(80, 25))
        self.l_NoteNewAlbum.Wrap(200)

        self.chkUpdate = wx.CheckBox(self.panel,    label="Update database before upload", pos=(h3, vs + (7 * vo)), size=(215, 25))

        # Bind function to button
        self.user.SetValue('')
        self.Bind(wx.EVT_COMBOBOX, self.OnCombo, self.user)
        self.Bind(wx.EVT_BUTTON, self.callUpload, self.btnUpload)
        self.Bind(wx.EVT_BUTTON, self.callUpdate, self.btnUpdate)

        self.Bind(wx.EVT_CHECKBOX, self.onChecked, self.chkNewPub)
        self.Bind(wx.EVT_CHECKBOX, self.onChecked, self.chkNewFamily)
        self.Bind(wx.EVT_CHECKBOX, self.onChecked, self.chkNewFriend)

        #self.log = wx.TextCtrl(self.panel, wx.ID_ANY,     pos=(10, 150), size=(580,250), style = wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL)

        # redirect text here
        # redir=RedirectText(self.log)
        # sys.stdout=redir

    def onChecked(self, event):
        chkbx = event.GetEventObject()
        self.cb[chkbx.GetLabel()] = chkbx.GetValue()

        if self.chkNewPub.GetValue() == True:
            self.chkNewFamily.Enable(False)
            self.chkNewFamily.SetValue(False)
            self.chkNewFriend.Enable(False)
            self.chkNewFriend.SetValue(False)
        elif self.chkNewPub.GetValue() == False:
            self.chkNewFamily.Enable(True)
            self.chkNewFriend.Enable(True)

        if self.chkNewFamily.GetValue() == True or self.chkNewFriend.GetValue() == True:
            self.chkNewPub.Enable(False)
            self.chkNewPub.SetValue(False)
        elif self.chkNewFamily.GetValue() == False or self.chkNewFriend.GetValue() == False:
            self.chkNewPub.Enable(True)

        print(self.cb)

    def OnCombo(self, event):
        global users
        global root_dir
        global username

        username = self.user.GetValue()
        root_dir = users[self.user.GetValue()]['root_dir']

        print('User selected from dropdown menu')
        print('USER:   {}'.format(username))
        print('KEY:    {}'.format(users[username]['api_key']))
        print('SECRET: {}'.format(users[username]['api_secret']))

        self.dir.SetLabel(root_dir)
        dirs = sorted([f for f in os.listdir(root_dir) if not f.startswith('.')],
                      key=lambda f: f.lower())
        self.listBox1.Set(dirs)

    def callFolder(self, evt):
        global root_dir
        dirs = sorted([f for f in os.listdir(root_dir) if not f.startswith('.')],
                      key=lambda f: f.lower())

    def callUpload(self, evt):
        # Disable button to be clicked again
        self.btnUpload.Enable(False)
        # Set gauge value to 0
        self.g_albums.SetValue(0)
        self.g_photos.SetValue(0)

        subdir = self.listBox1.GetStringSelection()
        print('\nWx GUI: Privacy settings:\n\tPublic={}\n\tFamily={}\n\tFriends={}\n'.format(
            self.cb['public'], self.cb['family'], self.cb['friends']))

        startUpload(username=username,
                    root_dir=root_dir,
                    subdir=subdir,
                    public=self.cb['public'],
                    family=self.cb['family'],
                    friends=self.cb['friends'],
                    update=self.chkUpdate.GetValue()
                    )

        thread2 = threading.Thread(target=self.longRunning,
                                   name='Thread-2',
                                   args=()
                                   )
        thread2.start()

    def callUpdate(self, evt):
        # Disable button to be clicked again
        self.btnUpdate.Enable(False)

        # Set gauge value to 0
        self.g_albums.SetValue(0)
        self.g_photos.SetValue(0)

        # Start a new thread calling "self.longRunning"
        startUpdate(username=username)
        thread2 = threading.Thread(target=self.longRunning,
                                   name='Thread-2',
                                   args=()
                                   )
        thread2.start()

    def onLongRunDone(self):
        self.g_albums.SetValue(0)
        self.g_photos.SetValue(0)

        self.btnUpload.Enable(True)
        self.btnUpdate.Enable(True)

        # Clear all labels
        self.album.SetLabel('')
        self.album_id.SetLabel('')
        self.filename.SetLabel('')
        self.prog.SetLabel('')
        self.MD5.SetLabel('')
        self.SHA1.SetLabel('')
        self.g_msg.SetLabel('')
        self.u_msg.SetLabel('')

    def longRunning(self):
        """This runs in a different thread."""
        global queue
        global thread1
        while thread1.isAlive():
            d = queue.get()
            if d['exitFlag']:
                thread1.join(1)
            else:
                try:
                    # Album title
                    self.album.SetLabel('{}'.format(d['album']))
                    # Album ID
                    self.album_id.SetLabel('{}'.format(d['album_id']))
                    # Filename
                    self.filename.SetLabel('{}'.format(d['filename']))
                    # Folder progress
                    self.prog.SetLabel('{: >3} of {: >3} ({: >3} of {: >3})'.format(d['actual_album'], d['total_albums'], d['actual_image'], d['total_images']))
                    # MD5 checksum
                    self.MD5.SetLabel('{}'.format(d['md5']))
                    # SHA1 checksum
                    self.SHA1.SetLabel('{}'.format(d['sha1']))
                    # Message line #1
                    self.g_msg.SetLabel('{}'.format(d['msg1']))
                    # Message line #2
                    self.u_msg.SetLabel('{}'.format(d['msg2']))

                    # Set gauge for album
                    wx.CallAfter(self.g_albums.SetRange, d['total_albums'])
                    wx.CallAfter(self.g_albums.SetValue, d['actual_album'])

                    # Set gauge for album photos
                    wx.CallAfter(self.g_photos.SetRange, d['total_images'])
                    wx.CallAfter(self.g_photos.SetValue, d['actual_image'])

                    # Set gauge for upload progress
                    wx.CallAfter(self.g_upl.SetRange, 100)
                    wx.CallAfter(self.g_upl.SetValue, d['upload_progress'])
                except:
                    wx.CallAfter(self.g_albums.SetValue, 0)
                    wx.CallAfter(self.g_photos.SetValue, 0)
                    wx.CallAfter(self.g_upl.SetValue, 0)
        wx.CallAfter(self.onLongRunDone)

if __name__ == "__main__":
    #app = wx.PySimpleApp()
    app = wx.App()
    app.TopWindow = MainFrame(None)
    app.TopWindow.Show()
    app.MainLoop()
