#!/usr/bin/env python
#
# Copyright 2009 Hareesh Nagarajan.

import os
import cgi
import datetime
import logging
import random
import wsgiref.handlers
import urllib
import time
import re
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import images
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

first_cap_re = re.compile('(.)([A-Z][a-z]+)')
all_cap_re = re.compile('([a-z0-9])([A-Z])')

def strip_camel_case(content):
  s1 = first_cap_re.sub(r'\1_\2', content)
  txt = all_cap_re.sub(r'\1_\2', s1).lower()
  return txt.replace('_', ' ')

class ImageObject(db.Model):
  author = db.UserProperty()
  content = db.StringProperty(multiline=True)
  full_text = db.StringProperty(multiline=True)
  payload = db.BlobProperty()
  thumbnail = db.BlobProperty()
  date = db.DateTimeProperty(auto_now_add=True)
  views = db.IntegerProperty(default=1)
  date_str = db.StringProperty(default="")

def get_time_ago(reference_epoch, created_dt):
  # pretty_dates.append(get_time_ago(time.time(), image.date))
  seconds_ago = int(reference_epoch - time.mktime(created_dt.timetuple()))
  ret = '%d seconds' % seconds_ago
  if seconds_ago > 60 and seconds_ago <= 3600:
    ret = '%d minutes' % (seconds_ago / 60)
  elif seconds_ago > 3600 and seconds_ago <= 86400:
    ret = '%d hours' % (seconds_ago / 3600)
  elif seconds_ago > 86400:
    ret = '%d days' % (seconds_ago / 86400)
  return ret

def get_images(images):
  reference_epoch = time.time()  
  for img in images:
    img.content = cgi.escape(img.content)
    img.date_str = get_time_ago(reference_epoch, img.date)
    try:
      img.put()
    except:
      logging.error('get_images(): Oops, problem in the image put')
  return images

def get_header(title=None):
  if title:
    logging.info('the length of title %s %d', title, len(title))
    if len(title) < 50:
      return title
    else:
      return title[:50] + '...'
  return '<a href="/" title="TwImgr.com" alt="TwImgr.com">twimgr.com</a>'

def get_random_content():
  uri = 'i like number %s' % str(hex(int(random.uniform(1, 1000000))))
  return generate_unique_uri(uri)

def content_exist(uri):
  image_list = get_images(db.GqlQuery(
    "SELECT * FROM ImageObject WHERE content = :content",
    content=uri))
  for image in image_list:
    return True
  return False

def delete_content(uri):
  image_list = get_images(db.GqlQuery(
    "SELECT * FROM ImageObject WHERE content = :content AND author = :author",
    content=uri,
    author=users.get_current_user(),
    ))
  for image in image_list:
    logging.info('Found the image to delete ...')
    image.delete()
    return True
  return False

def generate_unique_uri(uri):
  test_uri = uri[:120]
  while content_exist(test_uri):
    test_uri = uri + str(hex(int(random.uniform(1, 10000))))
    logging.error('Uri already exists. Regenerating %s (%s)', test_uri, uri)
  return test_uri
  
def validate_content(content):
  if len(content) == 0:
    content = get_random_content()
  else:
    content = content[:120]
    new_content = []
    idx = 0
    while idx < len(content):
      if (content[idx].isalnum() or content[idx] == ' '):
        new_content.append(content[idx])
      idx+=1
    content = ''.join(new_content)
    
  ll=[]
  for word in content.split():
    ll.append(word.capitalize())
  
  unique_uri = ''.join(ll)
  return generate_unique_uri(unique_uri)
    
def get_user():
  req_author = users.get_current_user()
  if req_author:
    return req_author.email()
  else:
    return ''
  
class Problem(webapp.RequestHandler):
  def get(self, problem):
    path = os.path.join(os.path.dirname(__file__), 'templates/problem.html')
    template_values = {
      'username' : get_user(),
      'problem' : problem,
      'header' : get_header(),
    }
    self.response.out.write(template.render(path, template_values))

class About(webapp.RequestHandler):
  def get(self):
    req_author = users.get_current_user()
    path = os.path.join(os.path.dirname(__file__), 'templates/about.html')
    template_values = {
      'username' : get_user(),
      'header' : get_header(),
    }
    self.response.out.write(template.render(path, template_values))

class MainPage(webapp.RequestHandler):
  def get(self):
    image_list = get_images(db.GqlQuery("SELECT * FROM ImageObject ORDER BY date DESC"))
    path = os.path.join(os.path.dirname(__file__), 'templates/new_home.html')
    template_values = {
      'image_list': image_list,
      'username': get_user(),
      'header' : get_header(),
    }
    self.response.out.write(template.render(path, template_values))

class AllImages(webapp.RequestHandler):
  def get(self):
    image_list = get_images(db.GqlQuery("SELECT * FROM ImageObject ORDER BY views DESC"))
    path = os.path.join(os.path.dirname(__file__), 'templates/all.html')
    template_values = {
      'image_list': image_list,
      'username': get_user(),
      'header' : get_header(),
    }
    self.response.out.write(template.render(path, template_values))
  
class UpdatePage(webapp.RequestHandler):
  def get(self):
    path = os.path.join(os.path.dirname(__file__), 'templates/update.html')
    template_values = {
      'username' : get_user(),
      'header' : get_header()
    }
    self.response.out.write(template.render(path, template_values))

