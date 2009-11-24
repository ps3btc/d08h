#!/usr/bin/env python
#
# Copyright 2009 Hareesh Nagarajan.

import os
import cgi
import datetime
import logging
import random
import wsgiref.handlers
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

def get_random_content():
  # TODO(hareesh): What if the same URI exists? Check+reject etc.
  return 'i like number %s' % str(hex(int(random.uniform(1, 1000000))))
  
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
  
  return ''.join(ll)
  
class ImageObject(db.Model):
  author = db.UserProperty()
  content = db.StringProperty(multiline=True)
  payload = db.BlobProperty()
  date = db.DateTimeProperty(auto_now_add=True)

class MainPage(webapp.RequestHandler):
  def get(self):
    image_list = get_images(db.GqlQuery("SELECT * FROM ImageObject ORDER BY date DESC LIMIT 10"))
    path = os.path.join(os.path.dirname(__file__), 'templates/home.html')
    template_values = {
      'image_list': image_list,
    }
    self.response.out.write(template.render(path, template_values))
    
class UpdatePage(webapp.RequestHandler):
  def get(self):
    path = os.path.join(os.path.dirname(__file__), 'templates/update.html')
    template_values = {}
    self.response.out.write(template.render(path, template_values))

class ShowUser(webapp.RequestHandler):
  def get(self):
    req_author = users.get_current_user()
    image_list = get_images(db.GqlQuery(
      "SELECT * FROM ImageObject WHERE author = :author ORDER BY date DESC",
      author=req_author))
    path = os.path.join(os.path.dirname(__file__), 'templates/home.html')
    template_values = {
      'image_list': image_list,
    }
    self.response.out.write(template.render(path, template_values))

class ShowLink(webapp.RequestHandler):
  def get(self, link):
    if not link:
      self.redirect('/')
    # TODO(hareesh): Add a check to make sure there is only 1 result
    # TODO(hareesh): Degrade gracefully if there are no results
    image_list = get_images(db.GqlQuery(
      "SELECT * FROM ImageObject WHERE content = :content ORDER BY date DESC",
      content=link))
    path = os.path.join(os.path.dirname(__file__), 'templates/home.html')
    template_values = {
      'image_list': image_list,
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
      self.redirect('/')
      return
    xi = ImageObject()
    if users.get_current_user():
      xi.author = users.get_current_user()
      
    content = self.request.get("content")
    xi.content = validate_content(content)
    try:
      payload = images.resize(raw_img, 640, 480)
      xi.payload = db.Blob(payload)
      xi.put()
    finally:
      self.redirect('/')
      return

def main():
  application = webapp.WSGIApplication([
      ('/', MainPage),
      ('/u', UpdatePage),
      ('/img', Image),
      ('/update', Update),
      ('/user', ShowUser),
      (r'/(.*)', ShowLink)
      ], debug=True)
  run_wsgi_app(application)

if __name__ == '__main__':
    main()