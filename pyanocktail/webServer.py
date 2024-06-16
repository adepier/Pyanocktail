# -*- coding: utf-8 -*-
'''
Created on 30 mai 2012

@author: babe
'''
import sys
import os
import json
# from numpy import ndarray
from twisted.application.internet import StreamServerEndpointService
from twisted.internet import defer,\
    protocol,\
    reactor,\
    threads,\
    utils,\
    endpoints, \
    serialport
from twisted.web.resource import Resource
from twisted.web import server, static
from twisted.python import log, util
from twisted.protocols.basic import LineReceiver 
from autobahn.twisted.websocket import WebSocketServerFactory, \
    WebSocketServerProtocol
from autobahn.twisted.resource import WebSocketResource
from . import dbUtils
from .i2cRpi import switchcontrol, playRecipe
from .songAnalysis import filter_process_result, format_output
from .pyanalysis import PIANOCKTAIL
# from pyanocktail.midi import listInports, listOutports

# from pyanocktail.pyanocktaild import task_queue, status_queue

Com = dict()
Com['record 1'] = 1
Com['record 0'] = 2
Com['play 1'] = 7
Com['status'] = 6
Com['reload'] = 5
Com['cocktail'] = 3
Com['panic'] = 4
Com['close'] = 9
Com['config'] = 6
Com['pump'] = 10

CanCommands = ["stop", "record", "play", "pump", "cocktail", "panic", "status", "modeAuto"]


class WebService(StreamServerEndpointService):
    '''
    web interface module and parent of all services
    '''

    def __init__(self, debug, basedir, conf):
        '''
        Initialization of web and websocket servers
        '''
        self.playing = False
        self.conf = conf
        self.recording = False
        self.modeAuto = True
        self.analysing = False
        self.serving = False
        self.opened = False
        self.analyzed = {}
        self.analyzed['cocktail'] = 0
        self.analyzed['result'] = ''
        self.port = str(conf.httpport)
        self.debug = debug
        self.langage = conf.langage
        self.type = conf.get('type', 0)
        self.dbsession = conf.dbsession
        self.inports = []
        self.outports = []
        self.sysports = [(0, 0), (0, 0)]
        self.page = Dispatcher(debug, basedir, conf)
        print("installdir= %s" % basedir)
        self.page.parent = self
        self.site = server.Site(self.page)
#         self.site.protocol = HTTPChannelHixie76Aware
        if isinstance(conf.httpport, int):
            edp = endpoints.serverFromString(
                reactor, "tcp:" + str(conf.httpport))
        else:
            edp = endpoints.serverFromString(reactor, conf.httpport)
        StreamServerEndpointService.__init__(self, edp, self.site)
        
