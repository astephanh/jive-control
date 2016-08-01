#!/usr/bin/env python 
import urllib2

amp_host = 'localhost'
amp_port = 54321


urllib2.urlopen("http://%s:%i/AmpOFF" % (amp_host,amp_port)).read()


