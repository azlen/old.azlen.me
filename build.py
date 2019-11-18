from notion.client import NotionClient
import regex as re
import os
import shutil
import glob
import jinja2
from html5print import HTMLBeautifier
import jinja2_highlight

from datetime import datetime

import json
import argparse

import requests
import urllib.parse

parser = argparse.ArgumentParser()
parser.add_argument('--cached', action='store_true', help='Use cached pages')
parser.add_argument('--push', action='store_true', help='Commit and push new changes')
parser.add_argument('--forcepush', action='store_true', help='Commit and push new changes')
parser.add_argument('--serve', action='store_true', help='Commit and push new changes')
args = parser.parse_args()

# Initialize jinja filesystem
templateLoader = jinja2.FileSystemLoader(searchpath="./templates")
templateEnv = jinja2.Environment(loader=templateLoader, extensions=['jinja2_highlight.HighlightExtension'])

templateEnv.extend(jinja2_highlight_cssclass = 'highlight')
templateEnv.filters['commafy'] = lambda v: "{:,}".format(v)
templateEnv.filters['flatten'] = lambda A: [y for x in A for y in x]

id_cache = []
def idfy(string_to_idfy):
    #if page_id not in id_cache:
    #    id_cache[page_id] = []

    a = string_to_idfy.lower()
    a = re.sub(r'\s+', '_', a)
    a = re.sub(r'\W+', '', a)

    out = a
    i = 1
    while out in id_cache:
        out = a + str(i)
        i += 1
    
    id_cache.append(out)
    return out

# Obtain the `token_v2` value by inspecting your browser cookies on a logged-in session on Notion.so
from secret import token
client = NotionClient(token_v2=token)

# Load databases
pages    = client.get_collection_view("https://www.notion.so/eidka/b539082b0b02490580f7fd5872d1798e?v=38b84447673746abb18521983b30abe0")
blog     = client.get_collection_view("https://www.notion.so/eidka/7dc1a478d8274055a1f7b9f04d29057b?v=d4fb4101b07649cd95c5fcf63cc7c232")
wiki     = client.get_collection_view("https://www.notion.so/eidka/df41aba6463b4d8cb3b6c2b40b0de634?v=bcea2c4e405441399470592c2a096be9")
projects = client.get_collection_view("https://www.notion.so/eidka/a1b4d1e913f0400d8baf0581caaedea7?v=52e1aaf92d1b4875a16ca2d09c7c60c8")

twtxt    = client.get_collection_view("https://www.notion.so/eidka/51c6a2837c4c4d20b843b936f45ff75b?v=78a7ba17c6da434d8cc61232be5d7064")

temp_dir = '_temp'
public_dir = 'public'

glossary = {}

processingQueue = {}

tableofcontents = []
navigation = []

cache = {}
if args.cached and os.path.exists('.cache.json'):
    with open('.cache.json', 'r') as f:
        _c = json.loads(f.read())
        cache = _c['data']
        glossary = _c['glossary']
did_anything_change = False

wordcount = 0

def addCollectionToQueue(database, folder):
    collectionArray = []

    for row in database.collection.get_rows():
        props = row.get_all_properties()
        data  = row.get()

        #print(data)
        
        if props['published'] == True:
            block_ids = []
            if 'content' in data:
                block_ids = data['content']

            if props["permalink"].strip() == "":
                permalink = props["name"].lower()
                permalink = re.sub(r'[^\w -]', '', permalink) # remove symbols
                permalink = re.sub(r'\s+', '_', permalink.strip()) # convert spaces to underscore
                
                props["permalink"] = permalink
            else:
                if props["permalink"][0] == '/':
                    props["permalink"] = props["permalink"][1:]
            
            path = os.path.join("/", folder, props["permalink"])
            # print(path)

            itemData = {
                'block_ids': block_ids,
                'path': path,
            }

            #if database == pages:
            #    if props['navigation'] == True:
            #        navigation.append(props['name'], itemData)

            #if folder == 'projects':
            #    print(dir(props['date']))
            #    print(type(props['date'].start))
            #    print(props['date'].end)

            #print('updated' in props.keys())

            for key in props:
                itemData[key] = props[key]
            
            if itemData['template'] == None:
                itemData['template'] = 'default'
            
            processingQueue[data['id']] = itemData
            collectionArray.append(itemData)
    
    return collectionArray