#         self.realport = self.endpoint._port

    def init_ws(self):
        print("start ws")
        if self._waitingForPort:
            if hasattr(self._waitingForPort.result, "getHost"):
                self.wsfactory = SeqFactory(
                    self.debug, self._waitingForPort.result.getHost().port)
                self.wsfactory.protocol = PyanoTCP
        #         self.wsfactory.setProtocolOptions(allowHixie76=True)
                self.wsfactory.parent = self
                self.wsresource = WebSocketResource(self.wsfactory)
                self.page.putChild(b"ws", self.wsresource)
                return
        reactor.callLater(5,  #@UndefinedVariable
                          self.init_ws)
        

    def startService(self):
        '''
        Start slave processes to intercept midi and gpio events
        '''
        super(WebService, self).startService()
        self.init_ws()
        self.startMidi()
        if self.type and self.type == 2:
            self.startCan()
        else:
            self.startGpio()
        log.msg('Pianocktail starting')
        
    def startCan(self):
        self.canfactory = CanFactory(self, self.conf)
        self.canfactory.connect()
        
    def startMidi(self):
        self.notes = []
        self.midifactory = MidiFactory(self.debug, self)
        self.midi = self.midifactory.protocol(debug=self.debug)
        self.midi.factory = self.midifactory
        exe = sys.executable
        midiscriptpath = util.sibpath(__file__, "midiprocess.py")
        midiex = [exe, "-u"]
        midiex.append(midiscriptpath)
        midiargs = ['-a', '-s', '-f',
                    os.path.join(self.conf.installdir, "scripts/current.pckt")]
        midicmd = midiex + midiargs
        if self.debug:
            log.msg(midicmd)
        self.midi.cmd = midicmd
        reactor.spawnProcess(self.midi, midicmd[0], args=midicmd, env=None,  # @UndefinedVariable
                             childFDs={0: "w", 1: "r", 2: "r"})

    def startGpio(self):
        self.gpiofactory = GpioFactory(self.debug, self)
        self.gpio = self.gpiofactory.protocol(debug=self.debug)
        self.gpio.factory = self.gpiofactory
        self.in_functions = dbUtils.getInputs(self.dbsession)
        print("*******%s" % self.in_functions)
        exe = sys.executable
        gpioscriptpath = util.sibpath(__file__, "gpioprocess.py")
        gpioex = [exe, "-u"]
        gpioex.append(gpioscriptpath)
        gpioargs = []
        if len(self.in_functions.keys()):
            gpioargs += ['-i'] + list(self.in_functions.keys())
        gpiocmd = gpioex + gpioargs
        if self.debug:
            log.msg(gpiocmd)
        self.gpio.cmd = gpiocmd
        reactor.spawnProcess(self.gpio, gpiocmd[0], args=gpiocmd, env=None,  # @UndefinedVariable
                             childFDs={0: "w", 1: "r", 2: "r"})

    def stopService(self):
        self.gpiofactory.stop()
        self.midifactory.stop()
        self.conf.save(self.conf.configdir)
        self.dbsession.commit()

    def badResult(self):
        tt =  "On ne sert pas les fainéants !!!\n"
        self.wsfactory.sendmessage( tt.encode("utf8"))
        self.canfactory.serial_port.write(bytes([0xaa,5,6,99,1,0,0,0,0,0,0xbb]))
        # on envoie du texte, 0xff termine la ligne
        self.canfactory.serial_port.write(tt.encode("utf8"))
        self.canfactory.serial_port.write(bytes([0xff])) 
        self.canfactory.serial_port.write(bytes([0xaa,5,6,200,1,0,0,0,0,0,0xbb])) 
    def display(self, text):
        self.wsfactory.sendmessage(text.encode("utf8"))

    def showResult(self, result):
        '''
        Display analysis result to ws status window
        '''
        if result != None:
            self.analyzed = result
            self.canfactory.serial_port.write(bytes([0xaa,5,6,99,1,0,0,0,0,0,0xbb]))
            for line in result['result']:
                self.wsfactory.sendmessage(line.encode("utf8"))
                self.canfactory.serial_port.write(line.encode("utf8") + b"\r\n")
                log.msg("log message %s" % line)
            self.canfactory.serial_port.write(bytes([0xff])) 
            self.canfactory.serial_port.write(bytes([0xaa,5,6,200,1,0,0,0,0,0,0xbb])) 
            return int(result['cocktail'])

    def set_command(self, command, args=''):
        '''
        transmit or execute commands from websocket or gpio interfaces
        '''
        if not isinstance(command, str):
            command = command.decode('utf8')
        if command == 'modeAuto':

            self.midifactory.command('modeAuto 1')
 
            # self.set_command('record')
        elif command == 'stop':
            log.msg("log message stop")
            # bouton stop (cmde:12) allumé
            self.canfactory.serial_port.write(bytes([0xaa,5,6,12,1,0,0,0,0,0,0xbb])) 
            self.canfactory.serial_port.write(bytes([0xaa,5,6,200,1,0,0,0,0,0,0xbb])) 
            # bouton stop (cmde:12) eteint
            self.canfactory.serial_port.write(bytes([0xaa,5,6,12,0,0,0,0,0,0,0xbb])) 
            self.canfactory.serial_port.write(bytes([0xaa,5,6,200,1,0,0,0,0,0,0xbb])) 
            # self.canfactory.serial_port.write(bytes([0xaa,5,6,12,1,0,0,0,0,0,0xbb]))
            # self.canfactory.serial_port.write(bytes([0xaa,5,6,13,0,0,0,0,0,0,0xbb]))
            if self.playing:
                self.midifactory.command('play 0')
                self.playing = False
            if self.recording:
                self.midifactory.command('record 0')
                self.recording = False
            if self.opened:
                pass
        elif command in ('play', 'record'):
            self.midifactory.command(command + ' 1')
            if command == 'play':
                self.playing = True
            else:
                print('commande recue record')
                # bouton enregistre (cmde:11) allumé
                self.canfactory.serial_port.write(bytes([0xaa,5,6,11,1,0,0,0,0,0,0xbb])) 
                self.canfactory.serial_port.write(bytes([0xaa,5,6,200,1,0,0,0,0,0,0xbb])) 
                # bouton enregistre (cmde:11)  
                self.canfactory.serial_port.write(bytes([0xaa,5,6,11,0,0,0,0,0,0,0xbb])) 
                self.canfactory.serial_port.write(bytes([0xaa,5,6,200,1,0,0,0,0,0,0xbb])) 
                # self.canfactory.serial_port.write(bytes([0xaa,5,6,1,1,0,0,0,0,0,0xbb]))
                # self.canfactory.serial_port.write(bytes([0xaa,5,6,2,0,0,0,0,0,0,0xbb]))
                # self.canfactory.serial_port.write(bytes([0xaa,5,6,3,0,0,0,0,0,0,0xbb]))
                self.analyzed['cocktail'] = 0
                self.analyzed['result'] = b''
                if not self.recording:
                    self.recording = True
                    self.notes = []
        elif command == 'cocktail':
            log.msg('commande recue cocktail')
            log.msg('cocktail %s'  % self.analyzed['cocktail'])
            if self.analyzed['cocktail'] > 0:
                # bouton servir (cmde:13) allumé
                self.canfactory.serial_port.write(bytes([0xaa,5,6,13,1,0,0,0,0,0,0xbb])) 
                self.canfactory.serial_port.write(bytes([0xaa,5,6,200,1,0,0,0,0,0,0xbb])) 
                # bouton servir (cmde:13) eteint
                self.canfactory.serial_port.write(bytes([0xaa,5,6,13,0,0,0,0,0,0,0xbb])) 
                self.canfactory.serial_port.write(bytes([0xaa,5,6,200,1,0,0,0,0,0,0xbb])) 
                # self.canfactory.serial_port.write(bytes([0xaa,5,6,1,0,0,0,0,0,0,0xbb]))
                # self.canfactory.serial_port.write(bytes([0xaa,5,6,2,0,0,0,0,0,0,0xbb]))
                # self.canfactory.serial_port.write(bytes([0xaa,5,6,3,1,0,0,0,0,0,0xbb]))
                d = threads.deferToThread(
                    self.serve, *(self.analyzed['cocktail'], self.conf.factor))
                d.addCallback(self.wsfactory.sendmessage)
                self.wsfactory.sendmessage(
                    b'Service en cours, %.1f cocktail%s...\n' % (
                        self.conf.factor,
                        b"s" if self.conf.factor > 1 else b''))
            else:
                if self.recording:
                    self.midifactory.command('record 0')
                    self.recording = False
                    if self.analyzed['cocktail'] == 0:
                        # @UndefinedVariable
                        # @UndefinedVariable
                        # @UndefinedVariable
                        # @UndefinedVariable
                        reactor.callLater(  # @UndefinedVariable
                            1, self.set_command, 'cocktail')
        elif command[:4] == 'test':
            cont = dbUtils.getPump(self.dbsession, command[6:])
            if len(cont) > 1:
                if cont[0] == 'gpio_in':
                    try:
                        try:
                            self.set_command(cont[4].split(
                                ",")[0], cont[4].split(",")[1])
                        except IndexError:
                            self.set_command(cont[4].split(",")[0])
                    except Exception as err:
                        print(err.message)
                elif command[5] == '-':
                    switchcontrol(cont, debug=self.debug)
                    self.serving = False
                else:
                    switchcontrol(cont, on=1, debug=self.debug)
                    self.serving = True
            else:
                log.msg("i2c error: no data found for pump n°:%s, error: %s"
                        % (str(command[6:]), cont[0]))
        else:
            try:
                fct = getattr(self, "sys_" + command)
            except AttributeError:
                log.msg("unknown function: %s" % command)
            else:
                fct(args)

    def get_command(self, command):
        '''
        manage commands from midi process
        '''
        if self.debug:
            log.msg('command from midi process: %s' % command.decode("utf8"))
        if command == b'Recorded':
            self.wsfactory.sendmessage(b"Analysing...")
            # analyse
            # log.msg(self.notes)
            d = threads.deferToThread(self.getDataAnalysis)
            d.addCallback(self.analyze)
            
        elif command == b'Recording_auto':
            print('recording auto!')
            # on allume les carrousels
            self.canfactory.serial_port.write(bytes([0xaa,1,6,12,0,0,0,0,0,0,0xbb])) 
            self.canfactory.serial_port.write(bytes([0xaa,1,6,200,1,0,0,0,0,0,0xbb]))
            
            self.canfactory.serial_port.write(bytes([0xaa,2,6,12,0,0,0,0,0,0,0xbb])) 
            self.canfactory.serial_port.write(bytes([0xaa,2,6,200,1,0,0,0,0,0,0xbb]))
            
            self.canfactory.serial_port.write(bytes([0xaa,3,6,12,0,0,0,0,0,0,0xbb])) 
            self.canfactory.serial_port.write(bytes([0xaa,3,6,200,1,0,0,0,0,0,0xbb]))
            self.set_command('record') 

        elif command == b'Recorded_auto':
            print('mode auto : recorded -> anaylse -> serve ')  
            self.wsfactory.sendmessage(b"Analysing...")
            # analyse
            # log.msg(self.notes)
            d = threads.deferToThread(self.getDataAnalysis)
            # d.addCallback(self.analyze)
            # service
            d.addCallback(lambda _:self.set_command('cocktail'))
        else:
            self.wsfactory.sendmessage(command)

    def getDataAnalysis(self):
        log.msg("alcool: %s" % bool(self.conf.alc))
        return dbUtils.getCocktails(self.dbsession, bool(self.conf.alc))

    def lockDB(self, result, lock=True, db=''):
        #log.msg("lockdb result= %s" % str(result))
        #log.msg("lockdb lock= %s" % str(lock))
        #log.msg("lockdb db = %s" % db)
        if lock == True:
            log.msg("locking %s" % db)
        else:
            log.msg("unlocking %s" % db)

    def get_info(self, data):
        '''
        process information data from midi process
        '''
        data = data.decode("utf8")
        if self.debug:
            log.msg('info from midi process: %s' % data)
