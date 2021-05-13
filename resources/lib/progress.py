# -*- coding: utf-8 -*-
#########################################################
# SCRIPT  : progress.py                                 #
#           Progress functions for WebGrab++            #
#           I. Helwegen 2016                            #
#########################################################

####################### IMPORTS #########################
import os
import time, datetime

#########################################################

####################### GLOBALS #########################

#########################################################    
PARAM_NA = 'N/A'

class WGInfo(object):
    Channels = 0
    Channel = PARAM_NA
    ChannelCounter = 0
    Shows = 0
    TotalChannels = 0
    Updated = 0
    New = 0
    FinishedTime = 0
    Duration = PARAM_NA

#########################################################    

class LogFile(object):
    def __init__(self, interval, logfile):
        self.WGInfo = WGInfo()
        self.__epg_interval = interval
        self.__wg_logfile = logfile
        
    def GetJobDetails(self, Line, mtime):
        try:
            FinishedTime = self.WGDate2Epoch(Line.split('job finished at ')[1].split(' done in ')[0])
        except:
            FinishedTime = 0
        try:
            d = int(Line.split(' done in ')[1].split(' seconds')[0])
            m = d/60
            s = d%60
            Duration = "%dm %ds"%(m,s)
        except:
            try:
                m = int(Line.split(' done in ')[1].split('m')[0])
                s = int(Line.split('m ')[1].split('s')[0])
                Duration = "%dm %ds"%(m,s)
            except:
                Duration = "0"
        dtime = abs (FinishedTime - int(mtime))
        if (dtime > 20): # If more than 20 seconds time difference, take file time
            FinishedTime = int(mtime)
        return (FinishedTime, Duration)

    def GetUpdateChannels(self, Line):
        try:
            Channels = int(Line.split('- out of - ')[1].split(' - channels')[0])
        except:
            Channels = 0
        return Channels
    
    def GetChannelName(self, Line):
        try:
            if ') -- ' in Line:
                Channel = Line.split('(xmltv_id=')[1].split(') -- ')[0]
            elif ') site' in Line:
                Channel = Line.split('(xmltv_id=')[1].split(') site')[0]
            else:
                Channel = Line.split('channel ')[1].split(' same as')[0]
        except:
            Channel = None
        return Channel

    def GetShowsInChannels(self, Line):
        try:
            Shows = int(Line.split('[  debug ] ')[1].split(' shows in ')[0])
        except:
            Shows = 0
        try:
            TotalChannels = int(Line.split(' shows in ')[1].split(' channels')[0])
        except:
            TotalChannels = 0
        return (Shows, TotalChannels)

    def GetShowsUpdated(self, Line):
        try:
            Updated = int(Line.split('[  debug ] ')[1].split(' updated shows')[0])
        except:
            Updated = 0
        return Updated

    def GetShowsNew(self, Line):
        try:
            New = int(Line.split('[  debug ] ')[1].split(' new shows added')[0])
        except:
            New = 0
        return New
        
    def ClearLog(self):
        self.WGInfo.Channels = 0
        self.WGInfo.Channel = PARAM_NA
        self.WGInfo.ChannelCounter = 0
        self.WGInfo.Shows = 0
        self.WGInfo.TotalChannels = 0
        self.WGInfo.Updated = 0
        self.WGInfo.New = 0
        self.WGInfo.FinishedTime = 0
        self.WGInfo.Duration = PARAM_NA
    
    def GetLogFile(self, oldlog):
        self.ClearLog()
        if oldlog == True: 
            if os.path.exists("%s.old"%(self.__wg_logfile)):
                mtime = os.path.getmtime("%s.old"%(self.__wg_logfile))
                datafile = None
                with open("%s.old"%(self.__wg_logfile), "r") as fp:
                    datafile = fp.readlines()
            else:
                oldlog = False
        if oldlog == False:
            if os.path.exists(self.__wg_logfile):
                mtime = os.path.getmtime(self.__wg_logfile)
                datafile = None
                with open(self.__wg_logfile, "r") as fp:
                    datafile = fp.readlines()
            else:
                datafile = None
                mtime = 0
        if datafile != None:
            for l in datafile:
                line = l.lower()
                if '[  info  ] update requested for' in line:
                    self.WGInfo.Channels = self.GetUpdateChannels(line)
                if '[  info  ] channel ' in line:
                    self.WGInfo.Channel = self.GetChannelName(l)
                    self.WGInfo.ChannelCounter += 1
                if ' -- chan. (' in line:
                    self.WGInfo.Channel = self.GetChannelName(l)
                    self.WGInfo.ChannelCounter += 1
                if ' shows in ' in line:
                    self.WGInfo.Shows, self.WGInfo.TotalChannels = self.GetShowsInChannels(line)
                if ' updated shows' in line:
                    self.WGInfo.Updated = self.GetShowsUpdated(line)
                if ' new shows added' in line:
                    self.WGInfo.New = self.GetShowsNew(line)
                if ' job finished at' in line:
                    self.WGInfo.FinishedTime, self.WGInfo.Duration = self.GetJobDetails(line, mtime)
        del datafile
        
    def ReadLogFile(self, onlycurrent = False):
        self.GetLogFile(False)
        if onlycurrent == False:
            if (self.WGInfo.FinishedTime == 0): # Currentlog has no finishtime, try oldlog
                self.GetLogFile(True)
                
    def CalcNextUpdate(self):
        if self.WGInfo.FinishedTime == 0:
            NextUpdate = self.EpochGetNow() + (self.__epg_interval*3600) # Does not harm when setting it 12 hours from now (prevent loop)
        else:
            if self.__epg_interval == 0:
                NextUpdate = 0
            else:
                NextUpdate = self.WGInfo.FinishedTime + (self.__epg_interval*3600)         
        return NextUpdate              
    
    def CopyLog(self,Copy):
        Copy.Channels = self.WGInfo.Channels
        Copy.Channel = self.WGInfo.Channel
        Copy.ChannelCounter = self.WGInfo.ChannelCounter
        Copy.Shows = self.WGInfo.Shows
        Copy.TotalChannels = self.WGInfo.TotalChannels
        Copy.Updated = self.WGInfo.Updated
        Copy.New = self.WGInfo.New
        Copy.FinishedTime = self.WGInfo.FinishedTime
        Copy.Duration = self.WGInfo.Duration
        return Copy
        
    #datetime.datetime
    #rettime = time.struct_time([2016, 1, 10, 4, 58,0,0,0,0])
    #time.struct_time(tm_year=2016, tm_mon=1, tm_mday=10, tm_hour=4, tm_min=58, tm_sec=0, tm_wday=0, tm_yday=0, tm_isdst=0)
    #time.struct_time(tm_year=2016, tm_mon=1, tm_mday=3, tm_hour=10, tm_min=4, tm_sec=58, tm_wday=6, tm_yday=3, tm_isdst=-1)
    # 1/3/2016 10:04:58 AM
        
    def Mystrptime(self, date_time):
        a = date_time.split('/')
        b = a[2].split(' ') 
        c = b[1].split(':')
        y = int(b[0])
        if len(b) > 2:
            m = int(a[0])
            d = int(a[1])
            if (b[2].lower() == 'am'):
                if int(c[0]) == 12:
                    h = 0
                else:
                    h = int(c[0])
            else:
                if int(c[0]) == 12:
                    h = int(c[0])
                else:
                    h = int(c[0]) + 12
        else:
            m = int(a[1])
            d = int(a[0])
            h = int(c[0])
        mn = int(c[1])
        s = int(c[2])
        return time.struct_time([y, m, d, h, mn, s, 0, 0, -1])
        
    def WGDate2Epoch(self,date_time):
        #return int(time.mktime(time.strptime(date_time.strip(), '%m/%d/%Y %I:%M:%S %p')))
        return int(time.mktime(self.Mystrptime(date_time.strip())))
        
    def Epoch2Date(self,epoch):
        if (epoch == 0):
            return "None"
        return time.strftime('%d-%m-%Y %H:%M',time.localtime(epoch))

    def Epoch2Dates(self,epoch):
        if (epoch == 0):
            return "None"
        return time.strftime('%d-%m-%Y %H:%M:%S',time.localtime(epoch))
    
    def EpochGetNow(self):
        return int(time.mktime(datetime.datetime.now().timetuple()))
