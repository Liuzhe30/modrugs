#%%
import time
import re
import os
import bs4 
import json
import requests
from pandas import read_html
from requests.exceptions import ConnectionError
from tqdm import tqdm
from pprint import pprint
# from functools import reduce
#%%
txt = lambda elem: elem.text.replace('\n', '').strip()

def extract_metadata(soup):
    content = soup.find('div', 'contentBox')
    sub = content.find('p', 'drug-subtitle')
    if sub is None:
        return {'meta' : 'NO METADATA FOUND'}
    keys = list(map(txt, sub.find_all('b')))
    sub = sub.get_text()
    for key in keys:
        sub = sub.replace(key, '<key>')
    sub = [i.strip() for i in sub.split('<key>') if i != '']
    return dict(zip(keys, sub))


def extract_side_meta(soup):
    sidebar_meta = {}
    sidebar = soup.find('div', id='sidebar')
    sections =  ['sideBoxDrugManufacturers', 'sideBoxDrugClass', 'sideBoxRelatedDrugs']
    for section in sections:
        section = sidebar.find('div', section)
        if section is not None:
            title = txt(section.find('div', 'sideBoxTitle'))
            vals = list(map(txt, section.find_all('a')))
            # print(vals)
            sidebar_meta.update({title:vals})
    ratings = sidebar.find('div', 'drug-rating')
    try:
        sidebar_meta['User Rating and Reviews'] = {
            'rating': ratings.find('span', 'rating-score').text,
            'reviews' : ratings.find('span', 'ratings-total').text
            }
    except AttributeError:
        pass
    try:
        sidebar_meta['img'] = sidebar.find('div', id='drug-imprint-primary').find('img')['src']
    except AttributeError:
        pass
    return sidebar_meta

def extract_text(soup, content_box=True):
    content = {}
    stack = []
    level = 1
    pointer = content
    prev_elem = None
    content_soup = soup
    if content_box:
        content_soup = soup.find('div', 'contentBox')
    
    for elem in content_soup.children:
        tag = str(elem.name)
        pointer = content
        if re.match('h[2-6]', tag):
            diff = int(tag[-1]) - level
            if diff:
                if diff < 0:
                    for i in range(abs(diff)):
                        stack.pop()
                    stack.pop()
                    stack.append(txt(elem))
                    prev_elem = elem
                if diff > 0:
                    for i in range(abs(diff)):
                        stack.append(txt(elem))
                        prev_elem = elem
                level += diff
            else:
                stack.pop()
                stack.append(txt(elem))

            for point in stack:
                try:
                    pointer = pointer[point]
                except KeyError:
                    pointer[point] = {'text' : []}
                    pointer = pointer[point]

        elif len(stack) and str(type(elem)) == '<class \'bs4.element.Tag\'>' and str(elem.name) == 'p':
            for point in stack:
                pointer = pointer[point]
            pointer['text'].append(txt(elem))
            prev_elem = elem

        elif len(stack) and str(type(elem)) == '<class \'bs4.element.Tag\'>' and str(elem.name) == 'ul':
            for point in stack:
                pointer = pointer[point]
            lis = []
            for li in elem.find_all('li'):
                lis.append(li.get_text().replace('\n', ' '))
            if prev_elem.name == 'p':
                try:
                    pointer['text'].pop()
                except IndexError:
                    pass
                pointer['text'].append({txt(prev_elem) : lis})
            elif prev_elem.name[0] == 'h':
                pointer['text'].append(lis)
            prev_elem = elem
    return content

def extract_reviews(soup):
    def get_comments(soup, reviews, condition):
        comments = soup.find_all('div', 'ddc-comment')
        for comment in comments: 
            review = {
                'user'              : comment.find('span', 'user-name'),
                'time_on_medication': comment.find('span', 'text-color-muted', string=re.compile('Taken for')),
                'comment_date'      : comment.find('span', 'comment-date'),
                'content'           : comment.find('p', 'ddc-comment-content'),
                'rating'            : comment.find('div', 'rating-score')
            }
            try:
                isthere = reviews[condition]
            except KeyError:
                reviews[condition] = []
            finally:
                for key in review:
                    try:
                        review[key] = txt(review[key])
                    except AttributeError:
                        review[key] = ''
                reviews[condition].append(review)
    reviews = {}
    conditions = soup.find('table', 'data-list')
    if conditions is None:
        get_comments(soup, reviews, 'reviews')
    else:
        condition_pages = conditions.find_all('a', string=re.compile('[0-9]* review'))
        conditions = read_html(str(conditions))[0]['Condition'][:-1]
        for i, condition in enumerate(conditions):
            page = 1
            while True:
                page_link = url(condition_pages[i]['href'] + f'?page={page}')
                r = requests.get(page_link)
                soup = bs4.BeautifulSoup(r.content, 'lxml')
                # print(page, ''.join(re.findall('[0-9]', soup.find('h1').text)))
                if page > 1 and ''.join(re.findall('[0-9]', soup.find('h1').text)) != str(page):
                    # print('page end at ', page)
                    break
                else:
                    get_comments(soup, reviews, condition)
        
                page+=1
    return reviews


