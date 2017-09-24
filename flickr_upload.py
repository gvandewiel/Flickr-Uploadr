 # Copyright 2009 Mark Longair

#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

# This depends on a couple of packages:
#   apt-get install python-pysqlite2 python-flickrapi

import os
import sys
import traceback
import re
#import xml
#import tempfile
#from subprocess import call, Popen, PIPE
#from optparse import OptionParser

import flickrapi
from common import *

#import datetime
from time import sleep
from datetime import datetime

import sqlite3 as sqlite

from photos_to_sqlite import Flickr_To_SQLite
from config import users

import requests

#import logging
#import curses
#from multiprocessing import Queue
###########

class output_dictionary():
  def __init__(self,queue=None):
    if queue != None:
      print('FlickrUpload: Recieved queue pointer')
    self.queue=queue
    self.out_dict={}
    self.out_dict['exitFlag']=False

  def add_to_queue(self,**kwargs):
    for key, value in kwargs.items():
      self.out_dict[key]=value

    if self.queue == None:
      print('out_dict={}'.format(self.out_dict))
    else:
      self.queue.put(self.out_dict)

  def clear(self):
    self.out_dict={'g_msg':'',
                   'u_msg':'',
                   'title':'',
                   'img_cnt':'',
                   'pcnt':'',
                   'sp':0,
                   'album_id':'',
                   'fname':'',
                   'md5':'',
                   'sha1':'',
                   'photo_id':'',
                   'up_photos':''}

def init(user=None,queue=None):
  print('FlickrUpload: Starting output_dictionary')
  q = output_dictionary(queue)
  global options
  configuration = {}
  if user in users:
    configuration['api_key']=users[user]['api_key']
    configuration['api_secret']=users[user]['api_secret']
  else:
    print('no user '+user+' found in dictionary')

  print('FlickrUpload: Starting connection to FlickrAPI')
  global flickr
  flickr = flickrapi.FlickrAPI(configuration['api_key'],configuration['api_secret'])
  flickr.authenticate_via_browser(perms='write')

  print('FlickrUpload: Starting database connection')
  global con,cur
  con = sqlite.connect(str(user)+'_flickr.sqlite')
  cur = con.cursor()

  print('FlickrUpload: Initate Flickr2SQLite module')
  global db
  db = Flickr_To_SQLite(flickr=flickr,
                        connection=con,
                        cursor=cur,
                        queue=queue)
  print('\n')
  return q, flickr, con,cur,db

def find_photo(md5,cursor):
  #log.debug('calculated md5sum = '+md5)
  flp = find_local_photo(md5,cursor)
  if flp == False:
    return find_flickr_photo(md5,cursor)
  else:
    return flp

def find_local_photo(md5,cursor):
  # Check local databse
  cursor.execute("SELECT id FROM photos WHERE md5=\'"+md5+"\'")
  id = cursor.fetchone()
  if id==None:
    return False
  else:
    return id[0]

def find_flickr_photo(md5,cursor):
  global md5_machine_tag_prefix
  # Check flickr database
  photos = flickr.photos_search(user_id="me",tags=md5_machine_tag_prefix + md5,extras="date_taken,machine_tags")
  photo_elements = photos.getchildren()[0]

  if len(photo_elements) == 0:
    #log.debug('No photo found in flickr db')
    return False
  else:
    if len(photo_elements) > 1:
      # Mark all photos for removal except first one
      for i, elem in enumerate(photo_elements[1:]):
        print('\tMarking photo with id "{}" for removal'.format(photo_elements[0].attrib['id']))
        result = flickr.photos.addTags(photo_id=elem,tags='ToDelete')

    db.write_photo_to_photo_db(photo_elements[0])
    con.commit
    return photo_elements[0].attrib['id']

def find_album(title,cursor):
  fla = find_local_album(title,cursor)
  if fla == False:
    return False
    #return find_flickr_album(title)
  else:
    return fla

def find_local_album(title,cursor):
  # Check local databse
  cursor.execute("SELECT id FROM albums WHERE Title =\'"+title+"\'")
  id = cursor.fetchone()
  if id==None:
    return False
  else:
    return id[0]

