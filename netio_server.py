#!/usr/bin/env python


import RPi.GPIO as GPIO
import logging,sys, os
import time
from threading import Thread, Event, Lock
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer

http_server_port = 54321
AmpPin = 18
player = 'tpi'

class MyHttpHandler(BaseHTTPRequestHandler):
    def __init__(self,  *args):
        """ change Player for encoder """
        self.logger = logger or logging.getLogger(__name__)
        BaseHTTPRequestHandler.__init__(self, *args)

    def log_message(self, format, *args):
        return

    #Handler for the GET requests
    def do_GET(self):
        # do something with uri
        self.logger.debug("GOT URL: %s" %  self.path)
        try:
            if self.path == "/AmpON":
                self.logger.info("Starting AMP")
                GPIO.output(AmpPin, GPIO.LOW)
                self._return_200()
            elif self.path == "/AmpOFF":
                self.logger.info("Stopping AMP")
                GPIO.output(AmpPin, GPIO.HIGH)
                self._return_200()
            else:
                return self._return_404()
        except ValueError:
            pass

    def _return_200(self):
        self.logger.debug("Responding 200")
        self.send_response(200)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        self.wfile.write("ok\n")

    def _return_404(self):
        self.logger.debug("Responding 404")
        self.send_response(404)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        self.wfile.write("URL %s not found\n" % self.path)

class MyHttpServer:
    """ HTTP Server for changing the active player """
    def __init__(self,logger=None):
        self.logger = logger or logging.getLogger(__name__)

        # start http server for Jive remote
        self.t = Thread(target=self._select_player, args=())
        self.t.start()

    def _select_player(self):
        """ Waits on http for the active player """

	self.http_server = HTTPServer(('', http_server_port), MyHttpHandler)
	self.logger.info('Http Server started on port %i' % http_server_port)
	
        #Wait forever for incoming http requests
        self.logger.debug("HTTP Server Thread started")
        try:
            self.http_server.serve_forever()
        except Exception as e:
            self.logger.debug("Http Server closed")
            pass

    def destroy(self):
        self.http_server.socket.close()


if __name__ == '__main__':     # Program start from here

    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)

    GPIO.setmode(GPIO.BOARD)       # Numbers GPIOs by physical location
    GPIO.setup(AmpPin, GPIO.OUT)
    GPIO.output(AmpPin, GPIO.HIGH)
    logger.debug("Init Pin %i" % AmpPin)

    hs = MyHttpServer()

    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:  # When 'Ctrl+C' is pressed, the child program destroy() will be  executed.
        hs.destroy()
        GPIO.cleanup()

