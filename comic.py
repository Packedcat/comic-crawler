#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import sys
import requests
import traceback
from selenium import webdriver
from multiprocessing import Pool, cpu_count, freeze_support
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


def validatetitle(title):
    rstr = r'[\/\\\:\*\?\"\<\>\|]'
    new_title = re.sub(rstr, "", title).replace(' ', '')
    return new_title


class Chapter():

    def __init__(self, comic_title, comic_dir, chapter_title, chapter_url):
        self.comic_title, self.comic_dir, self.chapter_title, self.chapter_url = comic_title, comic_dir, chapter_title, chapter_url
        self.chapter_dir = os.path.join(self.comic_dir, validatetitle(self.chapter_title))
        if not os.path.exists(self.chapter_dir):
            os.mkdir(self.chapter_dir)
        self.pages = []

    def get_pages(self):
        r_slt = r'onchange="select_page\(\)">([\s\S]*?)</select>'
        r_p = r'<option value="(.*?)".*?>第(\d*?)页<'
        try:
            dcap = dict(DesiredCapabilities.PHANTOMJS)
            dcap['phantomjs.page.settings.loadImages'] = False
            driver = webdriver.PhantomJS(desired_capabilities=dcap)
            driver.get(self.chapter_url)
            text = driver.page_source
            st = re.findall(r_slt, text)[0]
            self.pages = [(int(p[-1]), p[0]) for p in re.findall(r_p, st)]
        except Exception:
            traceback.print_exc()
            self.pages = []
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        finally:
            driver.quit()
            print('Got %d pages in chapter %s' %
                  (len(self.pages), self.chapter_title))
            return self.pages

    def download_chapter(self):
        results = []
        if not self.pages:
            print('No page')
            return None
        mp = Pool(min(8, max(cpu_count(), 4)))
        for page in self.pages:
            results.append(mp.apply_async(self.download_page, (page,)))
        mp.close()
        mp.join()
        num = sum([result.get() for result in results])
        print('Downloaded %d pages' % num)

    def download_page(self, page):
        headers = {
            'use-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36',
            'referer': self.chapter_url
        }
        n = page[0]
        url = page[-1]
        if not os.path.exists(self.chapter_dir):
            os.mkdir(self.chapter_dir)
        path = os.path.join(self.chapter_dir, '%s.%s' % (str(n), url.split('.')[-1]))
        try:
            print('Downloading page %s into file %s' % (n, path))
            res = requests.get('https:%s' % url, headers=headers)
            data = res.content
            with open(path, 'wb') as f:
                f.write(data)
        except Exception:
            e = traceback.format_exc()
            print('Got eorr when downloading picture\n %s' % e)
            return 0
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        else:
            return 1


class Comic():

    def __init__(self, comic_url, comic_title=None, comic_dir=None):
        self.comic_url = comic_url
        n_comic_title, self.des, self.cover, self.chapter_urls = self.get_info()
        self.chapter_num = len(self.chapter_urls)
        self.comic_title = (comic_title if comic_title else n_comic_title)
        self.comic_dir = os.path.abspath((comic_dir if comic_dir else validatetitle(self.comic_title)))
        if not os.path.exists(self.comic_dir):
            os.mkdir(self.comic_dir)
        print('There are %s chapters in comic %s' % (self.chapter_num, self.comic_title))
        self.chapters = {
            info[0]: Chapter(self.comic_title, self.comic_dir, *info) for info in self.chapter_urls
        }
        self.pages = []

    def get_info(self):
        headers = {
            'use-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36',
            'Referer': 'http://manhua.dmzj.com/tags/s.shtml'
        }
        root = 'http://manhua.dmzj.com'
        r_title = r'<span class="anim_title_text"><a href=".*?"><h1>(.*?)</h1></a></span>'
        r_des = r'<meta name=\'description\' content=".*?(介绍.*?)"/>'
        r_cover = r'src="(.*?)" id="cover_pic"/></a>'
        r_cb = r'<div class="cartoon_online_border" >([\s\S]*?)<div class="clearfix"></div>'
        r_cs = r'<li><a title="(.*?)" href="(.*?)" .*?>.*?</a>'
        try:
            text = requests.get(self.comic_url, headers=headers).text
        except ConnectionError:
            traceback.print_exc()
            raise ConnectionError
        title = re.findall(r_title, text)[0]
        cb = re.findall(r_cb, text)[0]
        chapter_urls = [(c[0], '%s%s#@page=1' % (root, c[1])) for c in re.findall(r_cs, cb)]
        cover_url = re.findall(r_cover, text)[0]
        des = re.findall(r_des, text)
        return title, des, cover_url, chapter_urls

    def download_all_chapters(self):
        print('Downloading all chapters of comic %s into dir %s' % (self.comic_title, self.comic_dir))
        for title in self.chapters.keys():
            self.download_chapter(title)

    def download_chapter(self, key, flag=True):
        if not key in self.chapters:
            print('No such chapter %s\nThere are chapters:\n%s' % (key, '\n'.join(self.chapters.keys())))
            return None
        if not self.chapters[key].pages:
            self.pages += self.chapters[key].get_pages()
        self.chapters[key].download_chapter()

if __name__ == '__main__':
    if sys.platform.startswith('win'):
        freeze_support()
    if not sys.argv[1]:
        print('without start url')
    else:
        path = sys.argv[1]
        print('Download comics based on file %s' % path)
        print('Using multi threads...')
        comic = Comic(path)
        comic.download_all_chapters()
