#%%
import requests
import json
import bs4
from tqdm import tqdm
import time
from pprint import pprint as pp
#%%
drugs = {}
alpha = list('abcdefghijklmnopqrstuvwxyz')
alpha = [i+j for i in alpha for j in alpha]

def update_list(soup, by):
    ul = soup.find('ul', 'ddc-list-column-2')
    if ul is None:
        ul = soup.find('ul', 'ddc-list-unstyled')       
    for li in ul.find_all('li'):
        try:
            d = drugs[by]
        except KeyError:
            drugs[by] = []
        finally:
            drugs[by].append((li.text, li.find('a')['href']))

for by in alpha:
    # print(by, end='\t')
    r = requests.get(f'https://www.drugs.com/alpha/{by}.html')
    if r.status_code == 200:
        soup = bs4.BeautifulSoup(r.text, 'lxml')
        page = soup.find('div', 'contentBox').find('h1').text.split(':')[1].strip().lower()
        print(page, by)
        if page == by:
            update_list(soup, by)
            # soup = bs4.BeautifulSoup(requests.get(f'https://www.drugs.com/alpha/{by}.html?pro=1').text, 'lxml')
            # print(by)
            # update_list(soup=soup, by=by)
    else:
        print(by, r.status_code)
    
with open('alpha.json', 'w') as f:
    json.dump(drugs, f, indent = 4)

#%%
with open('alpha.json', 'r') as f:
    drugs = json.load(f)
    count = 0
    for i in drugs:
        count += len(drugs[i])
    print(count)
# %%