#         cid = d.split(':')[0]
#         pid = d.split(':')[1]
#         cname = ''.join(for s in d[1:-1])
        if data.split()[0] == 'Input:':
            self.outports.append([data.split()[-1].split(':')[0],
                                  data.split()[-1].split(':')[1],
                                  ' '.join(s for s in data.split()[1:-1])])
        if data.split()[0] == 'Output:':
            self.inports.append([data.split()[-1].split(':')[0],
                                 data.split()[-1].split(':')[1],
                                 ' '.join(s for s in data.split()[1:-1])])

    def get_conf(self, data):
        '''
        process configuration data from midi process
        '''
        if self.debug:
            log.msg('config from midi process: %s' % data)
        if data.split()[0] == 'Input_port:':
            self.sysports[0] = (data.split()[-1].split(':')[0],
                                data.split()[-1].split(':')[1])
        if data.split()[0] == 'Output_port:':
            self.sysports[1] = (data.split()[-1].split(':')[0],
                                data.split()[-1].split(':')[1])
#         log.msg(self.sysports)

    def get_data(self, data):
        if self.debug:
            log.msg('data from midi process: %s' % data)

    def set_data(self, data, _args=''):
        if self.debug:
            log.msg(data + b' sent to midiprocess')
        self.midifactory.send(data)

    def serve(self, cocktail_id, qty=None):
        if not qty:
            qty = self.conf.factor
        if not isinstance(cocktail_id, int):
            if not isinstance(cocktail_id, str):
                cocktail_id = cocktail_id.decode("utf8")
        service = dbUtils.getServe(self.dbsession, cocktail_id)
        #self.type == 2 => CAN control
        if self.type and self.type == 2:
            for ser_ in service:
                ser_[0] = self.canfactory.serial_port
                # 4 => DEVICE_ID
                ser_[1] = 4
        log.msg('recette: %s' % service)
        playRecipe(service, qty, self.debug)
        ss = (b'', b'',)
        if qty > 1:
            ss = (b's', b's',)
        return b"%.1f Cocktail%s Servi%s !" % (qty, *ss)

    def analyze_old(self, tabs):
        #        log.msg("analyse requested")
        prog = os.path.abspath(self.conf.extProgram)
        if self.debug:
            log.msg("Analyze executable: %s" % prog)
        pargs = ['-nwni', '-nb', '-f', 'PIANOCKTAIL.sci']
        en = {'SCIHOME': os.path.join(self.conf.installdir, "scripts")}
        d = utils.getProcessOutput(prog,
                                   args=pargs,
                                   path=os.path.join(
                                       self.conf.installdir, "scripts"),
                                   env=en, errortoo=True)
        d.addCallback(filter_process_result, *(tabs,
                                               float(self.conf.complexind),
                                               float(self.conf.tristind),
                                               float(self.conf.nervind),
                                               self.debug))
        d.addCallback(self.showResult)

    def analyze(self, tabs):
        if self.debug:
            log.msg("Analyse Python")
        if len(self.notes) < 4:
            log.msg("moins de 4 notes")
            self.badResult()
            return 0
