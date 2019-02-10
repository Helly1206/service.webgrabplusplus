# -*- coding: utf-8 -*-
#########################################################
# SCRIPT  : script.py                                   #
#           Script handling commands for WebGrab++      #
#           I. Helwegen 2015                            #
#########################################################

####################### IMPORTS #########################
import sys, os
import xbmc, xbmcaddon, xbmcgui
import re
import socket
#########################################################

####################### GLOBALS #########################
__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('id')
__addonpath__ = __addon__.getAddonInfo('path')
__LS__ = __addon__.getLocalizedString
__lib__ = xbmc.translatePath( os.path.join( __addonpath__, 'resources', 'lib' ).encode("utf-8") ).decode("utf-8")

sys.path.append(__lib__)
import common
import progress

### CONTROLS ###
BUTTON_FORCE   = 10
BUTTON_EXIT    = 20
PROGRESS_GRAB  = 40
LABEL_TITLE    = 15
LABEL_STATUS   = 30
LABEL_NEXT     = 32
LABEL_CHANNEL  = 34
LABEL_PROGRESS = 36
LABEL_LATEST   = 51
LABEL_SECONDS  = 54
LABEL_SHOWS    = 56
LABEL_CHANNELS = 58
LABEL_NEW      = 60
LABEL_UPDATED  = 62

FIELD_STATUS   = 31
FIELD_NEXT     = 33
FIELD_CHANNEL  = 35
FIELD_PROGRESS = 37
FIELD_LATEST   = 52
FIELD_SECONDS  = 53
FIELD_SHOWS    = 55
FIELD_CHANNELS = 57
FIELD_NEW      = 59
FIELD_UPDATED  = 61

UPDATE_TIME = 5

CANCEL_DIALOG = (9, 10, 216, 247, 257, 275, 61448, 61467)

SOCKET_TIMEOUT = 20000

class GUI(xbmcgui.WindowXMLDialog):
	
    def __init__(self, *args, **kwargs):
        self.rt = None
        self.percent = 0
        self.Status = common.STAT_UNKNOWN
        self.OldStatus = common.STAT_UNKNOWN
        self.getSettings()
        self.LogInfo = progress.LogFile(self.__epg_interval,self.__wg_logfile)
        self.WGInfoOld = progress.WGInfo()
        
        ### read addon settings

    def getSettings(self):
        try:
            self.__epg_interval = int(re.match('\d+', __addon__.getSetting('epg_interval')).group())
        except:
            self.__epg_interval = 0
        self.__wg_logfile = __addon__.getSetting('wg_logfile')
      
    def onInit(self):
        self.getControl(LABEL_TITLE).setLabel(__LS__(30100))

        self.getControl(LABEL_STATUS).setLabel(__LS__(30101))
        self.getControl(LABEL_NEXT).setLabel(__LS__(30102))
        self.getControl(LABEL_CHANNEL).setLabel(__LS__(30103))
        self.getControl(LABEL_PROGRESS).setLabel(__LS__(30104))
        self.getControl(LABEL_LATEST).setLabel(__LS__(30105))
        self.getControl(LABEL_SECONDS).setLabel(__LS__(30106))
        self.getControl(LABEL_SHOWS).setLabel(__LS__(30107))
        self.getControl(LABEL_CHANNELS).setLabel(__LS__(30108))
        self.getControl(LABEL_NEW).setLabel(__LS__(30109))
        self.getControl(LABEL_UPDATED).setLabel(__LS__(30110))
        self.getControl(BUTTON_FORCE).setLabel(__LS__(30111))
        self.getControl(BUTTON_FORCE).setEnabled(False)

        if self.CheckService(False):
             self.rt = common.RepeatedTimer(UPDATE_TIME, self.CheckService, [self, True])

    def onClick(self, controlId):
        if (controlId == BUTTON_FORCE):
            self.getControl(BUTTON_FORCE).setEnabled(False)
            common.writeLog("Force Grabbing ....")
            common.DoComm(common.CMD_FORCESTART)
        if (controlId == BUTTON_EXIT):
            self.ExitScript()

    def onAction(self, action):
        if (action.getButtonCode() in CANCEL_DIALOG):
            self.ExitScript()

    def ExitScript(self):
        common.writeLog("Exit script")
        if self.rt != None:
            self.rt.stop()
        del self.LogInfo
        del self.WGInfoOld
        self.close()

    def CheckService(self, Timed):
        if not common.IsRunning():
            common.notifyOSD(__LS__(30001), __LS__(30002), common.IconError)
            self.getControl(FIELD_STATUS).setLabel(__LS__(30115))
            if self.rt != None:
                self.rt.stop()
            return False
        self.DisplayStatus()
        if not Timed:
            # First run, get everything and read logfile...
            self.LogInfo.ReadLogFile()
            self.WGInfoOld = self.LogInfo.CopyLog(self.WGInfoOld)
            self.LogInfo.ReadLogFile(True)
            self.DisplayNextGrab()
            self.DisplayProgress()
            self.DisplayPrevInfo()
            self.OldStatus = self.Status
            if (self.Status == common.STAT_IDLE):
                self.getControl(BUTTON_FORCE).setEnabled(True)
        else:
            # Check timed      
            if (self.Status != self.OldStatus):
                # Status changed, if grabbing, only read current logfile and keep old
                if (self.Status == common.STAT_GRABBING):
                    self.getControl(BUTTON_FORCE).setEnabled(False)
                    self.LogInfo.ReadLogFile(True)
                    self.DisplayNextGrab()
                    self.DisplayProgress()                       
                # if idle, read log and copy once
                elif (self.Status == common.STAT_IDLE):
                    self.getControl(BUTTON_FORCE).setEnabled(True)
                    self.LogInfo.ReadLogFile()
                    self.WGInfoOld = self.LogInfo.CopyLog(self.WGInfoOld)
                    self.DisplayNextGrab()
                    self.DisplayProgress()   
                    self.DisplayPrevInfo()
            elif (self.Status == common.STAT_GRABBING):
                # Read current logfile
                self.LogInfo.ReadLogFile(True)
                self.DisplayProgress()
            self.OldStatus = self.Status
        return True

    def DisplayStatus(self):
        self.Status = common.ParseStatus(common.DoComm(common.CMD_GETSTATUS))
        if (self.Status == common.STAT_UNKNOWN):
            self.getControl(FIELD_STATUS).setLabel(__LS__(30112))
        elif (self.Status == common.STAT_GRABBING):
            self.getControl(FIELD_STATUS).setLabel(__LS__(30113))
        elif (self.Status == common.STAT_IDLE):
            self.getControl(FIELD_STATUS).setLabel(__LS__(30114))
        elif (self.Status == common.STAT_ERROR):
            self.getControl(FIELD_STATUS).setLabel(__LS__(30115))
        elif (self.Status == common.STAT_POSTPROC):
            self.getControl(FIELD_STATUS).setLabel(__LS__(30116))
        return

    def DisplayNextGrab(self):
        if self.Status == common.STAT_GRABBING:
            inextgrab = self.LogInfo.Epoch2Date(0)
        else:
            inextgrab = self.LogInfo.Epoch2Date(self.LogInfo.CalcNextUpdate())
        self.getControl(FIELD_NEXT).setLabel(inextgrab)
        return

    def DisplayProgress(self):
        iChannel = self.LogInfo.WGInfo.Channel
        iCurrent = self.LogInfo.WGInfo.ChannelCounter
        iAmount = self.LogInfo.WGInfo.Channels
        if (self.Status == common.STAT_GRABBING):
            self.getControl(FIELD_CHANNEL).setLabel(iChannel)
            self.getControl(FIELD_PROGRESS).setLabel("%d/ %d"%(iCurrent, iAmount))
        else:
            self.getControl(FIELD_CHANNEL).setLabel("None")
            self.getControl(FIELD_PROGRESS).setLabel("-")
        self.getControl(PROGRESS_GRAB).setPercent(common.CalcProgress(iCurrent, iAmount))
        return iCurrent, iAmount 

    def DisplayPrevInfo(self):
        iLatest = self.LogInfo.Epoch2Dates(self.WGInfoOld.FinishedTime)
        iSeconds = self.WGInfoOld.Duration
        iShows = self.WGInfoOld.Shows 
        iChannels = self.WGInfoOld.TotalChannels
        iNew = self.WGInfoOld.New 
        iUpdated = self.WGInfoOld.Updated
        self.getControl(FIELD_LATEST).setLabel(" %s"%iLatest)
        self.getControl(FIELD_SECONDS).setLabel(str(iSeconds))
        self.getControl(FIELD_SHOWS).setLabel(str(iShows))
        self.getControl(FIELD_CHANNELS).setLabel(str(iChannels))
        self.getControl(FIELD_NEW).setLabel(str(iNew))
        self.getControl(FIELD_UPDATED).setLabel(str(iUpdated))
        return