def parseText(textitems):
    output = ""
    for item in textitems:
        if len(item) == 2:
            text, props = item

            text = text.replace('\n', '<br/>')

            before = ""
            after = ""

            for prop in props:
                prop_type = prop[0]

                if prop_type == 'p': # internal link
                    link_id = prop[1]
                    text = client.get_block(link_id).name

                    href = ''
                    if link_id in processingQueue:
                        href = processingQueue[link_id]["path"]
                    else:
                        print('BROKEN INTERNAL LINK', link_id)

                    before += '<a href="{}"><span>'.format(href)
                    after  += '</span></a>'

                elif prop_type == 'b': # bold
                    before += '<strong>'
                    after  += '</strong>'
                
                elif prop_type == 'i': # italic
                    before += '<em>'
                    after  += '</em>'
                
                elif prop_type == 's': # strikethrough
                    before += '<s>'
                    after += '</s>'
                
                elif prop_type == 'h': # text color
                    before += '<span style="color: {}">'.format(prop[1])
                    after  += '</span>'
                
                elif prop_type == 'a': # external link
                    before += '<a href="{}" target="_blank"><span>'.format(prop[1])
                    if re.search(r'^\#.+', prop[1]) is None:
                        after  += '</span><svg xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" x="0px" y="0px" viewBox="0 0 100 125" enable-background="new 0 0 100 100" xml:space="preserve" xmlns="http://www.w3.org/2000/svg" style="fill: #ff3392;margin-left: 1px;margin-bottom: 4px;width: 0.5em;height: 0.5em;"><path d="M83.865,97.5H2.5V16.134h45.301v13.635H15.987v54.244h54.244V52.346h13.634V97.5z M97.5,38.564H83.865V25.81L47.947,61.582  l-9.528-9.53l35.917-35.918H61.582V2.5H97.5V38.564z"></path></svg></a>'

                elif prop_type == 'c':
                    before += '<code>'
                    after += '</code>'
                
                elif prop_type == 'd':
                    before += '<span class="tag blue inline-date">'
                    text = prop[1]['start_date']

                    if 'end_date' in prop[1]:
                        text += ' – ' + prop[1]['end_date']
                    
                    after += '</span>'

                else:
                    print("ERROR: UNKNOWN TEXT TYPE '%s'" % prop_type)
                    print(text)
                    print(prop)
            
            #wordcount = wordcount + len(text.split())

            output += before
            output += text
            output += after
        
        else:
            text = item[0]
            
            text = text.replace('\n', '<br/>')

            #wordcount = wordcount + len(text.split())

            output += text
    
    return output