def find_flickr_album(title):
  # seems impossible
  #log.info('Force update of the sqlite database album table')
  db.list_albums()
  return find_local_album(title)

def retrieve_ids_from_album(id,cursor):
  try:
    result = cursor.execute("SELECT Id FROM \'"+str(album_id)+"\'")
    photo_list=[]
    for row in result:
      photo_list.append(row[0])
  except:
    # Return empty list
    photo_list=[]

  return photo_list

def add_to_album(item,photo_list):
  # Make set of photos
  photos = set(photo_list)
  # Search set for existing id;
  # add item to list if not found (preventing duplicates)
  if item not in photos:
    photos.add(item)
  return list(photos)

def callback(progress):
    print('uploading photo '+progress+'%')

def sort_album_photos(album_id):
  global cur
  cur.execute("SELECT id FROM \'"+str(album_id)+"\' ORDER BY date_taken ASC")
  id_list = cur.fetchall()

  sorted_id = list()
  for item in id_list:
    sorted_id.append(item[0])

  sorted_ids = ','.join([str(x) for x in sorted_id])
  flickr.photosets.reorderPhotos(photoset_id=str(album_id),photo_ids=str(sorted_ids))

def sort_albums(sort_photos=False):
  albums=dict()
  sorted_id = list()

  # Counter of set pages
  spage = 0
  # counter of processed albums
  s_cnt = 0
  # Retrieve total number of albums in Flickr database
  total_albums = int(flickr.photosets_getList(per_page="1",page="1").getchildren()[0].attrib['total'])
  print('Total number of albums: {}'.format(total_albums))
  while s_cnt < total_albums:
    spage += 1
    sets = flickr.photosets_getList(per_page="500",page=str(spage))
    set_elements = sets.getchildren()[0]
    for s in set_elements:
      s_cnt+=1
      print('{} - Setname {}'.format(s_cnt,s.getchildren()[0].text))
      albums[s.getchildren()[0].text] = s.attrib['id']

  print('Sorting albums')
  for key in sorted(albums, reverse=True):
    print("{}:{}".format(key, albums[key]))
    sorted_id.append(albums[key])
    
    # Sort album photos
    if sort_photos == True:
      print('\tReorder album photos for {}'.format(key))
      sort_album_photos(albums[key])

  sorted_ids = ','.join([str(x) for x in sorted_id])
  
  print('Reorder albums')
  flickr.photosets.orderSets(photoset_ids=sorted_ids)
  print('Finished reording photos')


##################################################################################################

def PostedToTaken(user=None,queue=None):
    q, flickr, con,cur,db = init(user=user,queue=queue)
    all_photos = []

    print('-----> Fetching all photos')

    total_pages = 1
    page = 1
    while page <= total_pages:
        print('       Fetching page {} out of {}'.format(page, total_pages))
        res = json.loads(flickr.photos_search(user_id='me', page=page, per_page=500, extras='date_upload,date_taken')[14:-1])
        total_pages = res['photos']['pages']
        page = res['photos']['page'] + 1
        photos = res['photos']['photo']
        all_photos.extend(photos)

    print('-----> Updating dates')

    for photo in  all_photos:
        date_taken = photo['datetaken']
        date_taken = datetime.strptime(date_taken, '%Y-%m-%d %H:%M:%S')
        date_posted = int(photo['dateupload'])
        date_posted = datetime.fromtimestamp(date_posted)
        if date_posted != date_taken:
            print('       Updating "{}": change date posted from {} to {}'.format(photo['id'], date_posted, date_taken))
            new_date_posted = datetime.strftime(date_taken, '%s')
            flickr.photos_setDates(photo_id=photo['id'], date_posted=new_date_posted)
        else:
            print('       Skipping "{}": dates match'.format(photo['id']))

    print('-----> Done!')


def Order_Photos_Albums(user=None,queue=None,sort_photos=False):
  q, flickr, con,cur,db = init(user=user,queue=queue)
  
  q.add_to_queue(g_msg='Sorting albums')
  sort_albums(sort_photos=sort_photos)

