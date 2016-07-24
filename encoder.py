#!/usr/bin/env python
import RPi.GPIO as GPIO
import subprocess
import time
import json
import urllib2
import logging,sys, os
import socket
from evdev import InputDevice, categorize, ecodes
from select import select
from threading import Thread, Lock

#
# python squeezebox: https://github.com/jinglemansweep/PyLMS/blob/master/pylms/player.py
#

url = 'http://rpi:9000/jsonrpc.js'
player_id = 'b8:27:eb:3d:83:04'

RoAPin = 11    # pin11
RoBPin = 12    # pin12
RoSPin = 13    # pin13
LightPin = 15  # light pin
MovePin = 16   # movement detector
rebootPin = 40

display_vt = 5
maxVolume = 100
stepper = 10

# AMP Defaults
player_name = 'tpi'
amp_host = 'localhost'
amp_port = 54321

#use_lightsensor = False
use_lightsensor = True
#do_reboot = False
do_reboot = True

class Display:
    def __init__(self,timer,logger=None):
        """ light or no light"""
        self.logger = logger or logging.getLogger(__name__)
        self.maxcount = timer
        self.DisplayLock = Lock()
        self.count = 0
        self.is_on = False
        self.close = False
        global use_lightsensor

        # touch device
        self.dev = InputDevice('/dev/input/event1')
        self.logger.debug("Touch Dev: %s" % self.dev)
        
        GPIO.setup(LightPin, GPIO.OUT)
        GPIO.output(LightPin, GPIO.LOW)
        GPIO.setup(MovePin, GPIO.IN,pull_up_down=GPIO.PUD_DOWN)

        # start display
        if self.change_vt(display_vt):
            self.logger.debug("Waiting for Display to change")
            time.sleep(0.3)
        self.on()

        # light Sensor
        if use_lightsensor:
            GPIO.add_event_detect(MovePin, GPIO.RISING, callback=self.reset, bouncetime=500) # wait for raising

    def change_vt(self,vt):
        current_vt = int(subprocess.check_output(["/bin/fgconsole"]))
        if current_vt != vt:
            self.logger.debug("Changing VT from %i to %i" % (current_vt, vt) )
            subprocess.call(['/bin/chvt', str(vt)]) 
            return True
        return False

    def _sleeper(self):
        while self.count < self.maxcount:
            if self.close:
                self.logger.info("Destroying Timer")
                return True

            time.sleep(1) 
            self.DisplayLock.acquire()
            self.count += 1
            self.logger.debug("Counting: %i" % self.count)
            self.DisplayLock.release()

        if use_lightsensor:
            self.off()
        else:
            self.reset()

    def _watch_key(self):
        """ watch for touch movements if off """

        # miss the first input (light off)
        time.sleep(1)
        grabed = False

        while not grabed:
            try:
                self.dev.grab()
                grabed = True
            except Exception:
                time.sleep(0.3)
                pass
            
        # check for input
        self.logger.info("starting touch detector")

        while not self.close:
            try:
                self.logger.debug("waiting for input")
                r,w,x = select([self.dev], [], [], 0.5)
                for event in self.dev.read():
                    if event.type == ecodes.EV_KEY:
                        self.logger.debug(categorize(event))
                        self.reset()
                        self.dev.ungrab()
                        self.logger.debug("Destroying touch detection")
                        return True
            except Exception,e:
                pass

    def off(self):
        if self.is_on:
            GPIO.output(LightPin, GPIO.LOW)
            self.logger.debug("Turning Display Off")
            self.is_on = False


    def on(self):
        if use_lightsensor:
            if not self.is_on:
                # start sleeper thread
                t = Thread(target=self._sleeper, args=())
                t.start()

                GPIO.output(LightPin, GPIO.HIGH)
                self.logger.debug("Turning Display On")
                self.is_on = True

    def reset(self,ev=None):
        self.DisplayLock.acquire()
        self.logger.debug("Resetting Counter")
        self.count = 0
        if not self.is_on:
            self.on()
        self.DisplayLock.release()

    def destroy(self):
        self.close = True

class MySqueeze:
    def __init__(self,playername,logger=None):
        self.logger = logger or logging.getLogger(__name__)

        # init class
        self.player = self._get_player(playername)
        self.player['name'] = playername
        self._get_volume()
        self.logger.debug('Player Volume is %i' % self.player['volume'])
        self.logger.info('Squeze Daemon started')

        # start amp if running on start
        self._amp_on_start()


    def _amp_on_start(self):
	# start amp if player is running
	if self.is_running():
            self.logger.debug('player %s is running, turning amp on' % self.player['name'])
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            try:
                s.connect((amp_host, amp_port))
                logger.debug('Connected to amp on host %s, port: %i' % (amp_host, amp_port) )
                s.send("%s\n" % 'AmpON')
                logger.info("Amp Turned on")
                s.close()
                del s
            except :
                self.logger.debug('Unable to connect to amp host:%s' % amp_host)

    def js_request(self,params):
        json_string = {
                "id": 1,
                "method": "slim.request",
                "params": params,
        }

        header = {
            'Content-Type': 'application/json',
            'User-Agent': 'tpi',
            'Accept': 'application/json',
        }

        # craft the request for a url
        req = urllib2.Request(url, json.dumps(json_string), headers=header)

        # send the request, return json as object
        res = urllib2.urlopen(req)
        return  json.loads(res.read())

    def _get_player(self,name):
            """ how mayn players are there """
            player = self.js_request(["",["players","0",]])['result']
            for play in player['players_loop']:
                if play['isplayer'] == 1 and play['name'] == name:
                    logger.debug("found player: %s" % play['name'])
                    return play
            self.logger.error("Player %s not found" % name)

    def _get_volume(self):
        """ gets volume for player """
        self.player['volume'] = int(float(self.js_request([self.player['playerid'],["mixer","volume","?"]])['result']['_volume']))


    def volume(self):
        """ return volume """
        self._get_volume()
        return self.player['volume']


    def vol_up(self,value):
        """ increase Volume """
        self.js_request([self.player['playerid'],["mixer","volume","+" + str(value)]])
        logger.debug("Volumne is: %i" % self.volume())

    def vol_down(self,value):
        """ increase Volume """
        self.js_request([self.player['playerid'],["mixer","volume","-" + str(value)]])
        logger.debug("Volumne is: %i" % self.volume())

    def mute(self):
        self._get_volume()
        self.js_request([self.player['playerid'],["mixer","volume","0"]])

    def pause(self):
        self.js_request([self.player['playerid'],["pause"]])
        logger.debug("Stopped player %s" % self.player['name'])

    def play(self):
        self.js_request([self.player['playerid'],["play"]])
        logger.debug("Started player %s" % self.player['name'])

    def is_running(self):
        mode =  self.js_request([self.player['playerid'],["mode","?"]])['result']['_mode']
        if mode == 'play':
            return True
        else:
            return False


