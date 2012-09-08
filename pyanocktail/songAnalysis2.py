#!/usr/bin/python2
# -*- coding: utf-8 -*-

#  Song Analysis and drinks cooking....
#                    
# Bertrand Verdu  08/08

#import os
#import operator
import math
#import unicodedata
from subprocess import Popen, PIPE, STDOUT
from operator import itemgetter



tonalite_tab = ['Do Majeur', 'Do# Majeur', 'Ré Majeur', 'Ré# Majeur', 'Mi Majeur', 'Fa Majeur', 'Fa# Majeur', 'Sol Majeur', 'Sol# Majeur', 'La Majeur', 'La# Majeur', 'Si Majeur', 'Do Mineur', 'Do# Mineur', 'Ré Mineur', 'Re# Mineur', 'Mi Mineur', 'Fa Mineur', 'Fa# Mineur', 'Sol Mineur', 'Sol# Mineur', 'La Mineur', 'La# Mineur', 'Si Mineur']

class MathEngine(object):
    
    def __init__(self,scrpath):
    
        self.scriptpath = scrpath
        self.tabpompes = []
        self.debug = False
    
    def settabpompes(self,tabpompes):
        self.tabpompes = tabpompes
        
    def settabrecipes(self,tabrecipes,tabpompesdb):
        self.tabrecipes_alc = tabrecipes
        self.tabpompesdb = tabpompesdb
        self.tabrecipes_noalcool = []
        for recipe in tabrecipes:
            if recipe['alcool']==0:
                self.tabrecipes_noalcool.append(recipe)
    def solve(self,style,compind=0.5,tristind=1,nervind=1,alc=0,direct=False,nam=''):
        if direct:
            service = []
            final = "test cocktail: "+nam +"\n"
            cock = ''
            for recip in self.tabrecipes_alc:
                if recip['name']==nam:
                    cock = recip
                    print("cocktail found")
            qty = 5.000/float((int(cock['qte1'])+int(cock['qte2'])+int(cock['qte3'])+int(cock['qte4'])+int(cock['qte5'])+int(cock['qte6'])))
            for ing in self.tabpompesdb:
                if cock['qte1']> 0:
                    if ing['name'] == cock['ing1']:
                        service.append([int(ing['pump']),float(cock['qte1'])*float(ing['time'])*qty/1000])
                if cock['qte2']> 0:
                    if ing['name'] == cock['ing2']:
                        service.append([int(ing['pump']),float(cock['qte2'])*float(ing['time'])*qty/1000])
                if cock['qte3']> 0:
                    if ing['name'] == cock['ing3']:
                        service.append([int(ing['pump']),float(cock['qte3'])*float(ing['time'])*qty/1000])
                if cock['qte4']> 0:
                    if ing['name'] == cock['ing4']:
                        service.append([int(ing['pump']),float(cock['qte4'])*float(ing['time'])*qty/1000])
                if cock['qte5']> 0:
                    if ing['name'] == cock['ing5']:
                        service.append([int(ing['pump']),float(cock['qte5'])*float(ing['time'])*qty/1000])
                if cock['qte6']> 0:
                    if ing['name'] == cock['ing6']:
                        service.append([int(ing['pump']),float(cock['qte6'])*float(ing['time'])*qty/1000])
            print("service = "+str(service))
            return [service, final]
        else:
            self.alc = alc
            if alc == 0:
                self.sansalcool = True
            else:
                self.sansalcool = False
            self.old = style
            scilabprocess = Popen(["cd " + self.scriptpath + " && /usr/bin/scicoslab -nwni -nb -f PIANOCKTAIL.sci"], bufsize= -1, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, universal_newlines=True,close_fds=False)
            if self.debug:
                print("process Scilab lance")
            if self.debug:
                print("Alcool = " + str(alc))
            final = []
            cocotail = []
            tab_alcool = []
            tab_soda = []
            service = []
            #instd.write("[duree,densite,Enervement,Complexite,metrique,tonalite,tempo,cocktail,is_particulier] = PIANOCKTAIL('current.pckt')" + '\n')
            #result = outstd.readlines()
            #while scilabprocess.poll() is None:
            result = unicode(scilabprocess.communicate("exit"+ '\n')[0],errors='replace')
            lines = result.splitlines()
            if self.debug:
                for line in lines:
                    print line
    #        for line in lines:
    #            if str(line).startswith("["):
    #                instd.write('o')
    #                print('choppe')
    #                resultb = outstd.readlines()
    #                linesb = resultb.splitlines()
    #                for line in linesb:
    #                    lines.append(line)
    #        instd.write('exit \n')
    #        outstd.close()
    #        instd.close()
    #        scilabprocess.terminate()
            try:
                if self.old :
                    for line in lines:           
                        if line.startswith('--> cocktail  ='):
                            if lines[lines.index(line) + 1].startswith('[') or lines[lines.index(line) + 2].startswith('['):
                                cocotail = lines[lines.index(line) + 3]
                            else : cocotail = lines[lines.index(line) + 2]
                            if self.debug:
                                print("cocktail detected = " + cocotail)
                        elif line.startswith(' tonalite  ='):
                            if lines[lines.index(line) + 1].startswith('[') or lines[lines.index(line) + 2].startswith('['):
                                tonalite = lines[lines.index(line) + 3]
                            else : tonalite = lines[lines.index(line) + 2]
                            final.append(u"Tonalité = "+tonalite_tab[int(tonalite.split()[0].strip('.'))-1])
                            if self.debug:
                                print(u"Tonalite = " +tonalite_tab[int(tonalite.split()[0].strip('.')) - 1])
                        elif line.startswith(' metrique  ='):
                            if lines[lines.index(line) + 1].startswith('[') or lines[lines.index(line) + 2].startswith('['):
                                metrique = lines[lines.index(line) + 3].split()[0]
                            else : metrique = lines[lines.index(line) + 2].split()[0]
                            if int(metrique.strip('.')) == 2:
                                final.append(u"Métrique = Binaire")
                                if self.debug:
                                    print(u"Metrique = Binaire")
                            elif int(metrique.strip('.')) == 3:
                                final.append(u"Metrique = Ternaire")
                                if self.debug:
                                    print(u"Metrique = Ternaire")
                            else:
                                final.append(u"Metrique incoherente....")
                                if self.debug:
                                    print(u"Metrique incoherente....")
                        elif line.startswith(' duree  ='):
                            if lines[lines.index(line) + 1].startswith('[') or lines[lines.index(line) + 2].startswith('['):
                                duree = lines[lines.index(line) + 3]
                            else : duree = lines[lines.index(line) + 2]
                            print(unicode(duree))
                            final.append(u"Durée du morceau = " + duree.split()[0] + " secondes")
                            if self.debug:
                                print(u"Durée du morceau = " + duree)
                        elif line.startswith(" tempo"):
                            if lines[lines.index(line) + 1].startswith('[') or lines[lines.index(line) + 2].startswith('['):
                                tempo = lines[lines.index(line) + 3]
                            else : tempo = lines[lines.index(line) + 2]
                            final.append("Tempo = "+ tempo.split()[0]+" bpm")
                            if self.debug:
                                print("Tempo = " + tempo.split()[0] + " bpm")              
                    tribegin = sorted(self.tabpompes,key=itemgetter(2))
                    triend = sorted(tribegin,key=itemgetter(1))
                    for i in range(len(triend)):
                        if int(triend[i][1]) > 0:
                            tab_alcool.append(triend[i])
                        elif triend[i][0] not in ('vide','UP','DOWN','purge','diode1','diode2','diode3','diode4','diode5'):
                            tab_soda.append(triend[i])
                    soda_milieu = int(math.floor(float(len(tab_soda)/float(2))))
                    if int(len(tab_soda)) in (1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31):
                        if (5 - int(tab_soda[soda_milieu][4])) <= (5 - int(tab_soda[soda_milieu+1][4])):
                            tab_soda_maj = tab_soda[:soda_milieu]
                            tab_soda_min = tab_soda[soda_milieu:]
                        else :
                            tab_soda_maj = tab_soda[:soda_milieu+1]
                            tab_soda_min = tab_soda[soda_milieu+1:]
                    else : 
                        tab_soda_maj = tab_soda[:soda_milieu]
                        tab_soda_min = tab_soda[soda_milieu:]
                    soda_maj_sorted = sorted(tab_soda_maj,key=itemgetter(4))
                    soda_min_sorted = sorted(tab_soda_min,key=itemgetter(4))
                    indexalcool = float(len(tab_alcool))/float(12)
                    indexsodamaj = float(len(tab_soda_maj))/float(4)
                    indexsodamin = float(len(tab_soda_min))/float(4)
                    if self.debug:
                        print(indexsodamaj)
                        print(indexsodamin)
                        print(cocotail)
                        print(result)
                        #print(str(alc_fort))
                        print(soda_maj_sorted)
                        print(soda_min_sorted)
                   
                    if len(cocotail.split()) > 1:
                        global alc_fort
                        idx = int(math.floor(indexalcool*(float(cocotail.split()[0].strip('alc')))))
                        if len(tab_alcool) > 0 and not self.sansalcool:
                            alc_fort = tab_alcool[idx][0]
                        else : alc_fort = "Pas d\'alcool fort"
                        for i in range(len(self.tabpompes)):
                            if self.tabpompes[i][0] == alc_fort:
                                service.append([i+1,str(float(self.tabpompes[i][7])*float(cocotail.split()[1]))])
                                break
                        if int(cocotail.split()[1]) <= 1:
                            final.append('                      '+cocotail.split()[1]+' '+'dose de '+ alc_fort)
                        else:
                            final.append('                      '+cocotail.split()[1]+' '+'doses de '+ alc_fort)
                        if len(cocotail.split()) > 3:
                            if cocotail.split()[2].strip('s').startswith('j'):
                                idx = int(math.floor(indexsodamaj*(float(cocotail.split()[2].strip('sj')))))
            ##            print str(idx)+' majeur'
                                if len(tab_soda_maj) > 0:
                                    soda_final = tab_soda_maj[idx-1][0]
                                else: soda_final = 'ca manque de soda sucre'
                                if len(tab_soda_min) > 0:
                                    tralala  = tab_soda_min[len(tab_soda_min)-1][0]
                                else : tralala = 'ca manque de soda'
                            else:
                                if cocotail.split()[2].strip('s').startswith('n'):
                                    idx = int(math.floor(indexsodamin*(float(cocotail.split()[2].strip('sn')))))
                                else : idx = 0
            ##            print str(idx)+' mineur'
            ##            print soda_min_sorted
                                if len(tab_soda_min)> 0:
                                    soda_final = tab_soda_min[idx-1][0]
                                else : soda_final = 'ca manque de soda'
                                if len(tab_soda_maj) > 0:
                                    tralala  = tab_soda_maj[0][0]
                                else: tralala = 'ca manque de soda sucre'
                            for i in range(len(self.tabpompes)):
                                if self.tabpompes[i][0] == soda_final:
                                    service.append([i+1,str(float(self.tabpompes[i][7])*float(cocotail.split()[3]))])
                                    break
                            if int(cocotail.split()[3]) <= 1:
                                final.append('                      '+cocotail.split()[3]+' '+'dose de '+ soda_final)
                            else:
                                final.append('                      '+cocotail.split()[3]+' '+'doses de '+ soda_final)
                            if len(cocotail.split()) > 5:
                                for i in range(len(self.tabpompes)):
                                    if self.tabpompes[i][0] == tralala:
                                        service.append([i+1,str(float(self.tabpompes[i][7])*float(cocotail.split()[5]))])
                                        break
                                if int(cocotail.split()[5]) <= 1:
                                    final.append('                      '+cocotail.split()[5]+' '+'dose de '+ tralala)
                                else:
                                    final.append('                      '+cocotail.split()[5]+' '+'doses de '+ tralala)
                    if self.debug:
                        for line in final:
                            try :
                                print(line)
                            except:
                                print("l'unicode me fatigue")
                                print(line)
                    return [service,final]
                else:
                    if self.debug:
                        print("new style !!\n")
                    for line in lines:
                        if line.startswith(' Duree'):
                            duree = line.split()[0].split('=')[1]
                            tristesse = line.split()[1].split('=')[1]
                            enervement = line.split()[2].split('=')[1]
                            final.append(u"Durée du morceau = " + duree + " secondes")
                            final.append('tristesse = '+tristesse)
                            final.append('enervement = '+enervement)
                            if self.debug:
                                print(u"Durée du morceau = " + duree)
                            if self.debug:
                                print("tristesse returned = "+tristesse)
                        elif line.startswith(' Complexite'):
                            complexite = line.split()[0].split('=')[1]
                            metrique = line.split()[1].split('=')[1]
                            tonalite = line.split()[2].split('=')[1]
                            final.append('complexite = '+complexite)
                            if int(metrique.strip('.')) == 2:
                                final.append(u"Métrique = Binaire")
                                if self.debug:
                                    print(u"Metrique = Binaire")
                            elif int(metrique.strip('.')) == 3:
                                final.append(u"Metrique = Ternaire")
                                if self.debug:
                                    print(u"Metrique = Ternaire")
                            else:
                                final.append(u"Metrique incoherente....")
                                if self.debug:
                                    print(u"Metrique incoherente....")
                            final.append(u"Tonalité = "+tonalite_tab[int(tonalite.strip('.'))-1])
                            if self.debug:
                                print(u"Tonalite = " +tonalite_tab[int(tonalite[0].strip('.')) - 1])
                        elif line.startswith(' Tempo'):
                            tempo = line.split()[0].split('=')[1]
                            cocktail = line.split()[1].split('=')[1:]
                            final.append("Tempo = "+ tempo +" bpm")
                            if self.debug:
                                print("Tempo = " + tempo + " bpm")
                    cocktail = ('default',999.999)
                    if self.alc > 0:
                        tabrecipes = self.tabrecipes_alc
                    else:
                        tabrecipes = self.tabrecipes_noalcool
                    for recipe in tabrecipes:
                        if alc >= int(recipe['alcool']):
                            score = math.fabs(float(complexite)*compind - float(recipe['complex'])) + math.fabs(float(tristesse)*tristind - float(recipe['tristesse'])) + math.fabs(float(enervement)*nervind - float(recipe['nerf']))
                            if self.debug:
                                print(recipe['name']+" score = "+str(score))
                            if score < cocktail[1]:
                                cocktail = (recipe['name'],score)
                                cock = recipe
                    final.append(u"Cocktail choisi : "+cocktail[0])
                    if self.debug:
                        print("cocktail found = "+cocktail[0]+" score = "+str(cocktail[1]))
                    qty = 5.000/float((int(cock['qte1'])+int(cock['qte2'])+int(cock['qte3'])+int(cock['qte4'])+int(cock['qte5'])+int(cock['qte6'])))
                    for ing in self.tabpompesdb:
                        if cock['qte1']> 0:
                            if ing['name'] == cock['ing1']:
                                service.append([int(ing['pump']),float(cock['qte1'])*float(ing['time'])*qty/1000])
                        if cock['qte2']> 0:
                            if ing['name'] == cock['ing2']:
                                service.append([int(ing['pump']),float(cock['qte2'])*float(ing['time'])*qty/1000])
                        if cock['qte3']> 0:
                            if ing['name'] == cock['ing3']:
                                service.append([int(ing['pump']),float(cock['qte3'])*float(ing['time'])*qty/1000])
                        if cock['qte4']> 0:
                            if ing['name'] == cock['ing4']:
                                service.append([int(ing['pump']),float(cock['qte4'])*float(ing['time'])*qty/1000])
                        if cock['qte5']> 0:
                            if ing['name'] == cock['ing5']:
                                service.append([int(ing['pump']),float(cock['qte5'])*float(ing['time'])*qty/1000])
                        if cock['qte6']> 0:
                            if ing['name'] == cock['ing6']:
                                service.append([int(ing['pump']),float(cock['qte6'])*float(ing['time'])*qty/1000])
                    print("service = "+str(service))
                    return [service, final]
            except Exception,err:
                final.append("script error: "+err.message)
                return [service, final]      
                
