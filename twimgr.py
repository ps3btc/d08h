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
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import images
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

def get_images(images):
  image_list = images
  for image in image_list:
    image.content = cgi.escape(image.content)
  return image_list

def get_header(title=None):
  if title:
    return title[:50] + '...'
  return 'embed your tweet inside the URL of the image that you upload'

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
    
class ImageObject(db.Model):
  author = db.UserProperty()
  content = db.StringProperty(multiline=True)
  payload = db.BlobProperty()
  date = db.DateTimeProperty(auto_now_add=True)

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
    image_list = get_images(db.GqlQuery("SELECT * FROM ImageObject ORDER BY date DESC LIMIT 20"))
    path = os.path.join(os.path.dirname(__file__), 'templates/home.html')
    template_values = {
      'image_list': image_list,
      'username': get_user(),
      'header' : get_header(),
      'show_trash' : False,
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
    }
    self.response.out.write(template.render(path, template_values))

class Delete(webapp.RequestHandler):
  def get(self, delete_link):
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
      header = get_header(link)
      break
    template_values = {
      'image_list': image_list,
      'username': req_author,
      'header' : header,
    }
    self.response.out.write(template.render(path, template_values))

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
    if users.get_current_user():
      xi.author = users.get_current_user()
    content = self.request.get("content")
    xi.content = validate_content(content)
    try:
      xi.payload = db.Blob(raw_img)
      xi.put()
    except:
      payload = images.resize(raw_img, 640, 480)
      xi.payload = db.Blob(raw_img)
      xi.put()
      
    self.redirect('/user')

def main():
  application = webapp.WSGIApplication([
      ('/', MainPage),
      ('/u', UpdatePage),
      ('/img', Image),
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