#         d = threads.deferToThread(PIANOCKTAIL, *(os.path.join(self.conf.installdir,"scripts","current.pckt"),self.notes))
        d = threads.deferToThread(PIANOCKTAIL, self.notes)
        d.addCallback(format_output)
        d.addCallback(filter_process_result, *(tabs, float(self.conf.complexind),
                                               float(self.conf.tristind), float(self.conf.nervind), self.debug))
        d.addCallback(self.showResult)

    def sys_shutdown(self, reboot=False):
        cmd = "reboot" if reboot else "poweroff"
        if self.debug:
            log.msg("%s requested" % cmd)
        d = utils.getProcessValue('/bin/systemctl', [cmd])
#         d = utils.getProcessValue('/usr/bin/true')
        d.addCallback(self.shutdown)

    def shutdown(self, value):
        if self.debug:
            log.msg("Shutdown return value: %d" % value)
        if value == 0:
            self.wsfactory.sendmessage(b'Shutdown in progress...\n')
        else:
            self.wsfactory.sendmessage(b'Shutdown error :(\n')


class SeqFactory(WebSocketServerFactory):
    '''
    WebSocket Factory
    '''

    def __init__(self, debug, port):
        #         self.task = task_queue
        #         self.notein = notein_queue
        self.debug = debug
        self.clients = []
        self.lastmsg = b""
        WebSocketServerFactory.__init__(self, "ws://localhost:" + str(port))

    def got_midipid(self, midipid):
        self.midipid = midipid

    def sendmessage(self, message):
        self.lastmsg = message