#%%
# overview_url  = lambda drug : f'https://www.drugs.com/mtm/{str(drug)}.html'
# monograph_url = lambda drug : f'https://www.drugs.com/monograph/{str(drug)}.html'
# sideeffects_url = lambda drug: f'https://www.drugs.com/sfx/{str(drug)}-side-effects.html'
# professional_url_0 = lambda drug : f'https://www.drugs.com/pro/{str(drug)}.html'
# professional_url_1 = lambda drug : f'https://www.drugs.com/ppa/{str(drug)}.html'
# interactions_url = lambda drug : f'https://www.drugs.com/drug-interactions/{str(drug)}.html'
# dosage_url = lambda drug : f'https://www.drugs.com/dosage/{str(drug)}.html'

url = lambda link : f'https://www.drugs.com{link}'

done = os.listdir('data/')
print(len(done), 'drugs already scraped')
# %%
drugs = {}
with open('alpha.json', 'r') as f:
    drugs = json.load(f)

i, last, goto = 0, None, None
with open('pickles.txt', 'r') as f:
    pickles = f.read()
    if len(pickles) > 1:
        goto = pickles
        print('starting at', goto)
    else:
        print('found nothing pickled')

t1 = time.time()
while True:
    try:    
        for drug, link in tqdm([i for key in drugs for i in drugs[key]]):
            drug = drug.replace('/', ' ')
            last = drug; i += 1
            if goto is not None:
                if goto != last:
                    continue
                else:
                    goto = None
            if drug in done:
                # print('skipping', drug)
                continue
            # print('Scraping', drug, '...') # stdout log?
            try:
                os.mkdir(f'data/{drug}')
            except FileExistsError:
                pass
    
            r = requests.get(url(link))
            soup = bs4.BeautifulSoup(r.content, 'lxml')

            #  metadata
            with open(f'data/{drug}/{drug}_meta.json', 'w') as f:
                content = extract_metadata(soup)
                content.update(extract_side_meta(soup))
                json.dump(content, f, indent=2)
            
            # overview text
            with open(f'data/{drug}/{drug}.json', 'w') as f:
                content = extract_text(soup)
                json.dump(content, f, indent=5)

            tabs_ul = soup.find('ul', 'nav-tabs nav-tabs-collapse vmig')
            if tabs_ul is not None:
                links = {
                    'sfx'       : tabs_ul.find('a', text='Side Effects'),
                    'dose'      : tabs_ul.find('a', text='Dosage'),
                    'pro'       : tabs_ul.find('a', text='Professional'),
                    'inter'     : tabs_ul.find('a', text='Interactions'),
                    'reviews'   : soup.find('p', 'user-reviews-title').find('a')
                }
                # sideffects page
                if links['sfx'] is not None:
                    r = requests.get(url(links['sfx']['href']))
                    soup = bs4.BeautifulSoup(r.content, 'lxml')
                    with open(f'data/{drug}/{drug}_sfx.json', 'w') as f:
                        content = extract_text(soup)
                        json.dump(content, f, indent=5)
                
                # professional page
                if links['pro'] is not None:
                    r = requests.get(url(links['pro']['href']))
                    soup = bs4.BeautifulSoup(r.content, 'lxml') 
                    with open(f'data/{drug}/{drug}_pro.json', 'w') as f:
                        content = extract_text(soup)
                        json.dump(content, f, indent=5)
                    
                # dosage page
                if  links['dose'] is not None:
                    r = requests.get(url(links['dose']['href']))
                    soup = bs4.BeautifulSoup(r.content, 'lxml') 
                    with open(f'data/{drug}/{drug}_dose.json', 'w') as f:
                        content = {}
                        for div in soup.find_all('div', 'Section'):
                            content.update(extract_text(div, content_box=False))
                        json.dump(content, f, indent=5)

                # interactions page
                if links['inter'] is not None:
                    r = requests.get(url(links['inter']['href']))
                    soup = bs4.BeautifulSoup(r.content, 'lxml') 
                    with open(f'data/{drug}/{drug}_inter.json', 'w') as f:
                        content = extract_text(soup)
                        json.dump(content, f, indent=5)

                # reviews 
                if links['reviews'] is not None:
                    r = requests.get(url(links['reviews']['href']))
                    soup = bs4.BeautifulSoup(r.content, 'lxml')
                    with open(f'data/{drug}/{drug}_reviews.json', 'w') as f:
                        content = extract_reviews(soup)
                        json.dump(content, f, indent=4)
        
            with open('pickles.txt', 'w', encoding='utf-8') as f:
                f.write(last)
        
            # time.sleep(2) # god mode off
    except (TimeoutError, ConnectionError):
            print('BOT KILL, CONNECTION SEVERED')
            goto = last
            print('waiting a minute...')
            time.sleep(60)
            continue
    except KeyboardInterrupt:
        break
    break       
print('total time taken', round((time.time() - t1) / 60, 2))
