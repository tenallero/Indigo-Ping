#! /usr/bin/env python
# -*- coding: utf-8 -*-
#######################

import os
import sys
import indigo
import math
import decimal
import datetime
import socket
import subprocess

class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

            
        self.apiVersion    = "2.0"
        self.localAddress  = ""

        # create empty device list      
        self.deviceList = {}
        
    def __del__(self):
        indigo.PluginBase.__del__(self)     

    ###################################################################
    # Plugin
    ###################################################################

    def deviceStartComm(self, device):
        self.debugLog(u"Started device: " + device.name)
        self.addDeviceToList (device)

    def deviceStopComm(self,device):
        if device.id in self.deviceList:
            self.debugLog("Stoping device: " + device.name)
            del self.deviceList[device.id]

    def deviceCreated(self, device):
        self.debugLog(u'Created device "' + device.name)
        pass

    def addDeviceToList(self,device):        
        if device.id not in self.deviceList:    
            propsAddress = device.pluginProps["address"]                    
            propsAddress = propsAddress.strip() 
            propsAddress = propsAddress.replace (' ','')
            pingNextTime = datetime.datetime.now() - datetime.timedelta(seconds=10)
            pingInterval = device.pluginProps["pingInterval"]
            self.deviceList[device.id] = {'ref':device, 'address':propsAddress, 'pingInterval':pingInterval, 'pingNextTime': pingNextTime}       

    def startup(self):
        self.loadPluginPrefs()
        self.debugLog(u"startup called")

    def shutdown(self):
        self.debugLog(u"shutdown called")

    def getDeviceConfigUiValues(self, pluginProps, typeId, devId):
        valuesDict = pluginProps
        errorMsgDict = indigo.Dict()
        if "pingInterval" not in valuesDict:
            valuesDict["pingInterval"] = 300        
        return (valuesDict, errorMsgDict)

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        self.debugLog(u"validating device Prefs called")    
        
        self.debugLog(u"validating IP Address") 
        ipAdr = valuesDict[u'address']
        if ipAdr.count('.') != 3:
            errorMsgDict = indigo.Dict()
            errorMsgDict[u'address'] = u"This needs to be a valid IP address."
            return (False, valuesDict, errorMsgDict)
        if self.validateAddress (ipAdr) == False:
            errorMsgDict = indigo.Dict()
            errorMsgDict[u'address'] = u"This needs to be a valid IP address."
            return (False, valuesDict, errorMsgDict)
        pingInterval = valuesDict[u'pingInterval']
        try:
            iInterval = int (pingInterval)
            if iInterval < 1:
                errorMsgDict = indigo.Dict()
                errorMsgDict[u'pingInterval'] = u"This needs to be > 0."
                return False
        except Exception, e:
            errorMsgDict = indigo.Dict()
            errorMsgDict[u'pingInterval'] = u"This needs to be a valid number."
            return False
        return (True, valuesDict)

    def validatePrefsConfigUi(self, valuesDict):        
        return (True, valuesDict)

    def closedDeviceConfigUi(self, valuesDict, userCancelled, typeId, devId):
        if userCancelled is False:
            indigo.server.log ("Device preferences were updated.")
            del self.deviceList[devId]
            self.addDeviceToList (device)

    def closedPrefsConfigUi ( self, valuesDict, UserCancelled):
        #   If the user saves the preferences, reload the preferences
        if UserCancelled is False:
            indigo.server.log ("Preferences were updated, reloading Preferences...")
            self.loadPluginPrefs()

    def loadPluginPrefs(self):
        # set debug option
        if 'debugEnabled' in self.pluginPrefs:
            self.debug = self.pluginPrefs['debugEnabled']
        else:
            self.debug = False        
        
    def validateAddress (self,value):
        try:
            socket.inet_aton(value)
        except socket.error:
            return False
        return True
    
    ###################################################################
    # Concurrent Thread.
    ###################################################################

    def runConcurrentThread(self):

        self.debugLog(u"Starting Concurrent Thread")
        
        try:
            while self.stopThread == False: 
                indigoDevice = None
                try:
                    todayNow = datetime.datetime.now()
                    for pingDevice in self.deviceList:
                        pingNextTime = self.deviceList[pingDevice]['pingNextTime']

                        if pingNextTime <= todayNow:                            
                            pingInterval = self.deviceList[pingDevice]['pingInterval']
                            pingNextTime = todayNow + datetime.timedelta(seconds=int(pingInterval))
                            self.deviceList[pingDevice]['pingNextTime'] = pingNextTime                         

                            indigoDevice = self.deviceList[pingDevice]['ref']                           
                            self.deviceRequestStatus(indigoDevice)
                            
                except Exception,e:
                    self.errorLog (u"Error: " + str(e))
                    pass
                self.sleep(1)
            

        except self.StopThread:
            pass

        except Exception, e:
            self.errorLog (u"Error: " + str(e))
            pass    

    def stopConcurrentThread(self):
        self.stopThread = True
        self.debugLog(u"stopConcurrentThread called")
    

    ###################################################################
    # Custom Action callbacks
    ###################################################################

    def deviceRequestStatus(self,dev):    
        newValue = self.pingDevice(dev)
        if not newValue == dev.states['onOffState']:
           dev.updateStateOnServer(key='onOffState', value=newValue)
           if newValue:
                indigo.server.log (dev.name + u" is now up!")        
           else:
                indigo.server.log (dev.name + u" is down!")        
           pass
  
    def pingDevice (self,device):
        if device.id in self.deviceList:
            pingAddress  = self.deviceList[device.id]['address']
            return self.pingAddress(pingAddress)        
        return False

    def pingAddress (self, address):
        self.debugLog(u"Pinging address " + address + " ...")
        try:
            ret = 0
            ret = subprocess.call(["/sbin/ping", "-c", "4", "-t", "2", address], stdout = subprocess.PIPE, stderr = subprocess.PIPE)
            if ret == 0:
                self.debugLog(address + u": is reachable.")
                return True
            else:
                if ret == 1:
                    self.debugLog(address + u": host not found")
                elif ret == 2:
                    self.debugLog(address + u": ping timed out")
                self.debugLog(u"Ping result: Failure")
                return False
        except Exception, e:
            return False                       
       
    def actionControlSensor(self, action, dev):
        if action.sensorAction == indigo.kSensorAction.RequestStatus:
            self.deviceRequestStatus(dev)
            indigo.server.log ('sent "' + dev.name + '" status request')
            pass