def componentToHTML(block, lt, nt):
    text = ''
    data = block.get()

    self_wordcount = 0
    
    title = block.get('properties.title')
    if title != None:
        text = parseText(title)

        try:
            global wordcount

            self_wordcount = len(block.title.split())
            wordcount += self_wordcount
            print(self_wordcount, wordcount)
        except:
            pass
        
    html = ''

    if block.type == 'text':
        if len(text) > 0:
            html = '<p>{}</p>'.format(text)
        else:
            html = ''
    elif block.type == 'header':
        header_id = idfy(block.title)
        html = '<h1 id="{}">{}</h1>'.format(header_id, text)

        tableofcontents.append([1, block.title, header_id])
    elif block.type == 'sub_header':
        header_id = idfy(block.title)
        html = '<h2 id="{}">{}</h2>'.format(header_id, text)

        tableofcontents.append([2, block.title, header_id])
    elif block.type == 'sub_sub_header':
        header_id = idfy(block.title)
        html = '<h3 id="{}">{}</h3>'.format(header_id, text)

        tableofcontents.append([3, block.title, header_id])
    elif block.type == 'code':
        lang = data["properties"]["language"][0][0].lower()

        if lang == 'markup': # RESERVED FOR JINJA CODE AND SUCH
            html = block.title
        else:
            html = '<pre><code>{% highlight \'' + lang + '\' %}' + text + '{% endhighlight %}</code></pre>'
    elif block.type == 'callout':
        # BASIC IMPLEMENTATION
        # Should there be different kinds of callouts?
        # - Notes that appear to the side of the text
        # - Emphasized notes and asides within text
        # - Right or left
        # - different colours
        # - icon signify anything???

        icon = block.get('format.page_icon')

        if icon == '🔮': # glossary
            title = ''.join(list(map(lambda x: x[0], block.get('properties.title'))))
            match = re.match('(.+)\((.+)\):(.+)', title)
            if match != None:
                item, category, glossary_text = match.groups()
                if category not in glossary:
                    glossary[category] = {}
                
                glossary[category.strip()][item.strip()] = glossary_text.strip()
            html = ''
        elif icon == '🗑️':
            html = ''
        else:
            print(block.get())
            html = ''
            ##return '<aside class="sidenote">{}</aside>'.format(text)
        
    elif block.type == 'quote':
        html = '<blockquote>{}</blockquote>'.format(text)
    elif block.type == 'image':
        source = block.get('properties.source')[0][0]

        file_id = block.get('id')
        extension = re.match('.*(\..*)', source).group(1)

        caption = block.get('properties.caption')

        image_name = file_id + extension
        public_path = os.path.join(public_dir, 'images', image_name)
        temp_path = os.path.join(temp_dir, 'images', image_name)

        if os.path.isfile(public_path):
            shutil.copy2(public_path, temp_path)
        else:
            r = client.session.get(block.source)
            with open(temp_path, 'wb') as image:
                image.write(r.content)

        if caption == None:
            html = '<img src="{}"/>'.format(os.path.join('/images', image_name))
        else:
            html = """
                <figure>
                    <img src="{}"/>
                    <figcaption>{}</figcaption>
                </figure>
            """.format(os.path.join('/images', image_name), caption[0][0])
    elif block.type == 'to_do':
        # TO BE IMPLEMENTED
        html = ""
    elif block.type == 'divider':
        #return '<hr/>'
        html = '<div class="divider"></div>'
    elif block.type == 'numbered_list':
        output = ''

        if lt != 'numbered_list':
            output += '<ol>'
        
        output += '<li>{}</li>'.format(text)

        children = block.get('content')
        
        if children != None:
            children = list(map(client.get_block, children))

            for i in range(len(children)):
                sub_lt = ''
                if i > 0:
                    sub_lt = children[i-1].type
                
                sub_nt = ''
                if i < len(children) - 1:
                    sub_nt = children[i+1].type

                output += componentToHTML(children[i], sub_lt, sub_nt)[0]

        if nt != 'numbered_list':
            output += '</ol>'
        
        html = output
    elif block.type == 'bulleted_list':
        output = ''
        
        if lt != 'bulleted_list':
            output += '<ul>'
        
        output += '<li>{}</li>'.format(text)

        children = block.get('content')

        if children != None:
            children = list(map(client.get_block, children))

            for i in range(len(children)):
                sub_lt = ''
                if i > 0:
                    sub_lt = children[i-1].type
                
                sub_nt = ''
                if i < len(children) - 1:
                    sub_nt = children[i+1].type

                output += componentToHTML(children[i], sub_lt, sub_nt)[0]

        if nt != 'bulleted_list':
            output += '</ul>'
        
        html = output
    elif block.type == 'column_list':
        #block_ids = block.get('content')

        output = '<div class="column-container">'
        for column_id in block.get('content'):
            column = client.get_block(column_id)
            output += '<div class="column" style="flex: {}">'.format(column.get('format.column_ratio'))

            block_ids = column.get('content')
            for i in range(len(block_ids)):
                last_block_type = ''
                if i > 0:
                    last_block_type = client.get_block(block_ids[i-1]).type
                
                next_block_type = ''
                if i < len(block_ids)-1:
                    next_block_type = client.get_block(block_ids[i+1]).type
                
                output += componentToHTML(client.get_block(block_ids[i]), last_block_type, next_block_type)[0]
            
            output += '</div>'
        
        output += '</div>'
        
        html = output
    else:
        print('ERROR UNIMPLEMENTED BLOCK TYPE:', block.type)
        html = ''

    return (html, self_wordcount)