#         try:
        for client in self.clients:
            client.send(message, self.debug)
#         except Exception as err:
#             if self.debug:
#                 log.msg("sendmessage error: " + str(err))

    def wsReceived(self, data):
        #log.msg('data=%s' %data)
        if data.isdigit():
            #             print('note')
            return defer.Deferred(self.parent.set_data(b'1 ' + data))
#             if self.debug:
#                 log.msg('digit: '+data)
        elif data.startswith(b"-"):
            return defer.Deferred(self.parent.set_data(b'0 ' + data[1:]))
        else:
            if self.debug:
                log.msg('command: ' + data.decode("utf8"))

            return defer.Deferred(self.parent.set_command(data))


class PyanoTCP(WebSocketServerProtocol):
    '''
    ws protocol
    '''

    def connectionMade(self):
        self.factory.clients.append(self)
        if self.factory.debug:
            log.msg("New WS Connection from: " + str(self.transport.getHost()))
        WebSocketServerProtocol.connectionMade(self)
        reactor.callLater(1,   # @UndefinedVariable
                          self.send, self.factory.lastmsg)
#        self.send(self.factory.lastmsg)
#     def dataReceived(self, data):

    def onMessage(self, data, binary):
        if self.factory.debug:
            log.msg('data from ws: ' + data.decode("utf8"))
        if data == b'status':
            self.send(self.factory.lastmsg)
            return
        d = self.factory.wsReceived(data)

        def onError(err):
            if self.factory.debug:
                log.msg('error msg : ' + str(data))
            return b'Internal error in server'
        d.addErrback(onError)

        def writeResponse(message):
            if message is not None:
                self.sendMessage(message)
#            self.transport.loseConnection()
        d.addCallback(writeResponse)

    def connectionLost(self, reason):
        self.factory.clients.remove(self)
        if self.factory.debug:
            log.msg("ws connection lost\n")

    def send(self, data, debug=False):
        if self.connected:
            self.sendMessage(data)
#            if debug:
#                log.msg ("Sent to Websocket: "+data)
        elif debug:
            log.msg("Sent failed: not connected")


class MidiProtocol(protocol.ProcessProtocol):
    '''
    protocol in charge of slave local midi process
    '''

    def __init__(self, debug=False):
        self.debug = debug
#         self.psname = processname
        self.text = ""
        self.debugmsg = ""
        self.decoding = False
        self.num = 0

    def connectionMade(self):
        log.msg("midi process started")
#         self.transport.write("resume\n")
        self.factory.proto = self
        self.write(b'list io')

    def childDataReceived(self, childFD, data):
        # For compatibility, the default implementation of .childDataReceived
        #  dispatches to .outReceived or .errReceived when “childFD” is 1 or 2.
        if childFD == 1:
            
            for l in data.split(b'\n'):
                print(l.lstrip()[2:])
                log.msg("childDataReceived Midi: %s" % l)
                try:
                    c = int(l.split()[0])
#                     print(c)
                    self.factory.receive(c, l.lstrip()[2:])
                except (IndexError, ValueError):
                    if len(l) > 1:
                        log.msg("unknown message .outReceived from midi process: %s" % l)
        elif childFD == 2:
            for l in data.split(b'\n'):
                if l != b'':
                    if self.debug:
                        log.msg(l)
                    try:
                        n = l.split()
                        float(n[0])
                        self.factory.parent.notes.append(
                            [float(n[0]), float(n[1]), float(n[2]), float(n[3])])
                    except:
                        # log.msg("unknown message .errReceived from midiprocess: %s" %l)
                        pass

    def write(self, data):
        if self.debug:
            log.msg('sending %s' % data.decode("utf8"))
        self.transport.write(data + b'\n')

    def shutdown(self):
        if self.debug:
            log.msg('stopping midi subprocess')
        self.transport.signalProcess('INT')


class MidiFactory(protocol.Factory):
    '''
    factory for slave local midi process
    '''
    protocol = MidiProtocol

    def __init__(self, debug, parent):
        self.debug = debug
        self.parent = parent
#         self.proto = MidiProtocol(debug=debug)

    def send(self, data):
        if isinstance(data, str):
            data = data.encode('utf8')
        self.proto.write(data)

    def command(self, command, args=b''):
        if isinstance(command, str):
            command = command.encode("utf8")
        if isinstance(args, str):
            args = args.encode("utf8")
        self.proto.write(command + b" " + args)

    def receive(self, c, data):
        if c in (0, 1, 3):
            self.parent.get_command(data)
        else:
            if c == 2:
                self.parent.get_conf(data)
            elif c == 4:
                self.parent.get_info(data)
            else:
                self.parent.get_data(data)

    def stop(self):
        try:
            self.proto.shutdown()
        except:
            # Already exited
            pass
        
