import os
import sys
import re
import logging
import time
import csv
import smtplib
import mechanicalsoup
from ConfigParser import SafeConfigParser
from BeautifulSoup import BeautifulSoup
from collections import defaultdict

# CONSTANTS
LINK_CASERMA = 'build.php?tt=1&id=39'
LINK_CAMPI = 'dorf1.php'
LINK_COSTRUZIONI = 'build.php'
LINK_SK_TT = 'tt=1&id=39'
LINK_FIELD = 'build.php?id='

# LOGGER
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# create a file handler
handler_file = logging.FileHandler('TravianBot.log')
handler_file.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
# create a logging format
#formatter = logging.Formatter('%(asctime)s - %(name)16s - %(levelname)8s - %(message)s')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
handler_file.setFormatter(formatter)
handler.setFormatter(formatter)
# add the handlers to the logger
#logger.addHandler(handler_file)
logger.addHandler(handler)


class TravianBot:
    """ This class contains the travian session information """
    def __init__(self):
        logger.info('Starting TravianBot')
        self.base_path = os.path.dirname(os.path.realpath(__file__))
        self.cfg_file=str.replace(__file__,'.py','.cfg')
        # Loading Settings
        logger.info('Loading Settings from [%s]', self.cfg_file)
        self.load_config()
        self.username = self.settings['username']
        self.password = self.settings['password']
        #self.server = self.settings['server_url']
        #DATA INIT
        self.villages = list()
        self.job_todo_list = []
        #self.resourses = defaultdict(int)
        #self.fields = defaultdict(list)
        self.farms = []
        self.browser = mechanicalsoup.StatefulBrowser(
            soup_config={'features': 'lxml'},
            #soup_config={'features': 'html.parser'},
            raise_on_404=True,
        )
        self.browser.addheaders = [('User-agent', 'Firefox')]
        
        if self.settings['debug']: self.browser.set_verbose(2)

    def load_config(self):
        config = SafeConfigParser(allow_no_value=True)
        config.read(self.cfg_file)
        settings_dict = { 'server_url' : config.get('ACCOUNT', 'SERVER'),
                        'username' : config.get('ACCOUNT', 'USERNAME'),
                        'password' : config.get('ACCOUNT', 'PASSWORD'),
                        'evade' : config.get('SETTINGS', 'AUTO_EVADE_ATK'),
                        'debug' : config.get('BOT',  'DEBUG_MODE'),
                        'poll_int' : int(config.get('BOT',  'POLL_INTERVEAL')),
                        'mail_from' : config.get('MAIL',  'MAILUSER'),
                        'pass_from' : config.get('MAIL',  'MAILPASS'),
                        'mail_to' : config.get('MAIL',  'DESTMAIL') }
        self.settings=settings_dict
        return settings_dict
    
    def notify(self, _msg, _subject):
        msg = "\r\n".join([
          "From: "+self.settings['mail_from'],
          "To: "+self.settings['mail_to'],
          "Subject: " + str(_subject),
          "",
          str(_msg) + "\n\n\n\nSended by TravianBot"
          ])
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.login(self.settings['mail_from'],self.settings['pass_from'])
        server.sendmail(self.settings['mail_from'], [self.settings['mail_to']], msg)
        server.quit()

    def get_poll_interveal(self):
        return self.settings['poll_int']

    def login(self):
        """ Init session in travian """
        self.browser.open(self.settings['server_url'] + 'login.php')
        page = self.browser.get_current_page()
        logger.info("Starting Login in server:[%s]", str(page.title.text) )
        self.browser.select_form (nr=0)
        self.browser["name"] = self.settings['username']
        self.browser["password"] = self.settings['password']
        resp = self.browser.submit_selected()
        logger.info("Login completed with resp[%s]", str(resp))
        return resp

    def logout(self):
        """ Exit session """
        resp = self.browser.open(self.settings['server_url'] + 'logout.php')
        page = self.browser.get_current_page()
        logger.info("Logout completed with resp[%s]", str(resp))
        self.browser.close()

    def load_villages_list(self):
        """ Parse village list """
        self.browser.open(self.settings['server_url'] + LINK_CAMPI)
        page = self.browser.get_current_page()
        li_elems = page.find('div', {'id': 'sidebarBoxVillagelist'}).find_all('li')
        for idx,li in enumerate(li_elems):
            village = {'name': li.a.div.text.encode('ascii','ignore'), 'id': li.a['href']}
            logger.debug("Found Village [%s]", str(village))
            self.villages.append(village)

    def load_villages_data(self):
        """ Parse ALL data """
        for idx,village in enumerate(self.villages):
            self.browser.open(self.settings['server_url'] + LINK_CAMPI + str(village['id']))
            page = self.browser.get_current_page()
            self.villages[idx]['res'] = self.parse_resourses(page)
            self.villages[idx]['work_left'] = self.parse_work(page)

    def print_villages_list(self):
        """ Parse village list """
        for idx,village in enumerate(self.villages):
            logger.info("Village [%s]", str(village))

    def get_resourses(self):
        """ Parse resourses """
        for idx,village in enumerate(self.villages):
            self.browser.open(self.settings['server_url'] + LINK_CAMPI + str(village['id']))
            page = self.browser.get_current_page()
            self.villages[idx]['res'] = self.parse_resourses(page)

    def parse_resourses(self, bs4Page1):
        """ Parse resourses """
        resourses = defaultdict(int)
        resourses['wood'] = int(re.sub("[^0-9]", "", bs4Page1.find('span', {'id': 'l1'}).text))
        resourses['clay'] = int(re.sub("[^0-9]", "", bs4Page1.find('span', {'id': 'l2'}).text))
        resourses['iron'] = int(re.sub("[^0-9]", "", bs4Page1.find('span', {'id': 'l3'}).text))
        resourses['cereal'] = int(re.sub("[^0-9]", "", bs4Page1.find('span', {'id': 'l4'}).text))
        return resourses

    def get_troops(self):
        """ Parse resourses """
        for idx,village in enumerate(self.villages):
            self.browser.open(self.settings['server_url'] + LINK_CASERMA + '&' + str(village['id'][1:-1]))
            page = self.browser.get_current_page()
            self.villages[idx]['tt'] = self.parse_troops(page)

    def parse_troops(self, bs4PageTT):
        """ Parse resourses """
        troops = defaultdict(int)
        incoming_raid = bs4PageTT.find_all('table', {'class': 'troop_details inRaid'})
        troops['incoming_raid_num'] = len( incoming_raid )
        #print(troops['incoming_raid_num'])
        
        #incoming_supply = bs4PageTT.find_all('table', {'class': 'troop_details inSupply'})
        #troops['incoming_supply_num'] = len( incoming_supply )
        #print(troops['incoming_supply_num'])
        
        #outgoing_raid = bs4PageTT.find_all('table', {'class': 'troop_details outRaid'})
        #troops['outgoing_raid_num'] = len( outgoing_raid )
        #print(troops['outgoing_raid_num'])
        
        #outgoing_supply = bs4PageTT.find_all('table', {'class': 'troop_details outSupply'})
        #troops['outgoing_supply_num'] = len( outgoing_supply )
        #print(troops['outgoing_supply_num'])
        return troops

    def get_work(self):
        """ Parse resourses """
        for idx,village in enumerate(self.villages):
            self.browser.open(self.settings['server_url'] + LINK_CAMPI + str(village['id']))
            page = self.browser.get_current_page()
            self.villages[idx]['work_left'] = self.parse_work(page)

    def parse_work(self, bs4PageTT):
        """ Parse resourses """
        troops = defaultdict(int)
        work_div = bs4PageTT.find('div', {'class': 'boxes buildingList'})
        if (work_div == None):
            logger.debug('no work')
            return 0
        else:
            work_duration_sec = int(work_div.find('div', {'class': 'buildDuration'}).span['value'])
            logger.debug('work left in seconds: %d', work_duration_sec)
            return work_duration_sec

    def build_field(self, v_name, buid_id, level):
        """ Parse resourses """
        for idx,village in enumerate(self.villages):
            if (village['name'] == v_name):
                self.browser.open(self.settings['server_url'] + LINK_FIELD + str(buid_id)  + '&' + str(village['id'][1:-1]) )
                page = self.browser.get_current_page()
                curr_level = int(re.sub("[^0-9]", "", page.find('span', {'class': 'level'}).text ) )
                if level <= curr_level:
                    logger.info('[%s][BUILDFIELD] level already built [%d]', village['name'], curr_level)
                    return 1
                else:
                    logger.info('[%s][BUILDFIELD] level still to be build [%d]', village['name'], curr_level)
                butt_con = page.find('div', {'class': 'upgradeButtonsContainer section2Enabled'})
                if butt_con == None:
                    logger.info('[%s][BUILDFIELD] button not enabled: exiting', village['name'])
                    return -1
                else:
                    bbutton = butt_con.find('div', {'class': 'section1'}).button
                    jsbuild = bbutton['onclick'][24:-16]
                    #print('jsbuild:' + jsbuild)
                    if 'gold' in bbutton['class'] :
                        logger.info('[%s][BUILDFIELD] only gold avaiable: exiting', village['name'])
                        return -1
                    else:
                        resp = self.browser.open(self.settings['server_url'] + jsbuild )
                        logger.info('[%s][BUILDFIELD] BuildField completed with resp[%s]', village['name'], str(resp))
                        return 0

    def load_build_jobs(self):
        with open(self.base_path +'/'+ 'build_jobs.csv') as csvfile:
            #csv.reader(csvfile, delimiter=' ', quotechar='|')
            reader = csv.reader(csvfile, delimiter='|')
            for idx, row in enumerate(reader):
                logger.debug('CSV Headers: %s, %s, %d, %d', row[0], row[1], row[2], row[3])
                if(idx > 0):
                    job = {'VillageName': str(row[0]),'BuildType': str(row[1]),'BuildID': int(row[2]),'BuildLvl': int(row[3])}
                    self.job_todo_list.append(job)
                    logger.debug('Scheduled JOB : %s', job)

    def get_build_jobs(self, _villageName):
        import csv
        job_todo_list_4village = []
        for idx, job in enumerate(self.job_todo_list):
            if(job['VillageName'] == _villageName):
                job_todo_list_4village.append(job)
        return job_todo_list_4village