class   MyRotary:
    def __init__(self,logger=None):
        """ Encoder Controlling Class"""
        self.logger = logger or logging.getLogger(__name__)
        self.Current_A = 1
        self.Current_B = 1
        self.LockRotary = Lock()      # create lock for rotary switch

        GPIO.setup(RoAPin, GPIO.IN)    # input mode
        GPIO.setup(RoBPin, GPIO.IN)
        GPIO.setup(RoSPin,GPIO.IN,pull_up_down=GPIO.PUD_UP)

        GPIO.add_event_detect(RoAPin, GPIO.RISING, callback=self.rotate)
        GPIO.add_event_detect(RoBPin, GPIO.RISING, callback=self.rotate)
        GPIO.add_event_detect(RoSPin, GPIO.FALLING, callback=self.stop_start, bouncetime=2000) # wait for falling

    def rotate(self,A_or_B):

        # read both of the switches
        Switch_A = GPIO.input(RoAPin)
        Switch_B = GPIO.input(RoBPin)
                                                                          # now check if state of A or B has changed
                                                                          # if not that means that bouncing caused it
        if self.Current_A == Switch_A and self.Current_B == Switch_B:      # Same interrupt as before (Bouncing)?
          return                              # ignore interrupt!

        self.Current_A = Switch_A                        # remember new state
        self.Current_B = Switch_B                        # for next bouncing check


        if (Switch_A and Switch_B):                  # Both one active? Yes -> end of sequence
          self.LockRotary.acquire()                  # get lock 
          if A_or_B == RoBPin:                     # Turning direction depends on 
            # its going DOWN
            ds.reset()
            sq.vol_down(stepper) 
          else:                              # so depending on direction either
            # its going UP
            ds.reset()
            sq.vol_up(stepper) 
          self.LockRotary.release()                  # and release lock
        return                                 # THAT'S IT

    def stop_start(self,ev=None):
        ds.reset()
        if sq.is_running():
            sq.pause()
        else:
            sq.play()


class Reboot:
    def __init__(self,logger=None):
        """ Rebooting on Button """
        self.CountLock = Lock()
        self.count = 0
        self.maxcount = 3
        self.timer = 0
        self.maxtime = 10
        self.counting = False
        self.logger = logger or logging.getLogger(__name__)

        GPIO.setup(rebootPin, GPIO.IN,pull_up_down=GPIO.PUD_DOWN)    
        GPIO.add_event_detect(rebootPin, GPIO.RISING, callback=self.handle, bouncetime=500)

    def handle(self,args):
        self.count += 1
        self.logger.debug("reboot count %i" % self.count)

        if self.count == 1:
            t = Thread(target=self._sleeper, args=())
            t.start()

    def _sleeper(self):
        self.logger.debug("Creating Reboot Counter")
        while self.timer < self.maxtime:

            # reboot if count >3
            if self.count >= self.maxcount:
                self.count = self.maxcount
                self.reboot()
                break

            self.CountLock.acquire()
            self.timer += 1
            self.logger.debug("Reseting: %i" % self.timer)
            self.CountLock.release()
            time.sleep(1) 

        self.logger.debug("reseting reboot count")
        self.count = 0
        self.timer = 0


    def reboot(self):
        self.logger.debug("REBOOTING")
        cow = subprocess.check_output(["/usr/games/cowsay", "REBOOT"])
        fd = os.open('/dev/tty1', os.O_WRONLY | os.O_NOCTTY) 
        tty = os.fdopen(fd, 'w', 1)
        del fd
        for i in range(120):
            tty.write("\n")
        tty.write(cow)
        for i in range(20):
            tty.write("\n")
        ds.change_vt(1)
        time.sleep(2)
        if do_reboot:
            subprocess.call(["/sbin/reboot"])
        else:
            ds.change_vt(display_vt)





if __name__ == '__main__':     # Program start from here

    GPIO.setmode(GPIO.BOARD)       # Numbers GPIOs by physical location

    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)

    # main reboot handling
    Reboot()


    sq = MySqueeze(player_name)
    rt = MyRotary()
    ds = Display(60)

    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:  # When 'Ctrl+C' is pressed, the child program destroy() will be  executed.
        ds.destroy()
        GPIO.cleanup()             # Release resource

