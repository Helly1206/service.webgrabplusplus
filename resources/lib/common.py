# -*- coding: utf-8 -*-
#########################################################
# SCRIPT  : common.py                                   #
#           Common functions for WebGrab++              #
#           I. Helwegen 2016                            #
#########################################################

####################### IMPORTS #########################
import os, subprocess
import xbmc, xbmcaddon, xbmcgui
import time, datetime
from threading import Timer

#########################################################

####################### GLOBALS #########################
__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('id')
__path__ = __addon__.getAddonInfo('path')
__datapath__ = xbmc.translatePath(os.path.join('special://temp/', __addonname__))
__logfile__ = os.path.join(__datapath__, __addonname__ + '.log')

IconStop = xbmc.translatePath(os.path.join(__path__, 'resources', 'media', 'stop.png'))
IconError = xbmc.translatePath(os.path.join(__path__, 'resources', 'media', 'error.png'))
IconInfo = xbmc.translatePath(os.path.join(__path__, 'resources', 'media', 'wginfo.png'))

# parameters
CMD     = 'command'
RESP    = 'response'
MSG     = 'message'
MSGCNT  = 'mescount'
SERVRUN = 'servrun'
EMPTYPARAM = ''

# service methods
CMD_NONE        = 0
CMD_FORCESTART  = 1
CMD_GETSTATUS   = 2

#status
STAT_UNKNOWN  = 0
STAT_GRABBING = 1
STAT_POSTPROC = 2
STAT_IDLE     = 3
STAT_ERROR    = 4

MAX_RETRIES = 3
MAX_WAIT_LOOP = 2
COMMAND_LOOP = 1000

OSD = xbmcgui.Dialog()

__parameterwindow__ = 10000
#########################################################

#########################################################
# Functions : Local                                     #
#########################################################
def num(s):
    try:
        return int(s)
    except ValueError:
        return 0

def setParam(param, value):
    xbmcgui.Window(__parameterwindow__).setProperty(__addonname__ + '_' + param, value)

def getParam(param):
    return xbmcgui.Window(__parameterwindow__).getProperty(__addonname__ + '_' + param)

def clearParam(param):
    xbmcgui.Window(__parameterwindow__).clearProperty(__addonname__ + '_' + param)

def incParam(param):
    val = num(getParam(param))
    val += 1
    setParam(param,str(val))
#########################################################

#########################################################
# Functions : Global                                    #
#########################################################
class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False
        
class ExecuteCmd(object):
    def __init__(self):
        self.process = None

    def Run(self, command):
        self.process = subprocess.Popen(command, shell=False)
        return (self.process.pid)       
    
    def Busy(self):
        if self.process == None:
            return None
        else:
            PollVal = self.process.poll()
            if (PollVal != None):
                del self.process
                self.process = None           
            return (PollVal)  
            
    def Kill(self):
        if self.process == None:
            return
        else:
            self.process.terminate()
        del self.process
        self.process = None
            
def IsRunning():
    Running = getParam(SERVRUN)
    if Running == EMPTYPARAM:
        return False
    else:
        return True

def Run():
    setParam(SERVRUN,"Running")

def Stop():
    clearParam(SERVRUN)

def getCommand():
    cmd=num(getParam(CMD))
    clearParam(CMD)
    return cmd

def setCommand(methd):
    if methd == CMD_NONE:
        clearParam(CMD)
    else:
        setParam(CMD,str(methd))

def getResponse():
    respstr=getParam(RESP)
    if (respstr != EMPTYPARAM):
        clearParam(RESP)
    return respstr

def setResponse(respstr):
    if respstr == EMPTYPARAM:
        clearParam(RESP)
    else:
        setParam(RESP,respstr)

def DoComm(methd):
    retries = 0
    setCommand(methd)
    #wait for command accepted
    while True:
        if (getParam(CMD) != EMPTYPARAM) and (retries < MAX_WAIT_LOOP):
            xbmc.sleep(COMMAND_LOOP)
            retries += 1
        else:
            if (getParam(CMD) != EMPTYPARAM):
                return EMPTYPARAM
            break
    retries = 0
    #wait for response
    while True:
        respstr=getResponse()
        if (respstr == EMPTYPARAM) and (retries < MAX_RETRIES):
            xbmc.sleep(COMMAND_LOOP)
            retries += 1
        else:
            break
    return respstr

def BuildStatus(Status):
    # Status#
    return ("%s"%(str(Status)))

def ParseStatus(StatusStr):
    # Status#
    Status = STAT_UNKNOWN
    if StatusStr != None:
        Status = num(StatusStr)
    return (Status)
    
def CalcProgress(iCurr, iMax):
    if (iMax == 0):
        return 0
    return int(iCurr*100/iMax)    

def notifyOSD(header, message, icon=xbmcgui.NOTIFICATION_INFO):
    OSD.notification(header.encode('utf-8'), message.encode('utf-8'), icon)

def writeLog(message, level=xbmc.LOGNOTICE, forcePrint=False):
    if getParam(MSG) == message and not forcePrint:
        incParam(MSGCNT)
        return
    else:
        try:
            if not os.path.exists(__datapath__): os.makedirs(__datapath__)
            if not os.path.isfile(__logfile__):
                __f = open(__logfile__, 'w')
            else:
                __f = open(__logfile__, 'a')
            if num(getParam(MSGCNT)) > 0:
                __f.write('%s: >>> Last message repeated %s time(s)\n' % (
                    datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S'), num(getParam(MSGCNT))))
            setParam(MSG, message)
            clearParam(MSGCNT)
            __f.write('%s: %s\n' % (datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S'), message.encode('utf-8')))
            __f.close()
        except Exception, e:
            xbmc.log('%s: %s' % (__addonname__, e), xbmc.LOGERROR)
        xbmc.log('%s: %s' % (__addonname__, message.encode('utf-8')), level)    

#########################################################