#########################################################

def PrintHelp():
    writeLog("WebGrab++ Manager Usage: ")
    writeLog("No arguments: GUI controlled, with arguments: external access")
    writeLog("-h: show this help")
    writeLog("-s: Get status from service")
    writeLog("-g: Manually start grabbing")
    
def SocketMsg(msg):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port = int(__addon__.getSetting('socket_port'))
        s.connect(('localhost', port))
        s.send(msg)
        s.close()
    except:
        common.writeLog("[Remote] Error sending return message: %s"%msg)



#########################################################
######################## MAIN ###########################
#########################################################
if len(sys.argv) > 1:
    if sys.argv[1].lower() == "-h":
        PrintHelp()
    elif sys.argv[1].lower() == "-l": ## Just for testing, remove later
        SocketMsg("I'm alive !!!!")
        common.writeLog("[Remote] Testing communication ...")
    elif sys.argv[1].lower() == "-s":
        if common.IsRunning():
            status = common.DoComm(common.CMD_GETSTATUS)
            SocketMsg(status)
            #common.writeLog("[Remote] Get Status: %s"%status)
        else:
            SocketMsg("<Error>")
            common.writeLog("[Remote] Get Status")
            common.writeLog("Error: Service not running ...")
    elif sys.argv[1].lower() == "-g":
        common.writeLog("[Remote] Start Grabbing ...")
        if common.IsRunning():
            common.DoComm(common.CMD_FORCESTART)
            SocketMsg("<Ready>")
        else:
            SocketMsg("<Error>")
            common.writeLog("Error: Service not running ...")
    else:
        common.writeLog("Invalid option: %s" % sys.argv[1])
        SocketMsg("<Error>")
else:
    __gui_type = "Classic" if __addon__.getSetting('gui_type').upper() == 'CLASSIC' else "Default"
    ui = GUI("%s.xml" % __addonname__.replace(".","-") , __addonpath__, __gui_type)
    ui.doModal()
    del ui