class ShowUser(webapp.RequestHandler):
  def get(self, this_user=None):
    req_author = get_user()
    if (req_author == '') and (this_user == '' or this_user == None):
      self.redirect('/user')
      return
    search_user = users.get_current_user()
    if this_user:
      this_user = unicode(urllib.unquote(this_user), 'utf-8')
      search_user = users.User(urllib.unquote_plus(this_user))
    image_list = get_images(db.GqlQuery(
      "SELECT * FROM ImageObject WHERE author = :author ORDER BY date DESC LIMIT 30",
      author=search_user))
    results = 0
    for image in image_list:
      results+=1
    if results == 0:
      self.redirect('/problem/ERR_USER_NO_RESULTS')
      return
    path = os.path.join(os.path.dirname(__file__), 'templates/home.html')
    template_values = {
      'image_list': image_list,
      'username' : req_author,
      'header' : get_header(),
      'show_trash' : True,
      'show_link' : False,
    }
    self.response.out.write(template.render(path, template_values))

class Delete(webapp.RequestHandler):
  def get(self, delete_link):
    delete_link = unicode(urllib.unquote(delete_link), 'utf-8')
    req_author = get_user()
    if req_author == '':
      self.redirect('/problem/ERR_NOT_SIGNED_IN')
      return
    if not delete_content(delete_link):
      self.redirect('/problem/ERR_LINK_CANNOT_DELETE')
      return
    self.redirect('/user')

class ShowLink(webapp.RequestHandler):
  def get(self, link):
    link = unicode(urllib.unquote(link), 'utf-8')
    req_author = get_user()
    if req_author == '':
      req_author = 'not signed in'
    if not content_exist(link):
      self.redirect('/problem/ERR_LINK_NOT_EXIST')
      return
    image_list = get_images(db.GqlQuery(
      "SELECT * FROM ImageObject WHERE content = :content ORDER BY date DESC LIMIT 1",
      content=link))
    path = os.path.join(os.path.dirname(__file__), 'templates/home.html')
    header = get_header()
    for image in image_list:
      header = get_header(image.full_text)
      image.views +=1
      image.put()
      break
    template_values = {
      'image_list': image_list,
      'username': req_author,
      'header' : header,
      'show_link' : True,
    }
    self.response.out.write(template.render(path, template_values))

class Thumbnail(webapp.RequestHandler):
  def get(self):
    image = db.get(self.request.get("img_id"))
    if image.payload:
      self.response.headers['Content-Type'] = "image/png"
      self.response.out.write(image.thumbnail)
    else:
      self.response.out.write("No image")

class Image(webapp.RequestHandler):
  def get(self):
    image = db.get(self.request.get("img_id"))
    if image.payload:
      self.response.headers['Content-Type'] = "image/png"
      self.response.out.write(image.payload)
    else:
      self.response.out.write("No image")

class Update(webapp.RequestHandler):
  def post(self):
    raw_img = self.request.get("img")
    if len(raw_img) == 0:
      logging.info('Image payload is empty')
      self.redirect('/problem/ERR_PAYLOAD_EMPTY')
      return
    if len(raw_img) > 1000000:
      logging.error('Image is too large')
      self.redirect('/problem/ERR_IMG_TOO_LARGE')
      return
    xi = ImageObject()
    xi.views = 0
    if users.get_current_user():
      xi.author = users.get_current_user()
    content = self.request.get("content")
    xi.content = validate_content(content)
    xi.full_text = strip_camel_case(content)
    try:
      xi.payload = db.Blob(raw_img)
      xi.thumbnail = create_thumbnail(xi)
      xi.put()
    except:
      payload = images.resize(raw_img, 640, 480)
      xi.payload = db.Blob(raw_img)
      xi.thumbnail = create_thumbnail(xi)
      xi.put()
    self.redirect('/user')

def create_thumbnail(image):
  img = images.Image(image.payload)
  img.resize(width=160, height=120)
  img.im_feeling_lucky()
  return img.execute_transforms(output_encoding=images.PNG)
  
class Resize(webapp.RequestHandler):
  def get(self):
    image_list = get_images(db.GqlQuery("SELECT * FROM ImageObject"))
    for image in image_list:
      if image.thumbnail:
        logging.info('already resized ... %s' % (image.content))
        continue
      thumbnail = create_thumbnail(image)
      image.thumbnail = db.Blob(thumbnail)
      image.full_text = strip_camel_case(image.content)
      logging.info('resizing: %s ----> %s' % (image.content, image.full_text))
      time.sleep(1)
      image.put()
    self.redirect('/')

def main():
  application = webapp.WSGIApplication([
      ('/', MainPage),
      ('/all', AllImages),    
      ('/u', UpdatePage),
      ('/img', Image),
      ('/tiny', Thumbnail),
      ('/update', Update),
      (r'/user/(.*)', ShowUser),
      ('/user', ShowUser),
      ('/about', About),
      (r'/delete/(.*)', Delete),      
      (r'/problem/(.*)', Problem),
      (r'/(.*)', ShowLink)
      ], debug=True)
  run_wsgi_app(application)

if __name__ == '__main__':
    main()
