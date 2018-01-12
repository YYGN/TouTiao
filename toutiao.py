# !/usr/bin/env python
# -*- coding: utf-8 -*-

"""
分析Ajax请求并抓取今日头条美图
"""

import os
import re
from hashlib import md5
from multiprocessing import Pool
from requests import exceptions
import requests
import json
from urllib.parse import urlencode
import pymongo
from bs4 import BeautifulSoup
from config import *


cliet = pymongo.MongoClient(MONGO_URL)
db = cliet[MONGO_DB]
headers = {
    'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'
}

def get_html(offset, keyword):
    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': '20',
        'cur_tab':1,
        'from':'search_tab'
    }
    # 使用urllib库的urlencode将data转换到url中
    url = 'https://www.toutiao.com/search_content/?' + urlencode(data)
    try:
        response = requests.get(url, headers = headers)
        response.raise_for_status()
        return response.text
    except exceptions:
        print('打开网页失败', url)
        return None

def parse_html(html):
    data = json.loads(html)
    # 判断data和 data中是否有'data'键
    if data and 'data' in data.keys():
        for item in data.get('data'):
            # 生成网页地址迭代器
            yield item.get('article_url')

def get_detail(url):
    try:
        response = requests.get(url, headers = headers)
        response.raise_for_status()
        return response.text
    except exceptions:
        print('打开网页失败', url)
        return None
'''
分析网页代码发现，对于不同的图片集，图片地址存放位置不同，
有的存放在 'content' 中，有的存放在 'gallery： JSON.parse' 中，
所以采用两种解析方式提取图片地址
'''

def parse_detail(html, url):
    soup = BeautifulSoup(html, 'lxml')
    result = soup.select('title')
    title = result[0].get_text() if result else ''
    pattern =  re.compile('content: (.*?),', re.S)
    result = re.search(pattern, html)
    if result:
        final_result = re.findall('[a-zA-z]+://[^\s]*', result.group(1))
        images = [item[:-6] for item in final_result]
        return {
            'title': title,
            'url': url,
            'images': images
        }
    else:
        pattern = re.compile('gallery: JSON.parse\("(.*)"\)', re.S)
        result = re.search(pattern, html)
        if result:
            data = json.loads(result.group(1).replace('\\', ''))
            if data and 'sub_images' in data:
                sub_images = data.get('sub_images')
                images = [item.get('url') for item in sub_images]
                return {
                    'title': title,
                    'url': url,
                    'images': images
        }

def save_to_mongo(result):
    try:
        if db[MONGO_TABLE].insert(result):
            print('存储到MongoDB成功',result)
    except Exception:
        print('存储到MONGODB失败')


def save_image(url):
    content = requests.get(url).content
    folder_path = "D:\\TouTiao\\"
    if not os.path.exists(folder_path):
        os.mkdir(folder_path)
    file_path = folder_path + md5(content).hexdigest() + '.jpg'
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()
    else:
        print('文件已经存在了', url)

def main(offset):
    html = get_html(offset, KEYWORD)
    for url in parse_html(html):
        # 发现有的时候会突然抓到一个广告，所以加个条件筛选一下
        if url != None:
            html = get_detail(url)
            result = parse_detail(html, url)
            save_to_mongo(result)
            for link in result['images']:
                print('正在保存图片%s' % link)
                save_image(link)




if __name__ == '__main__':
    pool = Pool()
    pages = [x*20 for x in range(1, 7)]
    pool.map(main, pages)
    pool.close()
    pool.join()
