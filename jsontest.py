#!/usr/bin/python

import json
import urllib2


url = 'http://rpi:9000/jsonrpc.js'
player_id = 'b8:27:eb:3d:83:04'


def js_request(params):
    json_string = {
            "id": 1,
            "method": "slim.request",
            "params": [player_id, params],
    }

    header = {
        'Content-Type': 'application/json',
        'User-Agent': 'tpi',
        'Accept': 'application/json',
    }

    # craft the request for a url
    req = urllib2.Request(url, json.dumps(json_string), headers=header)

    # send the request
    res = urllib2.urlopen(req)
    return  json.loads(res.read())

def js_request2(params):
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

    # send the request
    res = urllib2.urlopen(req)
    return  json.loads(res.read())


def vol_up(value):
        js_request(["mixer","volume","+" + str(value)])

def vol_down(value):
        js_request(["mixer","volume","-" + str(value)])

def get_vol():
        return int(js_request(["mixer","volume","?"])['result']['_volume'])
        
def pause():
        return js_request(["pause"])

def play():
        return js_request(["play"])

def mode():
        return js_request(["mode","?"])

def serverstatus():
        """ {"id":1,"method":"slim.request","params":["",["serverstatus",0,999]]} """
        response =  js_request2(["",["serverstatus",0,999]])
        for player in response['result']['players_loop']:
            print "player", player['name'], player['playerid']

if __name__ == "__main__":
       #print mode()
       serverstatus()