def start_upload(main_dir='',user=None,public=False,family=False,friends=False,update=False,queue=None):
  q, flickr, con,cur,db = init(user=user,queue=queue)

  if main_dir=='':
    if update==False:
      exit()
    elif update==True:
      q.add_to_queue(g_msg='Make local copy of Flickr database')
      db.update_sqlite()
      q.clear()
      exit()

  try:
    if update:
      q.add_to_queue(g_msg='Make local copy of Flickr database')
      db.update_sqlite()

    # Start the upload process
    q.add_to_queue(g_msg='Start upload of main_dir = '+main_dir)

    mmax = len(list(os.walk(main_dir)))
    q.add_to_queue(mmax=mmax)
    mcnt = 0
    # Start of dirloop
    for dirname, subdirlist, fileList in os.walk(main_dir, topdown=False):
      q.add_to_queue(g_msg='',
                     u_msg='',
                     title=os.path.basename(dirname),
                     img_cnt='',
                     pcnt='',
                     sp=0,
                     album_id='',
                     fname='',
                     md5='',
                     sha1='',
                     photo_id='',
                     up_photos='')
      FileEXT='.*\.gif|.*\.png|.*\.jpg|.*\.jpeg|.*\.JPG|.*\.JPEG|.*\.tif|.*\.tiff|.*\.MOV|.*\.AVI|.*\.MP4'
      mcnt += 1
      mp = (mcnt/mmax)*100
      q.add_to_queue(mcnt=mcnt, mmax=mmax, mp=float("{0:.2f}".format(mp)))
      # Count images in folder (check if empty)
      photo_list=[]
      img_cnt = len([name for name in fileList if not name.startswith(".") and re.match(FileEXT, name)])
      
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

        # Find album id (if any)
        album_id = find_album(title,cur)

        # Retrieve photo_id's from the local database
        if not album_id == False:
          photo_list = retrieve_ids_from_album(id,cur)
          #log.info(str(len(photo_list))+' photos found in local database')
          print('\nProcessing '+str(title))
          q.add_to_queue(title=title,
                         img_cnt=int(img_cnt),
                         album_id=album_id)

        # Loop over all files in directory
        pcnt=0
        for file in fileList:
          # Exclude hidden files and only upload image files
          if not file.startswith(".") and re.match(FileEXT, file):
            
            # Set full path of image file
            fname = os.path.join(dirname, file)
            real_sha1 = sha1sum(fname)
            real_md5 = md5sum(fname)
            tags = md5_machine_tag_prefix+str(real_md5)+' '+sha1_machine_tag_prefix+str(real_sha1)

            pcnt+=1
            sp=(pcnt/img_cnt)*100

            q.add_to_queue(pcnt=pcnt,
                           sp=float("{0:.2f}".format(sp)),
                           img_cnt=int(img_cnt),
                           fname=file,
                           md5=real_md5,
                           sha1=real_sha1)

            # Check local and remote databse for photo
            photo_id = find_photo(real_md5,cur)

            if photo_id == False:
              q.add_to_queue(g_msg='Nothing found in local or remote database',
                             u_msg='Uploading photo...')

              # Determine the width of the screen
              sc = int(os.popen('stty size', 'r').read().split()[1])-75
              
              # Start upload of new photo
              while True:
                try:
                    print('Trying to upload '+file+' to Flickr...')
                    result = flickr.upload(filename=fname,
                                           title=file,
                                           tags=tags,
                                           callback=callback,
                                           is_public=int(public),
                                           is_family=int(family),
                                           is_friend=int(friends))

                except requests.exceptions.Timeout:
                  q.add_to_queue(g_msg='Timeout occurd during upload',
                                 u_msg='Sleeping for 60 seconds...')
                  sleep(60)
                  continue
                break
              photo_id = result.getchildren()[0].text

              q.add_to_queue(photo_id=photo_id,
                             g_msg='Photo uploaded to Flickr',
                             u_msg='')

              #Add photo to local database
              cur.execute("INSERT INTO photos VALUES (?,?,?,?,?,?,?)",(photo_id,fname,real_md5,real_sha1,int(public),int(friends),int(family)))
              con.commit()

              # Update progressbar
              #rep = ' '*int(sc - len(str(os.path.basename(dirname)+"\\"+' uploaded '+file+'with id='+photo_id)))
              #pb.fname = str(os.path.basename(dirname)+"\\"+' UPLOADED '+file+' with id='+photo_id+rep)

              photo_list = add_to_album(photo_id,photo_list)
              stime = 1
            else:
              # Photo already uploaded
              cur.execute("SELECT public,friend,family FROM photos WHERE id=\'"+str(photo_id)+"\'")
              db_public, db_friend, db_family = cur.fetchone()
              
              # Update title with current filename
              #result = flickr.photos.setMeta(photo_id=photo_id,title=file)
              '''
              if (not db_public == int(public) ) or (not db_friend == int(friends) ) or (not db_family==int(family) ):
                # Update perms
                q.add_to_queue(g_msg='Found in local database',
                                u_msg='Updating permissions',
                                title=title,
                                img_cnt=img_cnt,
                                album_id=album_id,
                                fname=fname,
                                md5=real_md5,
                                sha1=real_sha1,
                                photo_id=photo_id,
                                up_photos='')

                flickr.photos.setPerms(photo_id=photo_id,
                                       is_public=int(public),
                                       is_friend=int(family),
                                       is_family=int(friends))

                print('PhotoID='+str(photo_id)+' Writing permissions to database')
                cur.execute("UPDATE photos SET public="+str(int(public))+" WHERE id=\'"+str(photo_id)+"\'")
                cur.execute("UPDATE photos SET family="+str(int(family))+" WHERE id=\'"+str(photo_id)+"\'")
                cur.execute("UPDATE photos SET friend="+str(int(friends))+" WHERE id=\'"+str(photo_id)+"\'")
                con.commit()
                '''

              photo_list = add_to_album(photo_id,photo_list)
              stime = 0
        sleep(stime)
        #### End of file loop ####

        #Create or update album
        if album_id == False:
          album_id = flickr.photosets.create(title=title,
                                             description="",
                                             primary_photo_id=photo_list[0]).getchildren()[0].attrib['id']
          
          q.add_to_queue(g_msg='Creating new album',
                     u_msg='',
                     title=title,
                     img_cnt=img_cnt,
                     pcnt=pcnt,
                     album_id=album_id,
                     fname=fname,
                     md5=real_md5,
                     sha1=real_sha1,
                     photo_id=photo_id,
                     up_photos='')
          
          print('Creating table "album_id" with all photo_id\'s')
          cur.execute("DROP TABLE IF EXISTS \'"+str(album_id)+"\'")
          cur.execute("CREATE TABLE \'"+str(album_id)+"\' (Id INT)")

          data = [(photo,) for photo in photo_list]
          cur.executemany("INSERT INTO \'"+str(album_id)+"\' VALUES (?)",data)
          
          # Add album to local db albums
          print('Add "album_id" albums table')
          cur.execute("INSERT INTO albums VALUES (?,?,?,?)",(album_id,title,len(photo_list),0))
          
          con.commit()

        # Update flickr photoset to show all photos
        q.add_to_queue(g_msg='Updating album',
                   u_msg='',
                   title=title,
                   img_cnt=img_cnt,
                   pcnt=pcnt,
                   album_id=album_id,
                   fname=fname,
                   md5=real_md5,
                   sha1=real_sha1,
                   photo_id=photo_id,
                   up_photos=len(photo_list))

        print('\tAdd photos to album at Flickr')
        sdl = ','.join([str(x) for x in photo_list])
        flickr.photosets.editPhotos(photoset_id=str(album_id),primary_photo_id=str(photo_list[0]),photo_ids=str(sdl))
        
        print('\tReorder album photos on date-taken')
        q.add_to_queue(g_msg='Reorder album photos on date-taken')
        sort_album_photos(album_id)

    #### End of dir loop ####
    print('Sorting all albums')
    q.add_to_queue(g_msg='Sorting albums')
    sort_albums()

  except:
    print('TRACEBACK')
    traceback.print_exc()
  finally:
    q.add_to_queue(exitFlag=True)

