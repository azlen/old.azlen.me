from lib import NotionWebsiteBuilder
from secret import token
import regex as re

import os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--push', action='store_true', help='Commit and push new changes')
parser.add_argument('--forcepush', action='store_true', help='Commit and push new changes')
parser.add_argument('--serve', action='store_true', help='Commit and push new changes')
args = parser.parse_args()

website = NotionWebsiteBuilder(token_v2=token)

sitedata = {
    'wordcount': 0,
    'pagecount': 0,
    'glossary': {}
}

def addGlossaryItem(data):
    match = re.match(r'(.+)\((.+)\):(.+)', data['block']['rawtext'])
    if match != None:
        item, category, glossary_text = match.groups()
        if category not in sitedata['glossary']:
            sitedata['glossary'][category] = {}
        
        sitedata['glossary'][category.strip()][item.strip()] = glossary_text.strip()

def countwords(data):
    block = data['block']
    page = data['page']

    if block['type'] not in ['code', 'callout'] and 'rawtext' in block:
        count = len(block['rawtext'].split())
        sitedata['wordcount'] += count

        #page['wordcount'] = page['wordcount'] + count if 'wordcount' in page else count
        page['wordcount'] += count

def countpages(page):
    page['wordcount'] = 0
    sitedata['pagecount'] += 1

    if 'edited' in page:
        print(page['edited'])

def setflags(page):
    page['flags'] = {
        'new': False,
        'updated': False
    }

def test(page):
    if 'cover' in page:
        print(page['cover'])
    if 'thumbnail' in page:
        print(page['thumbnail'])


website.templates['blocks']['callout']['👉'] = """
<a class="pagecover" href="{{ href }}">
    <img src="{{ cover_image}}" />
</a>
"""

website.templates['blocks']['page'] = """
{% if id in cache %}
<a class="pagelink" href="{{ cache[id].path }}">
    {% if cache[id].thumbnail %}
        <div class="pagelink-icon" style="background-image: url({{ cache[id].thumbnail[0] }})"></div>
    {% endif %}

    <div class="pagelink-text">
        <div class="pagelink-text-title">{{ cache[id].name }}</div>
        <div class="pagelink-text-description">{% if cache[id].description %}{{ cache[id].description }}{% endif %}</div>
    </div>
</a>
{% else %}
ERROR {{ id }}
{% endif %}
"""

def test2(data):
    page_id = data['block']['text'][0][1][0][1]
    if page_id in website.cache:
        data['block']['cover_image'] = website.cache[page_id]['cover'][0]
        data['block']['href'] = website.cache[page_id]['path']
    else:
        print('COVER FOR PAGE ' + page_id + ' NOT FOUND')

website.listen('blocks/callout/🔮', addGlossaryItem)
website.listen('blocks/callout/👉', test2)
website.listen('blocks', countwords)
website.listen('pages', countpages)
website.listen('pages', setflags)
website.listen('pages', test)


website.addCollection('pages', 'https://www.notion.so/eidka/b539082b0b02490580f7fd5872d1798e?v=38b84447673746abb18521983b30abe0', folder='')
website.addCollection('blog', 'https://www.notion.so/eidka/7dc1a478d8274055a1f7b9f04d29057b?v=d4fb4101b07649cd95c5fcf63cc7c232')
website.addCollection('wiki', 'https://www.notion.so/eidka/df41aba6463b4d8cb3b6c2b40b0de634?v=bcea2c4e405441399470592c2a096be9')
website.addCollection('projects', 'https://www.notion.so/eidka/a1b4d1e913f0400d8baf0581caaedea7?v=52e1aaf92d1b4875a16ca2d09c7c60c8')

#for page in website.cache.values():
#    page['flags'] = {
#        'new': False,
#        'updated': False
#    }

from datetime import datetime
def fromiso(iso):
    if type(iso) == str:
        return datetime.fromisoformat(iso)
    elif type(iso) == datetime:
        return iso
    else:
        print(iso)
        print(type(iso))
        print('ERROR WRONG fromiso FORMAT %s' % iso)
        #return datetime.now()
        
