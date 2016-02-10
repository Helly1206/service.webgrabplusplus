# -*- coding: utf-8 -*-
#########################################################
# SERVICE : default.py                                  #
#           PVR-Manager service                         #
#           I. Helwegen 2015                            #
#########################################################

####################### IMPORTS #########################
import sys, os, platform
import socket
import re
import random
import xbmc, xbmcaddon, xbmcgui
import shutil
import socket
#########################################################

####################### GLOBALS #########################
__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('id')
__path__ = __addon__.getAddonInfo('path')
__version__ = __addon__.getAddonInfo('version')
__LS__ = __addon__.getLocalizedString
__lib__ = xbmc.translatePath( os.path.join( __path__, 'resources', 'lib' ).encode("utf-8") ).decode("utf-8")

sys.path.append(__lib__)
import common
import progress

SCHEDULERTIME = 10

PB_BUSY = 0
PB_CANCELED = 1

CMD_FORCEGRAB = "FG"
CMD_REQSTATUS = "S?"
CMD_CONNQUIT  = "CQ"
SOCKET_TIMEOUT = 20

#PLATFORM_OE = True if ('OPENELEC' in ', '.join(platform.uname()).upper()) else False

#########################################################
# Class : WGProgressBar                                 #
#########################################################
class WGProgressBar(object):
    def __init__(self):
        self.header = __LS__(30000)
        self.message = __LS__(30005)
        self.pb = xbmcgui.DialogProgressBG()

    def Create(self, Current, Amount):
        self.pb.create(self.header,self.message % (Current, Amount))
        self.pb.update(common.CalcProgress(Current, Amount))       
        return 

    def Update(self, Current, Amount):
        self.pb.update(common.CalcProgress(Current, Amount), self.header, self.message % (Current, Amount))
        return

    def Close(self):
        self.pb.close()

class SocketChannel(object):
    def __init__(self, port):
        self.sock = None
        self.ss = None
        self.port = port
        self.Open()
        self.Counter=0
        
    def Open(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('localhost', self.port))
        self.sock.listen(5) # become a server socket, maximum 5 connections
        self.sock.setblocking(False)
    
    def TryConn(self):
        Success = False
        if self.ss != None:
            Success = True
        else:
            try:
                self.ss,sockname = self.sock.accept()
                self.ss.settimeout(0.05)
                self.Counter = 0
                common.writeLog("[Remote] Socket connection established to: %s"%str(sockname))
                Success = True
            except socket.error, e:
                #common.writeLog("[Remote] Error socket connection: %s"%e)
                if self.ss != None:
                    self.ss.close()
                    self.ss = None
                Success = False
        return Success
    
    def Receive(self):
        msg = None
        try: 
            msg = self.ss.recv(63)
        except socket.timeout:
            msg = None
        except socket.error, e:
            msg = None
            common.writeLog("[Remote] Error socket connection: %s"%e)
            if self.ss != None:
                self.ss.close()
                self.ss = None
        else:
            if len(msg) == 0:
                msg = None
                if (self.Counter < SOCKET_TIMEOUT):
                    self.Counter += 1
                else:
                    if self.ss != None:
                        self.ss.close()
                        self.ss = None
                    common.writeLog("[Remote] Socket connection closed by timeout")
            else:
                if (msg == CMD_CONNQUIT):
                    if self.ss != None:
                        self.ss.close()
                        self.ss = None
                    common.writeLog("[Remote] Socket connection closed")
                    msg = None
                else:
                    self.Counter = 0
        return msg
    
    def Send(self,msg):
        try:
            self.ss.send(msg)
        except socket.error, e:
            common.writeLog("[Remote] Error socket connection: %s"%e)
            self.ss = None
    
    def Close(self):
        self.sock.close()
        self.sock = None