class CanSerialProtocol(LineReceiver):
    
    delimiter = 0xbb

    def connectionMade(self):
        print("Serial connection OK")
        self.first = True
        self.setRawMode()
        #self.factory.proto = self
        self.debug = self.factory.debug
        self.buf = []
    def rawDataReceived(self, data):
        print(data)
        if data[0] == 0xaa:
            print(data[0])
            print(data[9])
            
            print("command received from %i:" % data[1])
            if data[3] == 12 :
                self.factory.got_command("stop")
            elif data[3] == 11:
                self.factory.got_command("record")
            elif data[3] == 13:
                self.factory.got_command("cocktail")
            elif data[3] == 14:
                self.factory.got_command("modeAuto")
            else:
                print("unknown command %i" % data[2])
        # if self.first:
        #     if data[0] != 0xaa:
        #         print("line mode")
        #         self.setLineMode(data)
        #     else:
        #         # print("Can Received Hex: 0x%0x" % ord(data), end=" ")
        #         self.first = False
        # else:
        #     # print("0x%0x" % ord(data), end= " ")
        #     # self.buf.append(int((data)))
        #     if data == 0xbb:
        #         if len(self.buf) and self.buf[0] == 6:
        #             print("command received from %i:" % self.buf[1])
        #             if self.buf[2] == 2 :
        #                 self.factory.got_command("stop")
        #             elif self.buf[2] == 1:
        #                 self.factory.got_command("record")
        #             elif self.buf[2] == 3:
        #                 self.factory.got_command("cocktail")
        #             elif self.buf[2] == 4:
        #                 self.factory.got_command("play")
        #             else:
        #                 print("unknown command %i" % self.buf[2])
        #         self.buf = []
        #         self.first = True
    def lineReceived(self, line):
        print("Data serial received: %s" % line.strip())
        self.first = True
        self.setRawMode()
        self.factory.got_command(line.strip())
            
            
class CanFactory(protocol.Factory):
    
    protocol = CanSerialProtocol
    port = "/tmp/vserial1"
    debug = True
    
    def __init__(self, parent, conf=None):
        if conf:
            self.debug = conf.debug
            self.port = conf.get("ttyPort", "/tmp/vserial1")
        self.parent = parent
        
    def connect(self):
        self.proto = self.protocol()
        self.proto.factory = self
        try:
            self.serial_port = serialport.SerialPort(self.proto,
                                                 self.port,
                                                 reactor, baudrate = 9600 , timeout = 2, bytesize=8, parity='N', stopbits=1)
        except Exception as err:
            print(err)
        
    def got_command(self, command):
        log.msg("got_command: %s" % command)
        if not isinstance(command, str):
            command = command.decode('utf8')
        #command = command.decode("utf8")
        if command in CanCommands:
            log.msg(" command in CanCommands: %s" % command)
            self.parent.set_command(command)
        else:
            log.msg(" command NOT in CanCommands: %s" % command)
            self.parent.display(command)
        
        
    
    
    
            

class GpioProtocol(protocol.ProcessProtocol):
    '''
    protocol in charge of local gpio subprocess
    '''

    def __init__(self, debug=False):
        self.debug = debug
#         self.psname = processname
        self.text = ""
        self.debugmsg = ""
        self.decoding = False
        self.num = 0

    def connectionMade(self):
        log.msg("gpio process started")
#         self.transport.write("resume\n")
        self.factory.proto = self

    def childDataReceived(self, childFD, data):
        if childFD == 1:
            for l in data.split(b'\n'):
                try:
                    c = int(l.split()[0])
                    self.factory.receive(c)
                except:
                    if l != b'':
                        if l != b'None':
                            log.msg("unknown message from gpio process: %s" % l)
        elif childFD == 2:
            for l in data.split(b'\n'):
                if l != b'':
                    log.msg("Error message from gpio process: %s" % l)

    def shutdown(self):
        if self.debug:
            log.msg('Stopping gpio subprocess')
        self.transport.signalProcess('INT')


class GpioFactory(protocol.Factory):
    '''
    factory for slave local gpio process
    '''
    protocol = GpioProtocol

    def __init__(self, debug, parent):
        self.debug = debug
        self.parent = parent
        self.notes = []

    def stop(self):
        try:
            self.proto.shutdown()
        except:
            # Already exited
            pass

    def receive(self, c):
        if self.parent.debug:
            log.msg('Input signal from GPIO: %d' % c)


class Dispatcher(Resource):
    '''
    Dispatch request between static or dynamic pages
    '''
    isLeaf = False

    def __init__(self, debug, installdir, conf):
        Resource.__init__(self)
#        self.seq = seq
        self.conf = conf
        self.installdir = installdir
