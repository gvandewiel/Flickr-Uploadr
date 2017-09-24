from __future__ import print_function
import os
import re

import sys
import xml
import tempfile
from subprocess import call, Popen, PIPE

import datetime
import tempfile
from time import time, sleep
from datetime import datetime

from pprint import pprint

from multiprocessing import Queue

from common import *
import flickrapi

#flickr = flickrapi.FlickrAPI(configuration['api_key'],configuration['api_secret'])
#flickr.authenticate_via_browser(perms='write')

#(token, frob) = flickr.get_token_part_one(perms='write')
#if not token:
#    raw_input("Press 'Enter' after you have authorized this program")
#flickr.get_token_part_two((token, frob))

import sqlite3 as lite
import sys

class output_dictionary():
  def __init__(self,queue=None):
    if queue != None:
      print('Flickr2SQLite: Recieved queue pointer')
    self.queue=queue
    self.out_dict={}
    self.out_dict['exitFlag']=False

  def add_to_queue(self,**kwargs):
    for key, value in kwargs.items():
      self.out_dict[key]=value

    if self.queue == None:
      pprint(self.out_dict)
    else:
      #pprint(self.out_dict)
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


class Flickr_To_SQLite:
	def __init__(self,flickr,connection,cursor,queue=None):
		self.q = output_dictionary(queue)

		self.q.add_to_queue(g_msg='',
							u_msg='',
							title='',
							img_cnt='',
							pcnt='',
							sp=0,
							album_id='',
							fname='',
							md5='',
							sha1='',
							photo_id='',
							up_photos='')

		print('Flickr2SQLite: Starting Flickr instance')
		self.flickr = flickr
		print('Flickr2SQLite: Starting Database connection')
		self.connection = connection
		print('Flickr2SQLite: Starting Database cursor')
		self.cursor = cursor
		print('Flickr2SQLite: Create database tables...')
		cursor.execute("CREATE TABLE IF NOT EXISTS photos(Id INT, Title TEXT, md5 TEXT, sha1 TEXT, public INT, friend INT, family INT, date_taken TEXT)")
		cursor.execute("CREATE TABLE IF NOT EXISTS albums(Id INT, Title TEXT, photos INT, videos INT)")

	def update_sqlite(self):
		self.cursor.execute("DROP TABLE IF EXISTS photos")
		self.cursor.execute("DROP TABLE IF EXISTS albums")

		self.cursor.execute("CREATE TABLE photos(Id INT, Title TEXT, md5 TEXT, sha1 TEXT, public INT, friend INT, family INT, date_taken TEXT)")
		self.cursor.execute("CREATE TABLE albums(Id INT, Title TEXT, photos INT, videos INT)")
		self.connection.commit()

		self.list_photos()
		self.connection.commit()
		
		self.list_albums()
		self.connection.commit()

		self.q.add_to_queue(exitFlag=True)
		exit()

	def download_flickr_photo(self,id):
		self.q.add_to_queue(u_msg='Downloading photo to determine checksum...')
		info_result = self.flickr.photos_getInfo(photo_id=id)
		farm_url = info_to_url(info_result,'o')

		# Make temporary file to download photo into
		f = tempfile.NamedTemporaryFile()
		f.close()

		# Download photo to temporary file
		print("\tDownloading photo from flickr")
		p = Popen(["curl","--location","-o",f.name,farm_url],stdout=PIPE,stderr=PIPE)
		out, err = p.communicate()

		#call(["curl","--location","-o",f.name,farm_url])

		# Calculate checksums
		real_md5sum = md5sum(f.name)
		real_sha1sum = sha1sum(f.name)

		# Add tags to photos
		for t in info_result.getchildren()[0].find('tags'):
			if re.search('^'+md5_machine_tag_prefix,t.attrib['raw']):
				m_md5 = t.attrib['id']
			if re.search('^'+sha1_machine_tag_prefix,t.attrib['raw']):
				m_sha1 = t.attrib['id']

		if 'm_md5' in locals():
			print("\tremoving old MD5 tag ("+m_md5+")")
			self.flickr.photos.removeTag(tag_id=m_md5)

		if 'm_sha1' in locals():
			print("\tremoving old SHA1 tag ("+m_sha1+")")
			self.flickr.photos.removeTag(tag_id=m_sha1)

		print("\tSetting MD5 tag = \t"+real_md5sum)
		self.flickr.photos.addTags(photo_id=id, tags=md5_machine_tag_prefix+real_md5sum)
		
		print("\tSetting SHA1 tag = \t"+real_sha1sum)
		self.flickr.photos.addTags(photo_id=id, tags=sha1_machine_tag_prefix+real_sha1sum)
		
		# Remove temporary file
		print("\tRemoving temporary file.\n")
		call(["rm",f.name])

		return (real_md5sum,real_sha1sum)

	def write_photo_to_album_db(self,album_id,photo_element):
		id = photo_element.attrib['id']
		title = photo_element.attrib['title']

		pdt = datetime.strptime(photo_element.attrib['datetaken'],'%Y-%m-%d %H:%M:%S')
		date_taken = '{:02d}{:02d}{:02d}{:02d}{:02d}{:02d}'.format(pdt.year,pdt.month,pdt.day,pdt.hour,pdt.minute,pdt.second)

		#if self.cursor == False:
		#	return (id,)
		#else:
		#	self.cursor.execute("INSERT INTO \'"+str(album_id)+"\' VALUES (?)",(id,))
		self.cursor.execute("INSERT INTO \'"+str(album_id)+"\' VALUES (?,?)",(id,date_taken))

	def write_album_to_db(self,set_element):
		id = set_element.attrib['id']
		title = set_element.getchildren()[0].text
		photos = set_element.attrib['photos']
		videos = set_element.attrib['videos']
		
		update = self.photos_in_albums(id)

		#if self.cursor == False:
		#	return (id,title,photos,videos)
		#else:
		#	self.cursor.execute("INSERT INTO albums VALUES (?,?,?,?)",(id,title,photos,videos))
		self.cursor.execute("INSERT INTO albums VALUES (?,?,?,?)",(id,title,photos,videos))

	def photos_in_albums(self,album_id):
		data=[]
		self.cursor.execute("DROP TABLE IF EXISTS \'"+str(album_id)+"\'")
		self.cursor.execute("CREATE TABLE \'"+str(album_id)+"\' (Id INT, date_taken TEXT)")
		total_set_photos = int(self.flickr.photosets_getPhotos(photoset_id=album_id, per_page="1",page="1", media="all").getchildren()[0].attrib['total'])
		
		# page number
		spp = 1

		# number of photos processed
		sp_cnt = 0

		while sp_cnt < total_set_photos:
			photos = self.flickr.photosets_getPhotos(photoset_id=album_id, per_page="500",page=spp, media="all" ,extras="machine_tags, date_taken")
			photo_elements = photos.getchildren()[0]
			for p in photo_elements:
				sp_cnt+=1
				#id = p.attrib['id']
				#title = p.attrib['title']
				data.append(self.write_photo_to_album_db(album_id,p))
			spp += 1
			#cursor.executemany("INSERT INTO \'"+str(album_id)+"\' VALUES (?)",data)
		self.connection.commit

	def list_albums(self):
		data=[]
		
		# Counter of set pages
		spage = 0
		# counter of processed albums
		s_cnt = 0
		# Retrieve total number of albums in Flickr database
		total_albums = int(self.flickr.photosets_getList(per_page="1",page="1").getchildren()[0].attrib['total'])

		sp=(s_cnt/total_albums)*100

		# Loop over albums and retrieve ID, title and the number of photo's and video's
		self.q.add_to_queue(
							g_msg='Updating albums',
							pcnt=s_cnt,
							img_cnt=total_albums,
							sp=sp)
		
		while s_cnt < total_albums:
			spage += 1
			sets = self.flickr.photosets_getList(per_page="500",page=str(spage))
			set_elements = sets.getchildren()[0]
			for s in set_elements:
				# Update progressbar
				s_cnt+=1
				sp=(s_cnt/total_albums)*100
				self.q.add_to_queue(
									g_msg='Updating albums',
									pcnt=s_cnt,
									sp=sp)
				#update = photos_in_albums(id)
				data.append(self.write_album_to_db(s))
				#cur.execute("INSERT INTO albums VALUES (?,?,?,?)",(id,title,photos,videos))
		self.q.add_to_queue(g_msg='update sqlite database with album_ids')
		self.connection.commit
		#cursor.executemany("INSERT INTO albums VALUES (?,?,?,?)",data)

	def write_photo_to_photo_db(self,photo_element):
		while True:
			try:
				id = photo_element.attrib['id']
				title = photo_element.attrib['title']

				try:
					machine_tags=photo_element.attrib['machine_tags'].split(' ')
					if 'checksum:md5=' in machine_tags[0]:
						md5 = machine_tags[0].replace('checksum:md5=','')
						sha1 = ''
					elif 'checksum:sha1=' in machine_tags[0]:
						sha1 = machine_tags[0].replace('checksum:sha1=','')
						md5 = ''

					if 'checksum:md5=' in machine_tags[1]:
						md5 = machine_tags[1].replace('checksum:md5=','')
					elif 'checksum:sha1=' in machine_tags[1]:
						sha1 = machine_tags[1].replace('checksum:sha1=','')
					if md5=='' or sha1=='':
						print("\tIncomplete tags")
						md5, sha1 = self.download_flickr_photo(id)
				except:
					# No machine tags available
					# Call routine to download file and determine checksum
					# and add the data to the photos
					print("\tNog tags found")
					md5, sha1 = self.download_flickr_photo(id)

				# Show checksums of photo
				print("PhotoID = "+id+"\tMD5sum = "+md5+"\tSHA1sum = "+sha1)
				self.q.add_to_queue(md5=md5,sha1=sha1)

				if not re.search('^'+checksum_pattern+'$',md5):
					print("\tMalformed MD5")
					self.q.add_to_queue(g_msg="The MD5sum ('"+md5+"') was malformed.\n\nIt must be 32 letters long, each one of 0-9 or a-f.")
					md5, _ = self.download_flickr_photo(id)
					self.q.add_to_queue(md5=md5)
				if not re.search('^'+checksum_pattern+'$',sha1):
					print("\tMalformed SHA1")
					self.q.add_to_queue(g_msg="The SHA1sum ('"+sha1+"') was malformed.\n\nIt must be 40 letters long, each one of 0-9 or a-f.")
					_, sha1 = self.download_flickr_photo(id)
					self.q.add_to_queue(sha1=sha1)

				pdt = datetime.strptime(photo_element.attrib['datetaken'],'%Y-%m-%d %H:%M:%S')
				date_taken = '{:02d}{:02d}{:02d}{:02d}{:02d}{:02d}'.format(pdt.year,pdt.month,pdt.day,pdt.hour,pdt.minute,pdt.second)
				print('date_taken = {}'.format(date_taken))

				print('Setting data tuple with id,title,md5,sha1,date_taken')
				data = (id,title,md5,sha1,1,0,0,date_taken)
				#if self.cursor == False:
				#	return data
				#else:
				print('writing data into DB')
				self.cursor.execute("INSERT INTO photos VALUES (?,?,?,?,?,?,?,?)",data)
			except:
				print("\nError occurd, propbaly a TimeoutError")
				print("Waiting for 60 seconds")
				sleep(60)
				continue
			break
		sleep(0.002)

	def list_photos(self):
		data=[]
		
		# Counter of processed photos
		p_cnt = 0
		
		# Counter for pages
		ppage = 0
		# Retrieve total number of photo's in Flickr database
		total_photos = int(self.flickr.photos_search(user_id="me",per_page="1",page="1",media="all", extras=", date_taken,machine_tags").getchildren()[0].attrib['total'])

		# Retrieve metadata of all photos's from flickr and store in local sqllite database
		sp=(p_cnt/total_photos)*100

		self.q.add_to_queue(
							g_msg='Updating photos',
							pcnt=p_cnt,
							img_cnt=total_photos,
							mp=sp)

		while p_cnt<total_photos:
			ppage += 1
			photos = self.flickr.photos_search(user_id="me",per_page="500",page=str(ppage), media="all" ,extras="date_taken,machine_tags")
			photo_elements = photos.getchildren()[0]
			for p in photo_elements:
				p_cnt += 1

				sp=(p_cnt/total_photos)*100
				self.q.add_to_queue(
									g_msg='Updating photos',
									pcnt=p_cnt,
									mp=sp)

				data.append(self.write_photo_to_photo_db(p))

		self.q.add_to_queue(g_msg='Update sqlite database with photo_ids')
		self.connection.commit
		#self.cursor.executemany("INSERT INTO photos VALUES (?,?,?,?)",data)