#########################################################
# Class : Manager                                       #
#########################################################
### MAIN CLASS
class Manager(object):
    def __init__(self):
        self.__rndProcNum = random.randint(1, 1024)
        self.Command = common.ExecuteCmd()
        self.__CompChannelCounter = 0
        self.__GrabFailed = False
        self.__ProgressBar = None
        self.__NextUpdate = 0
        self.__Status = common.STAT_UNKNOWN
        self.__TimeOutTime = 0
        self.getSettings()
        self.LogInfo = progress.LogFile(self.__epg_interval, self.__wg_logfile)
        self.SockComm = SocketChannel(self.__socket_port)
        self.__StartupTime = self.LogInfo.EpochGetNow()

    ### read addon settings

    def getSettings(self):
        try:
            self.__epg_interval = int(re.match('\d+', __addon__.getSetting('epg_interval')).group())
        except:
            self.__epg_interval = 0
        try:
            self.__hang_detection = int(re.match('\d+', __addon__.getSetting('hang_detection')).group())
        except:
            self.__hang_detection = 0
        self.__progressbar_status = True if __addon__.getSetting('progressbar_status').upper() == 'TRUE' else False
        self.__notify_status = True if __addon__.getSetting('notify_status').upper() == 'TRUE' else False
        self.__backup_xml = True if __addon__.getSetting('backup_xml').upper() == 'TRUE' else False
        self.__wg_script = __addon__.getSetting('wg_script')
        self.__wg_logfile = __addon__.getSetting('wg_logfile')
        self.__wg_xmlfile = __addon__.getSetting('wg_xmlfile')
        self.__sck_transfer = True if __addon__.getSetting('sck_transfer').upper() == 'TRUE' else False
        self.__sck_url = __addon__.getSetting('sck_url')
        self.__post_transfer = True if __addon__.getSetting('post_transfer').upper() == 'TRUE' else False
        self.__post_script = __addon__.getSetting('post_script')
        self.__update_kodi = True if __addon__.getSetting('update_kodi').upper() == 'TRUE' else False
        self.__not_update_running = True if __addon__.getSetting('not_update_running').upper() == 'TRUE' else False 
        self.__socket_port = int(__addon__.getSetting('socket_port'))      

    def GetAndExecuteCommand(self):
        Command = common.getCommand()
        if (Command == common.CMD_FORCESTART):
            if (self.__Status == common.STAT_IDLE):
                self.__NextUpdate = self.LogInfo.EpochGetNow()
                common.setResponse("Done")
            else:
                common.setResponse("Busy")
        elif (Command == common.CMD_GETSTATUS):
            common.setResponse(common.BuildStatus(self.__Status))
            
    def GetAndExecuteSockCommand(self):
        if self.SockComm.TryConn():
            Command = self.SockComm.Receive()
            #common.writeLog('Command: %s'%Command)
            if Command == None:
                return
            if (Command == CMD_FORCEGRAB):
                if (self.__Status == common.STAT_IDLE):
                    self.__NextUpdate = self.LogInfo.EpochGetNow()
                    self.SockComm.Send("Done")
                else:
                    self.SockComm.Send("Busy")
            elif (Command == CMD_REQSTATUS):
                self.SockComm.Send(common.BuildStatus(self.__Status))
                
    def CalcTimeOut(self):
        if self.__hang_detection == 0:
            self.__TimeOutTime = 0
        else:
            self.__TimeOutTime = self.LogInfo.EpochGetNow() + (self.__hang_detection*60)
            
    def StartGrabbing(self, try2):
        Failed = False
        if try2 == False: # first try
            # Copy logfile to old
            if os.path.exists(self.__wg_logfile):
                shutil.copy(self.__wg_logfile, "%s.old"%(self.__wg_logfile))
            else:
                common.writeLog("log-file not found, no copy made",xbmc.LOGWARNING)
            # Make backup
            if self.__backup_xml == True:
                if os.path.exists(self.__wg_xmlfile):
                    shutil.copy(self.__wg_xmlfile, "%s.bak"%(self.__wg_xmlfile))
                else:
                    common.writeLog("xml-file not found, no backup made",xbmc.LOGERROR)
                    common.notifyOSD(__LS__(30006), __LS__(30007), common.IconStop)
            # try scan
            if os.path.exists(self.__wg_script):
                self.Command.Run([self.__wg_script])
            else:
                common.writeLog("EPG-update script not found",xbmc.LOGERROR)
                common.notifyOSD(__LS__(30006), __LS__(30008), common.IconError)   
                Failed = True 
        else: # second try
            # use fallback backup if failed
            if self.__backup_xml == True:
                if os.path.exists("%s.fallback"%(self.__wg_xmlfile)):
                    common.writeLog("Try again using fallback xml-file",xbmc.LOGWARNING)
                    shutil.move("%s.fallback"%(self.__wg_xmlfile),self.__wg_xmlfile)
                else:
                    common.writeLog("No fallback file found: Delete xml-file and try again with full grab",xbmc.LOGWARNING)
                    if os.path.exists(self.__wg_xmlfile):
                        os.remove(self.__wg_xmlfile)
                    else:
                        common.writeLog("No xml-file found to remove")
            else:
                common.writeLog("No backup set: Delete xml-file and try again with full",xbmc.LOGWARNING)
                if os.path.exists(self.__wg_xmlfile):
                    os.remove(self.__wg_xmlfile)
                else:
                   common.writeLog("No xml-file found to remove")
            if os.path.exists(self.__wg_script):
                self.Command.Run([self.__wg_script])
            else:
                common.writeLog("EPG-update script not found",xbmc.LOGERROR)
                common.notifyOSD(__LS__(30006), __LS__(30008), common.IconError)  
                Failed = True      
        return Failed 
                
    def GrabPre(self):
        self.getSettings()
        self.CalcTimeOut()
        self.__CompChannelCounter = 0
        #start
        self.__GrabFailed = self.StartGrabbing(False)
        if (not self.__GrabFailed):
            common.writeLog('Grabbing started ...')
            #notify
            if self.__notify_status == True:
                common.notifyOSD(__LS__(30000), __LS__(30003),common.IconInfo)
            #progress bar
            if self.__progressbar_status == True:
                self.__ProgressBar = WGProgressBar()
                self.__ProgressBar.Create(0, 0)
        return (not self.__GrabFailed)
               
    def GrabCheck(self):
        Busy = True
        #update progressbar (we do need to read the logfile ...)
        if self.__ProgressBar != None:
            self.ReadFromLogFile(True)
            self.__ProgressBar.Update(self.LogInfo.WGInfo.ChannelCounter, self.LogInfo.WGInfo.Channels)
        #check if grab is finished
        ExitCode = self.Command.Busy()
        if ExitCode != None:
            if ExitCode == 0: #Correct execution
                self.__GrabFailed = False
                Busy = False
            else:
                if self.__GrabFailed == True:
                    common.writeLog("Error executing EPG update (2nd try)",xbmc.LOGERROR)
                    common.notifyOSD(__LS__(30006), __LS__(30009), common.IconError) 
                    Busy = False
                else:
                    self.__GrabFailed = True
                    common.writeLog("Error executing EPG update (1st try)",xbmc.LOGWARNING)
                    self.CalcTimeOut()
                    Busy = not self.StartGrabbing(True)
        #timeout check
        if Busy == True:
            # Only read logfile after timeout time to save readings (and if no progressbar. Otherwise logfile is already been read)
            if (self.__TimeOutTime > 0) and (self.__TimeOutTime < self.LogInfo.EpochGetNow()):
                if self.__ProgressBar == None:
                    self.ReadFromLogFile(True)    
                if (self.LogInfo.WGInfo.ChannelCounter > self.__CompChannelCounter):
                    self.__CompChannelCounter = self.LogInfo.WGInfo.ChannelCounter
                    self.CalcTimeOut()
                else:
                    common.writeLog('EPG-grabbing timeout, kill process',xbmc.LOGERROR)
                    common.notifyOSD(__LS__(30000), __LS__(30015),common.IconError)
                    self.Command.Kill()
                    if self.__GrabFailed == True:
                        Busy = False
                    else:
                        self.__GrabFailed = True
                        self.CalcTimeOut()
                        Busy = not self.StartGrabbing(True)
        return Busy
                    
    def GrabPost(self):
        #notify
        if self.__notify_status == True:
            common.notifyOSD(__LS__(30000), __LS__(30004),common.IconInfo)
        #del ProgressBar
        if self.__ProgressBar != None:
            self.__ProgressBar.Close()
            del self.__ProgressBar
            self.__ProgressBar = None
        if self.__GrabFailed == False:
            # backup to fallback backup if not failed  
            if self.__backup_xml == True: 
                if os.path.exists("%s.bak"%(self.__wg_xmlfile)):
                    shutil.copy("%s.bak"%(self.__wg_xmlfile), "%s.fallback"%(self.__wg_xmlfile))
                else:
                    common.writeLog("xml-backup-file not found, no fallback file generated",xbmc.LOGWARNING)
                    common.notifyOSD(__LS__(30006), __LS__(30010), common.IconStop)
            # read log file for next grab if not failed
            self.ReadFromLogFile(True)
            common.writeLog('Grabbing finished ...')
        return (not self.__GrabFailed)

    def PostProcPre(self):
        Busy = (self.__sck_transfer == True) or (self.__post_transfer == True) or (self.__update_kodi == True)
        self.CalcTimeOut()
        #start
        if Busy == True:
            if not os.path.exists(self.__wg_xmlfile):
                common.writeLog("xml-file not found, no post-processing possible",xbmc.LOGERROR)
                common.notifyOSD(__LS__(30014), __LS__(30007), common.IconStop)
                Busy = False
            else:
                common.writeLog('Post processing started ...')
                if self.__sck_transfer == True:
                    if os.path.exists(self.__sck_url):
                        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        s.connect(self.__sck_url)
                        datafile = file(self.__wg_xmlfile)
                        for line in datafile:
                            s.send(line)
                        s.close()
                    else:
                        common.writeLog("Socket not found, no socket transfer possible",xbmc.LOGERROR)
                        common.notifyOSD(__LS__(30014), __LS__(30011), common.IconStop)
                    Busy = (self.__post_transfer == True) or (self.__update_kodi == True)
                if self.__post_transfer == True:
                    if os.path.exists(self.__post_script):
                        self.Command.Run([self.__post_script])
                    else:
                        common.writeLog("Postprocessor not found, no postprocessing possible",xbmc.LOGERROR)
                        common.notifyOSD(__LS__(30014), __LS__(30012), common.IconStop)            
        return Busy
               
    def PostProcCheck(self):
        Busy = True
        #finished
        if self.__post_transfer == True:
            ExitCode = self.Command.Busy()
            if ExitCode != None:
                Busy = False
                if ExitCode != 0:
                    common.writeLog("Postprocessor execution error",xbmc.LOGERROR)
                    common.notifyOSD(__LS__(30014), __LS__(30013), common.IconError)                
            #timeout check
            else:
                if (self.__TimeOutTime > 0) and (self.__TimeOutTime < self.LogInfo.EpochGetNow()):
                    common.writeLog('Postprocessor timeout, kill process')
                    common.notifyOSD(__LS__(30000), __LS__(30016),common.IconError)
                    self.Command.Kill()
                    Busy = False
        return Busy
                    
    def PostProcPost(self):
        #notify
        #if self.__notify_status == True:
        #    common.notifyOSD(__LS__(30000), __LS__(30018),common.IconInfo)
        # Update kodi
        if self.__update_kodi == True:
            if self.__not_update_running == True:
                if xbmc.getCondVisibility('Pvr.IsPlayingTv|Pvr.IsPlayingRadio|Pvr.IsPlayingRecording|Pvr.IsRecording') == True:
                    return
            xbmc.executebuiltin('StartPVRManager')
        common.writeLog('Post processing finished ...')
        return   
        
    def Scheduler(self):
        if (self.__Status == common.STAT_UNKNOWN) or (self.__Status == common.STAT_IDLE):
            if (self.__NextUpdate > 0) and (self.__NextUpdate < self.LogInfo.EpochGetNow()):
                if self.GrabPre() == True:
                    self.__Status = common.STAT_GRABBING
                else:
                    self.__Status = common.STAT_ERROR
            else:
                self.__Status = common.STAT_IDLE
        elif self.__Status == common.STAT_GRABBING:
            if self.GrabCheck() == False:
                if self.GrabPost() == True:
                    if self.PostProcPre() == True:
                        self.__Status = common.STAT_POSTPROC
                    else:
                        self.__Status = common.STAT_IDLE
                else:
                    self.__Status = common.STAT_ERROR                
        elif self.__Status == common.STAT_POSTPROC:
            if self.PostProcCheck() == False:
                self.PostProcPost()
                self.__Status = common.STAT_IDLE
        else:
            self.__Status = common.STAT_ERROR
        return
        
    def KillThreads(self):
        self.Command.Kill()
        del self.Command
        del self.LogInfo
        return
        
    def ReadFromLogFile(self, onlycurrent = False):
        self.LogInfo.ReadLogFile(onlycurrent)
        self.__NextUpdate = self.LogInfo.CalcNextUpdate()

    ####################################### START MAIN SERVICE #####################################

    def start(self):
        if common.IsRunning():
            common.writeLog('Attempting to start service while service already running, quit ....', xbmc.LOGERROR)
            return

        common.Run()
        common.writeLog('Starting service (%s)' % (self.__rndProcNum))
             
        bKillMain = False
        bStartApp = True

        ### START MAIN LOOP ###
        # Wait 10 seconds before reading old logfile to overcome python timer bug
        SchedulerCount = 0
        while (not xbmc.abortRequested) and (not bKillMain):
            xbmc.sleep(common.COMMAND_LOOP)
            self.GetAndExecuteCommand()
            self.GetAndExecuteSockCommand()
            if (SchedulerCount < SCHEDULERTIME):
                SchedulerCount += 1
            else:
                SchedulerCount = 0
                if bStartApp == True:
                    bStartApp = False
                    self.ReadFromLogFile()
                self.Scheduler()

        ### END MAIN LOOP ###
        
        self.KillThreads()
        self.SockComm.Close()
        common.Stop()
        common.writeLog('Service(%s) finished' % (self.__rndProcNum))

        ##################################### END OF MAIN SERVICE #####################################
#########################################################

#########################################################
######################## MAIN ###########################
#########################################################
WGMan = Manager()

#always check if manager is not already running, otherwise start manager
if not common.IsRunning():
    WGMan.start()

    __p = platform.uname()

    common.writeLog('<<<')
    common.writeLog('              _\|:|/_        BYE BYE')
    common.writeLog('               (o -)')
    common.writeLog('------------ooO-(_)-Ooo----- V.%s on %s --' % (__version__, __p[1]))
    common.writeLog('<<<\n')
else:
    common.writeLog('Attempting to start service while service already running')

del WGMan
#########################################################