#         self.task = task_queue
#         self.status_queue= status_queue
        self.debug = debug
        self.putChild(b"pictures",
                      static.File(os.path.join(self.installdir,
                                               'html', 'pictures')))
        self.putChild(b"favicon.png",
                      static.File(os.path.join(self.installdir,
                                               'html', 'favicon.png')))
        self.putChild(b"style.css",
                      static.File(os.path.join(self.installdir,
                                               'html', 'style.css')))
        self.putChild(b"pianocktail.js",
                      static.File(os.path.join(self.installdir,
                                               'html', 'pianocktail.js')))
        self.putChild(b"main",
                      static.File(os.path.join(self.installdir,
                                               'html', 'Pianocktail.html')))
        self.putChild(b"config",
                      static.File(os.path.join(self.installdir,
                                               'html', 'config.html')))
        self.putChild(b"pumps",
                      static.File(os.path.join(self.installdir,
                                               'html', 'pumps.html')))
        self.putChild(b"analyze",
                      static.File(os.path.join(self.installdir,
                                               'html', 'analyze.html')))
        self.putChild(b"recipes",
                      static.File(os.path.join(self.installdir,
                                               'html', 'recipes.html')))
        self.putChild(b"fonts",
                      static.File(os.path.join(self.installdir,
                                               'html', 'fonts')))
        self.putChild(b"scripts",
                      static.File(os.path.join(self.installdir,
                                               'html', 'scripts')))
        self.putChild(b"notes.pckt",
                      static.File(os.path.join(self.installdir,
                                               'scripts', 'current.pckt'),
                                  defaultType='application/octet-stream'))

    def getChild(self, name, request):
        if self.debug:
            log.msg("page requested: " + str(name))
        return MainPage(name, self.debug, self.installdir, self.conf, self.parent)


class MainPage(Resource):
    '''
    Handle dynamic content, mainly POST requests
    '''

    def __init__(self, page, debug, installdir, conf, parent):
        Resource.__init__(self)
        self.page = page
        self.conf = conf
        self.parent = parent
        self.debug = debug
        self.installdir = installdir
    isLeaf = True

    def resultOk(self, result, request, commit=False, option=None):
        #         log.msg('OK: %s' % result)
        if isinstance(result, dict):
            #             request.write(json.JSONEncoder().encode(result))
            r = json.JSONEncoder().encode(result)
            com = 'write'
        elif result == 1:
            #             request.redirect('recipes')
            r = 'recipes'
            com = 'redirect'
        else:
            dic = dict()
            if option != None:
                dic[option] = result
            else:
                dic['updated'] = 1
            # log.msg(dic)
            r = json.JSONEncoder().encode(dic)
#             request.write(json.JSONEncoder().encode(r))
            com = 'write'
        if commit:
            d = threads.deferToThread(self.parent.dbsession.commit)
            d.addCallback(self.endRequest, *(request, com, r,))
            return d
        else:
            self.endRequest(0, request, com, r)
#             getattr(request,com)(r)
#             request.finish()

    def resultFailed(self, result, request, rollback=False):
        log.msg('db update failed...%s' % str(result))
        if rollback:
            reactor.callInThread(  # @UndefinedVariable
                self.parent.dbsession.rollback)
        r = dict()
        r['updated'] = 0
        request.write(json.JSONEncoder().encode(r))
        request.finish()

    def endRequest(self, res, req, com, result):
        #         print(result)
        getattr(req, com)(result.encode("utf8"))
        req.finish()

    def render_GET(self, request):
        if self.page == b'':
            request.redirect(b'main')
        else:
            request.setResponseCode(404)
            request.write(b"nada!\n")
        request.finish()
        return server.NOT_DONE_YET

    def render_POST(self, request):
        param = False
        if self.debug:
            log.msg(request.content)
            log.msg("POST received Headers: " +
                    str(request.getAllHeaders()) + "\n")
            log.msg("POST received Args: " + str(request.args) + "\n")
            log.msg("POST received Content: %s" %
                    request.content.getvalue().decode('utf8'))