website.env.globals['datetime'] = datetime
website.env.globals['fromiso'] = fromiso

#def wordcount_to_freq(wordcount):
#   return 
website.env.filters['wordcount_to_freq'] = lambda x: int(min(200.0 + max(x, 0) / 5000.0 * 19700.0, 19900.0) / 100.0) * 100

website.render({
    'site': sitedata
})

# generate glossary in .ndtl format for Merveille's collaborative wiki
with open(os.path.join('public', 'glossary.ndtl'), 'w') as f:
    for category in sitedata['glossary']:
        f.write(category.upper() + '\n')

        for term, definition in sitedata['glossary'][category].items():
            f.write('  {} : {}\n'.format(term, definition))

# generate twtxt for peer-to-peer discussion feed
twtxt = website.client.get_collection_view("https://www.notion.so/eidka/51c6a2837c4c4d20b843b936f45ff75b?v=78a7ba17c6da434d8cc61232be5d7064")
with open(os.path.join('public', 'twtxt.txt'), 'w') as f:
    entries = twtxt.collection.get_rows()
    entries = list(map(lambda x: x.get_all_properties(), entries))
    entries = list(sorted(entries, key=lambda x: x['created'], reverse=True))

    for row in entries:         
        #date = row['created'].isoformat()   
        # By default `.isoformat()` returns without timezone stamp
        date = row['created'].strftime('%Y-%m-%dT%H:%M:%S+00:00')
        f.write('{}\t{}\n'.format(date, row['text']))

website.saveCache()

print(sitedata['glossary'])

import subprocess, sys
import random

messages = [
    "AUTOMAGIC BUILD",
    "RETICULATING SPLINES",
    "TRANSFERRING VITAL INFORMATION",
    "WRITING WORDS",
    "WORDS HAVE BEEN WRITTEN",
    "NEW CONTENT REPLACES OLD",
    "IN WITH THE NEW OUT WITH THE OLD",
    "THE GIT THAT KEEPS ON GIVING",
    "MAY THE --FORCE BE WITH YOU",
    "CECI N'EST PAS UNE COMMIT",
    "TO UPDATE ONE'S WEBSITE SHOWS TRUE COMMITMENT",
    "ADDED ANOTHER PAGE ABOUT GIRAFFES",
    "RECONCEPTUALIZING MEMEX SOFTWARE PROTOCOL",
    "ADJUSTING BELL CURVES",
    "ALIGNING COVARIANCE MATRICES",
    "INSERTING SUBMLIMINAL MESSAGES",
    "REARRANGING PLANCK UNITS",
    "DECONSTRUCTING CONCEPTUAL PHENOMENA",
    "DECIPHERING SQUIGGLY SYMBOLS",
    "QUARANTINING RADIOACTIVE PAGES",
    "MULTIPLYING UNKNOWN CONSTANTS",
    "REDESCRIBING THE UNDESCRIBABLE",
    "¿COMMIT GIT OR GIT COMMIT?",
    "UNRAVELLING THE ENCYCLOPEDIA",
    "INITIALIZING LINGUISTIC SUPERPOSITION",
    "UPDATING MIND CONTROL MANTRAS",
    "CORRECT HORSE BATTERY STAPLE",
    
]

#if (args.push and did_anything_change) or (args.forcepush):
if args.push:
    subprocess.run(['git', 'add', '-A'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    subprocess.run(['git', 'commit', '-m', '🤖 {} 🤖'.format(random.choice(messages))], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    subprocess.run(['git', 'push'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

if args.serve:
    cmd = "cd {}; python3 -m http.server".format(website.public_dir)
    
    p = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE)
    
    while True:
        out = p.stderr.read(1)
        """if out == '' and p.poll() != None:
            break
        if out != '':
            sys.stdout.write(out)
            sys.stdout.flush()"""