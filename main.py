from __future__ import print_function
import re
import psutil
import requests
from os import _exit,path,devnull
from sys import stdout
from time import sleep
from random import choice,uniform
from colorama import Fore
from argparse import ArgumentParser
from functools import partial
from traceback import format_exc,print_exc
from user_agent import generate_user_agent
from multiprocessing import Pool,Manager
from selenium import webdriver
from selenium.common.exceptions import *

parser=ArgumentParser()
parser.add_argument('-t','--threads',type=int,help='set the number of threads',default=15)
parser.add_argument('-u','--url',help='set url of the video/set the path of the urls list',default='',required=True)
parser.add_argument('-d','--duration',help='set the duration of the view in seconds',type=float)
parser.add_argument('-p','--proxies',help='set the path to list of proxies')
parser.add_argument('-us','--user-agent',help='set the user agent/set the path of to the list of user agents')
parser.add_argument('-dr','--driver',help='set the webdriver',choices=['chrome','firefox'],default='chrome')
parser.add_argument('-hd','--headless',help='set the webdriver as headless',action='store_true')
parser.add_argument('-s','--slow-start',help='start webdrivers one by one',action='store_true')
args=parser.parse_args()

def exit(exit_code):
	global drivers,pool
	if exit_code==1:
		print_exc()
	try:drivers
	except NameError:pass
	else:
		for driver in drivers:
			try:psutil.Process(driver).terminate()
			except:pass
	try:pool
	except NameError:pass
	else:pool.terminate()
	_exit(exit_code)
def print(message):
	if message.startswith('[ERROR]'):
		colour=Fore.RED
	elif message.startswith('[WARNING]'):
		colour=Fore.YELLOW
	elif message.startswith('[INFO]'):
		colour=Fore.GREEN
	else:
		colour=Fore.RESET
	stdout.write('%s%s%s\n'%(colour,message,Fore.RESET))
def get_proxies():
	if args.proxies:
		proxies=list(filter(None,open(args.proxies,'r').read().split('\n')))
	else:
		proxies=re.findall(re.compile('<td>([\d.]+)</td>'),str(requests.get('https://www.sslproxies.org/').content))
		proxies=['%s:%s'%x for x in list(zip(proxies[0::2],proxies[1::2]))]
	print('[INFO][0] %d proxies successfully loaded!'%len(proxies))
	return proxies
def bot(lock,drivers,exceptions,urls,user_agents,proxies,id):
	try:
		while True:
			url=choice(urls)
			lock.acquire()
			if len(proxies)==0:
				proxies.extend(get_proxies())
			lock.release()
			proxy=proxies.pop()
			print('[INFO][%d] Connecting to %s'%(id,proxy))
			user_agent=choice(user_agents) if args.user_agent else user_agents()
			print('[INFO][%d] Setting user agent to %s'%(id,user_agent))
			try:
				if args.slow_start:
					lock.acquire()
				if args.driver=='chrome':
					chrome_options=webdriver.ChromeOptions()
					chrome_options.add_argument('--proxy-server={}'.format(proxy))
					chrome_options.add_argument('--user-agent={}'.format(user_agent))
					chrome_options.add_argument('--mute-audio')
					if args.headless:
						chrome_options.add_argument('--headless')
					driver=webdriver.Chrome(options=chrome_options)
				else:
					firefox_options=webdriver.FirefoxOptions()
					firefox_options.preferences.update({
						'media.volume_scale':'0.0',
						'general.useragent.override':user_agent,
						'network.proxy.type':1,
						'network.proxy.http':proxy.split(':')[0],
						'network.proxy.http_port':int(proxy.split(':')[1]),
						'network.proxy.ssl':proxy.split(':')[0],
						'network.proxy.ssl_port':int(proxy.split(':')[1])
					})
					if args.headless:
						firefox_options.add_argument('--headless')
					driver=webdriver.Firefox(options=firefox_options,service_log_path=devnull)
				process=driver.service.process
				pid=process.pid
				cpids=[x.pid for x in psutil.Process(pid).children()]
				pids=[pid]+cpids
				drivers.extend(pids)
				if args.slow_start:
					lock.release()
				print('[INFO][%d] Successully started webdriver!'%id)
				driver.set_window_size(320,570)
				driver.set_page_load_timeout(120)
				print('[INFO][%d] Opening %s'%(id,url))
				driver.get(url)
				if not 'ERR_' in driver.page_source:
					print('[INFO][%d] Video successfully loaded!'%id)
					play_button=driver.find_element_by_class_name('ytp-play-button')
					if play_button.get_attribute('title')=='Play (k)':
						play_button.click()
					if args.duration:
						sleep(args.duration)
					else:
						video_duration=driver.find_element_by_class_name('ytp-time-duration').get_attribute('innerHTML')
						sleep(float(sum([int(x)*60**i for i,x in enumerate(video_duration.split(':')[::-1])])))
					print('[INFO][%d] Video successfully viewed!'%id)
				else:
					print('[WARNING][%d] Dead proxy eliminated!'%id)
			except TimeoutException:
				print('[WARNING][%d] Request timed out!'%id)
			except NoSuchWindowException:
				print('[ERROR][%d] Window has been closed unexpectedly!'%id)
			except NoSuchElementException:
				print('[ERROR][%d] Element not found!'%id)
			except ElementNotVisibleException:
				print('[ERROR][%d] Element is not visible!'%id)
			except ElementClickInterceptedException:
				print('[ERROR][%d] Element could not be clicked!'%id)
			finally:
				lock.acquire()
				print('[INFO][%d] Quitting webdriver!'%id)
				driver.quit()
				for pid in pids:
					try:drivers.remove(pid)
					except:pass
				lock.release()
	except KeyboardInterrupt:pass
	except:exceptions.append(format_exc())

if __name__=='__main__':
	try:
		if args.url:
			if path.isfile(args.url):
				urls=list(filter(None,open(args.url,'r').read().split('\n')))
			else:
				urls=[args.url]
		urls=[re.sub(r'\A(?:https?://)?(.*)\Z',r'https://\1',x) for x in urls]
		if args.user_agent:
			if path.isfile(args.user_agent):
				user_agents=list(filter(None,open(args.user_agent,'r').read().split('\n')))
			else:
				user_agents=[args.user_agent]
		else:
			user_agents=generate_user_agent
		manager=Manager()
		lock=manager.Lock()
		drivers=manager.list()
		exceptions=manager.list()
		proxies=manager.list()
		pool=Pool(processes=args.threads)
		pool.map_async(partial(bot,lock,drivers,exceptions,urls,user_agents,proxies),range(1,args.threads+1))
		while True:
			if len(exceptions)>0:
				for e in exceptions:
					print(e)
				exit(2)
			sleep(0.25)
	except KeyboardInterrupt:
		try:exit(0)
		except:pass
	except:exit(1)