#         try:
            '''
            Global exception handler to avoid letting bad connections open
            '''
        try:
            '''
            Check if it is a url-encoded or json-encoded request
            '''
            client = request.args[b'client'][0].decode('utf8')
            action = request.args[b'action'][0].decode('utf8')
            log.msg("222")
            try:
                command = request.args[b'command'][0].decode("utf8")
            except (AttributeError, KeyError,):
                command = False
            try:
                param = request.args[b'param'][0].decode('utf8')
            except (AttributeError, KeyError,):
                if command:
                    if command == 'setrecipe':
                        param = request.args
            if self.debug:
                log.msg("url-encoded request: %s" % action)
        except (AttributeError, KeyError) as err:
            print(err)
            dictreq = json.load(request.content)
            # log.msg(dictreq)
            client = dictreq['client']
            action = dictreq['action']
            command = dictreq['command']
            param = dictreq['params']
            if self.debug:
                log.msg("json-encoded request: %s" % action)

        if client == 'web':
            if action in ('status',
                          'close',
                          'play',
                          'record',
                          'reload',
                          'cocktail',
                          'stop',
                          'config',
                          'pump',
                          'test'):
                if action == 'config':
                    if param:
                        '''
                        Update Data
                        '''
                        if self.debug:
                            log.msg(
                                "request processed param = %s" % str(param))
                        self.updateDB(request, command, param)
                    else:
                        '''
                        Get Data
                        '''
                        if self.debug:
                            log.msg("request %s without parameter" % request)
                        self.queryDB(request, command)
                elif action == 'pump':
                    if command:
                        control = dbUtils.getPump(
                            self.parent.dbsession, command[1:])
                        if self.debug:
                            log.msg("pump command: " + command)
                        try:
                            switchcontrol(control, int(
                                not self.parent.serving), self.debug)
                            self.parent.serving = not self.parent.serving
                            # log.msg("serving = %s" % self.parent.serving)
                            request.write(b'0')
                        except:
                            log.msg("i2c system error")
                            request.write(b'1')
                    request.finish()

                elif action == 'cocktail':
                    d = threads.deferToThread(
                        self.parent.serve, *(command,))
                    d.addCallbacks(self.resultOk, errback=self.resultFailed,
                                   callbackArgs=(request,), errbackArgs=(request,))
            else:
                request.write(b"bad command")
                request.finish()
#         except json.JSONDecodeError as err:
#             log.msg("Error: " + str(err))
#             request.write(b"network error")
#             request.finish()

        return server.NOT_DONE_YET

    def updateDB(self, request, command, params):
        if command in ('setconf',
                       'setcocking',
                       'setrecipe',
                       'getcocking'):
            func = getattr(self, command)
        else:
            func = getattr(dbUtils, command)
        d = threads.deferToThread(func, *(self.parent.dbsession, params,))
        d.addCallback(self.resultOk, *(request, True,))
        d.addErrback(self.resultFailed, *(request, True,))
#         d.addCallbacks(self.resultOk, errback=self.resultFailed,
# callbackArgs=(request,True,), errbackArgs=(request,True,))
        d.addBoth(self.parent.lockDB, *(False, command[3:],))

    def queryDB(self, request, command):
        #         print(str(command))
        if command == ('getconf'):
            func = getattr(self, command)
        else:
            func = getattr(dbUtils, command)
        d = threads.deferToThread(func, *(self.parent.dbsession,))
        d.addCallbacks(self.resultOk,
                       errback=self.resultFailed,
                       callbackArgs=(request, False, command[3:],),
                       errbackArgs=(request, False,))

    def getconf(self, dbsession):
        d = dict()
        for param in self.conf.list_params:
            d[param] = getattr(self.conf, param)
        d['inports'] = self.parent.inports
        d['outports'] = self.parent.outports
        d['connectedin'] = self.parent.sysports[0]
        d['connectedout'] = self.parent.sysports[1]
        d['systemports'] = dbUtils.getPumps(dbsession)
        return d

    def setconf(self, dbsession, params):
        d = dict()
        for param in params:
            if self.debug:
                log.msg("setconf params: " + str(params))
                log.msg("update = " + str(param) +
                        " value = " + str(params[param]))
            if str(param) == 'rows':
                if params[param] == []:
                    continue
                if self.debug:
                    log.msg("setpumps params: " + str(params))
                dbUtils.setPumps(dbsession, params[param])
            elif str(param) == 'debug':
                if params[param] == 0:
                    setattr(self.conf, param, False)
                else:
                    setattr(self.conf, param, True)
            else:
                if param in ('factor',):
                    setattr(self.conf, param, float(params[param]))
                else:
                    setattr(self.conf, param, params[param])
        self.conf.save(self.conf.configdir)
        d['updated'] = "1"
        return d

    def getcocking(self, dbsession, ing):
        d = dict()
        d['ingredients'] = dbUtils.getRecipe(dbsession, int(ing))
        d['list'] = dbUtils.getIngList(dbsession)
        return d

    def setrecipe(self, dbsession, params):
        if self.debug:
            log.msg("setrecipe params: " + str(params))
        req = {}
        req['id'] = int(params[b'cocktail_id'][0].decode("utf8"))
        ingredients = []
        for i in range(int((len(params) - 4) / 2)):
            ingredients.append([])
            ingredients[i].append([])
            ingredients[i].append([])
        for k, v in params.items():
            key = k.decode("utf8")
            if key not in (
                    'config', 'action', 'command', 'cocktail_id'):
                if key.split()[0] == 'ing':
                    ingredients[int(key.split()[1]) -
                                1][0] = int(v[0].decode("utf8"))
                elif key.split()[0] == 'qty':
                    ingredients[int(key.split()[1]) -
                                1][1] = int(v[0].decode("utf8"))
        req['ingredients'] = ingredients
        dbUtils.setRecipe(dbsession, req)
        return 1