def renderQueue():
    # Remove temp dir if already exists
    if os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir)

    # Remove old files
    """for old_file in glob.glob('public/*'):
        if os.path.isfile(old_file):
            os.unlink(old_file)
        else:
            shutil.rmtree(old_file)"""
    
    os.makedirs(temp_dir, exist_ok=True)
    if args.cached and os.path.exists('public/images'):
        shutil.copytree('public/images', os.path.join(temp_dir, 'images'))
    else:
        os.makedirs('{}/images'.format(temp_dir), exist_ok=True)

    src_files = os.listdir('www')
    for file_name in src_files:
        full_file_name = os.path.join('www', file_name)
        if os.path.isfile(full_file_name):
            shutil.copy(full_file_name, temp_dir)
        elif os.path.isdir(full_file_name):
            shutil.copytree(full_file_name, os.path.join(temp_dir, file_name))

    

    for page_id in processingQueue:
        page = processingQueue[page_id]

        if args.cached and page_id in cache.keys():
            cached_page = cache[page_id]
            
            if cached_page['updated'] <= page['updated'].timestamp():
                page['html'] = cached_page['html']
                page['wordcount'] = cached_page['wordcount']

                global wordcount
                wordcount += page['wordcount']

                continue
        
        global did_anything_change
        did_anything_change = True

        global id_cache
        global tableofcontents
        id_cache = []
        tableofcontents = []

        page['html'] = ''
        page['wordcount'] = 0

        all_blocks = list(map(client.get_block, page['block_ids']))

        #header_types = {'header': 1, 'sub_header': 2, 'sub_sub_header': 3}
        #tableofcontents = list(filter(lambda x: x.type in header_types, all_blocks))
        #tableofcontents = list(map(lambda x: [header_types[x.type], x.get('properties.title')], tableofcontents))
        #print(tableofcontents)

        for i in range(len(all_blocks)):
            #block_id = page['block_ids'][i]
            block = all_blocks[i]

            #if page['path'] == '/wiki/riddles':
            #    print(block.get())
            
            last_block_type = ''
            if i > 0:
                last_block_type = all_blocks[i-1].type
            
            next_block_type = ''
            if i < len(page['block_ids'])-1:
                next_block_type = all_blocks[i+1].type
            
            html, block_wordcount = componentToHTML(block, last_block_type, next_block_type)

            page['html'] += html
            page['wordcount'] += block_wordcount

        if len(tableofcontents) > 0:
            lowest = min(list(list(zip(*tableofcontents))[0]))
            if lowest > 1:
                for i in range(len(tableofcontents)):
                    tableofcontents[i][0] -= (lowest-1)
        
        page['tableofcontents'] = tableofcontents

        page['flags'] = {
            'new': False,
            'updated': False
        }

        if 'posted' in page and page['posted'] != None:
            print(page['posted'].start)
            print(datetime.now().timestamp())
            print(datetime.fromordinal(page['posted'].start.toordinal()).timestamp())
            print(1000*60*60*24*7)
            if datetime.now().timestamp() - datetime.fromordinal(page['posted'].start.toordinal()).timestamp() < (60*60*24*7):
                page['flags']['new'] = True
        
        """if 'updated' in page and page['updated'] != None:
            if datetime.now().timestamp() - page['updated'].start.timestamp() < (1000*60*60*24*7):
                page['flags']['updated'] = True"""


    for item in wikiCollection:
        print(item['name'])

    for page_id in processingQueue:

        page = processingQueue[page_id]
        # Beautifies HTML (and css/js if exists) but also breaks whitespace
        # content = HTMLBeautifier.beautify(content, 4)
        
        # print(page)

        template_data = {
            'content': page['html'],
            'site': {
                'wordcount': wordcount,
                'pagecount': len(processingQueue.keys()),
                'glossary': glossary
            },
            'page': {
                'id': page_id,
                'title': page['name'],
                'path': page['path'],
                'tableofcontents': page['tableofcontents']
            },
            'collection': {
                'blog': blogCollection,
                'pages': pageCollection,
                'wiki': wikiCollection,
                'projects': projectCollection
            }
        }

        template = templateEnv.get_template('{}.html'.format(page['template']))
        outputText = template.render(**template_data)

        #print(outputText)

        temp = templateEnv.from_string(outputText)
        outputText = temp.render(**template_data)

        folder = os.path.join(temp_dir, page['path'][1:])
        os.makedirs(folder, exist_ok=True)

        with open(os.path.join(folder, 'index.html'), 'w') as f:
            f.write(outputText)
    
    with open(os.path.join(temp_dir, 'glossary.ndtl'), 'w') as f:
        for category in glossary:
            f.write(category.upper() + '\n')

            for term, definition in glossary[category].items():
                f.write('  {} : {}\n'.format(term, definition))
    
    with open(os.path.join(temp_dir, 'twtxt.txt'), 'w') as f:
        entries = twtxt.collection.get_rows()
        entries = list(map(lambda x: x.get_all_properties(), entries))
        entries = list(sorted(entries, key=lambda x: x['created'], reverse=True))

        for row in entries:         
            #date = row['created'].isoformat()   
            # By default `.isoformat()` returns without timezone stamp
            date = row['created'].strftime('%Y-%m-%dT%H:%M:%S+00:00')
            f.write('{}\t{}\n'.format(date, row['text']))

    shutil.rmtree(public_dir)
    os.rename(temp_dir, public_dir)

        

pageCollection    = addCollectionToQueue(pages, '')
blogCollection    = addCollectionToQueue(blog, 'blog')
wikiCollection    = addCollectionToQueue(wiki, 'wiki')
projectCollection = addCollectionToQueue(projects, 'projects')

renderQueue()

with open('.newcache.json', 'w') as f:
    cache_data = {}
    for page_id in processingQueue:
        cache_data[page_id] = {
            'updated': processingQueue[page_id]['updated'].timestamp(),
            'wordcount': processingQueue[page_id]['wordcount'],
            'html': processingQueue[page_id]['html'],
            'tableofcontents': processingQueue[page_id]['tableofcontents']
        }
    
    f.write(json.dumps({
        'data': cache_data,
        'glossary': glossary
    }))

if os.path.exists('.cache.json'):
    os.remove('.cache.json')

os.rename('.newcache.json', '.cache.json')

print(glossary)


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
    cmd = "cd {}; python3 -m http.server".format(public_dir)
    
    p = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE)
    
    while True:
        out = p.stderr.read(1)
        if out == '' and p.poll() != None:
            break
        if out != '':
            sys.stdout.write(out)
            sys.stdout.flush()