def main():
    tb = TravianBot()
    tb.login()
    tb.load_villages_list()
    try:
        while True:
            logger.info('Loading Villages Data...')
            tb.load_villages_data()
            logger.info('Loading Troops Data...')
            tb.get_troops()
            logger.info('Loading Jobs Data...')
            tb.load_build_jobs()
            #tb.print_villages_list()
            for village in tb.villages:
                if village['work_left'] == 0:
                    logger.info("[%s][JOB] No work in progress in this village", str(village['name']))
                    #add some work if needed
                    job_idx = 0
                    jobList = tb.get_build_jobs(village['name'])
                    jobListLen = len(jobList)
                    logger.info('[%s][JOB] Found %d jobs scheduled for this village',village['name'], jobListLen)
                    jobRes=1
                    while (job_idx < jobListLen and jobRes > 0 ):
                        currJob = jobList[job_idx]
                        jobRes=tb.build_field(currJob['VillageName'], currJob['BuildID'], currJob['BuildLvl'])
                        job_idx = job_idx + 1
                else:
                    logger.info("[%s][JOB] Work already in progress on this village", str(village['name']))
                if village['tt']['incoming_raid_num'] > 0:
                    logger.info("[%s][TROOP] Village IS UNDER ATTACK!!!", str(village['name']))
                    tb.notify('Village '+str(village['name'])+' IS UNDER ATTACK!!!',
                           'Village '+str(village['name'])+' IS UNDER ATTACK!!!')
                    logger.info("[%s][TROOP] Evade attack on Village", str(village['name']))
                else:
                    logger.info("[%s][TROOP] No Attack on this Village", str(village['name']))
            logger.info('Going to sleep for %d seconds', tb.get_poll_interveal())
            time.sleep(tb.get_poll_interveal())
    except KeyboardInterrupt:
        tb.logout()

if __name__ == '__main__':
    try:
        ret = main()
    except KeyboardInterrupt:
        ret = 0
sys.exit(ret)