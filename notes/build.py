import json
import jinja2
import os
import glob
import shutil
import shortuuid
from ftfy import fix_encoding
import re
from pyhiccup.core import convert

templateLoader = jinja2.FileSystemLoader(searchpath="./templates")
env = jinja2.Environment(loader=templateLoader, extensions=['jinja2_highlight.HighlightExtension'])

wordcount = 0

page_uuids = {}
page_names = {}

block_ids = {}

references = {}
_linksTo = []

page_data = {}

def collectIDs(page):
    pagestring = json.dumps(page)
    if '#Private' in pagestring:
        print('Private page: [[' + page['title'] + ']]')
        return

    uuid = shortuuid.uuid(name=page['title'])[:8]

    collectChildIDs(page)

    page_uuids[page['title']] = uuid
    page_names[uuid] = page['title']
    
def collectChildIDs(object):
    if 'children' in object.keys():
        for child in object['children']:
            block_ids[child['uid']] = child
            collectChildIDs(child)

def processPage(page):
    title = page['title']
    if title not in page_uuids:
        return

    uuid = page_uuids[title]

    children = []

    if 'children' in page.keys():
        for child in page['children']:
            children.append({
                'html': renderMarkdown(fix_encoding(child['string'])) + renderBullets(child)
            })
    
    template_data = {
        'title': renderMarkdown(title),
        'blocks': children,
        'uuid': uuid,
        'references': []
    }

    global _linksTo

    for item in _linksTo:
        item['link_from'] = uuid
        item['title'] = renderMarkdown(title)
        item['text'] = renderMarkdown(item['text'], ignoreLinks=True)

        #if item['uuid'] == uuid:
        #    continue

        if item['link_to'] in references.keys():
            references[item['link_to']].append(item)
        else:
            references[item['link_to']] = [item]
    
    _linksTo = []

    page_data[title] = template_data

def renderPage(page, directory='./', template='template.html', filename='index.html'):
    templateHTML = env.get_template(template)

    if page['title'] not in page_data:
        return

    template_data = page_data[page['title']]

    template_data['website_wordcount'] = wordcount
    template_data['website_pages'] = len(page_names)

    uuid = template_data['uuid']

    if uuid in references:
        template_data['references'] = references[uuid]

    outputHTML = templateHTML.render(**template_data)

    os.makedirs(os.path.join(directory, template_data['uuid']), exist_ok=True)

    with open(os.path.join(directory, template_data['uuid'], filename), 'w') as f:
        f.write(outputHTML)
        f.close()

def renderBullets(block):
    if 'children' not in block.keys():
        return ''
    
    output = '<ul>'
    for child in block['children']:
        output += '<li>'
        output += renderMarkdown(child['string'])

        if 'children' in child.keys():
            output += renderBullets(child)
        
        output += '</li>'
    
    output += '</ul>'

    return output

def _processInternalLink(match, block):
    name = match.group(1)
    if name in page_uuids:
        uuid = page_uuids[name]
        _linksTo.append({'link_to': uuid, 'text': block})
        return '<a class="internal" data-uuid="' + uuid + '" href="/' + uuid + '">' + renderMarkdown(name) + '</a>'
    else:
        return '<a class="internal private" href="#">' + renderMarkdown(name) + '</a>'

def renderMarkdown(text, ignoreLinks=False):
    if ':hiccup' in text:
        # THIS DOES NOT WORK WELL !!! VERY BROKEN
        print(text)

        data = re.sub(r'\n', '', text.strip())
        data = re.sub(r'(\[\s*?):([\w-]+)', r'\1"\2",', data)
        data = re.sub(r':([\w-]+)', r'"\1":', data)
        data = re.sub(r'([\}\]\:][\s]*?)(\w+)([\s]*?[\[\{\]])', r'\1"\2"\3', data)
        data = re.sub(r'([\}\]\"])([\s\n]*?)([\[\{\"])', r'\1,\2\3', data)

        print(data[9:])

        #print(data[10:])
        #print(json.loads(data[10:]))
        return convert(json.loads(data[9:]))

    if ignoreLinks == False:
        global wordcount
        wordcount += len(text.split())

    text = re.sub(r'\!\[([^\[\]]*?)\]\((.+?)\)', r'<img src="\2" alt="1" />', text)
    if ignoreLinks:
        text = re.sub(r'\[\[(.+?)\]\]', r'\1', text)
        text = re.sub(r'\[([^\[\]]+?)\]\((.+?)\)', r'\1', text)
    else:
        text = re.sub(r'\[\[(.+?)\]\]', lambda x: _processInternalLink(x, text), text)
        text = re.sub(r'\[([^\[\]]+?)\]\((.+?)\)', r'<a class="external" href="\2" target="_blank">\1</a>', text)
    
    text = re.sub(r'\n', r'<br>', text)
    text = re.sub(r'#(\[\[(.+?)\]\]|\w+)', r'<h2>\1</h2>', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\_\_(.*?)\_\_', r'<em>\1</em>', text)
    text = re.sub(r'\~\~(.+?)\~\~', r'<s>\1</s>', text)
    text = re.sub(r'\^\^(.+?)\^\^', r'<span class="highlight">\1</span>', text)
    text = re.sub(r'\`(.+?)\`', r'<code>\1</code>', text)
    text = re.sub(r'\(\((.+?)\)\)', lambda x: renderMarkdown(block_ids[x.group(1)]['string'], ignoreLinks=True), text)

    return text

with open('azlen.json', 'r') as f:
    data = json.loads(f.read())

for page in data:
    collectIDs(page)

for page in data:
    processPage(page)

pagecount = len(page_data.keys())

files = glob.glob('./public/*')
for f in files:
    if os.path.isdir(f):
        shutil.rmtree(f)
    else:
        os.remove(f)

# initialize build directory
src_files = os.listdir('./www')
for file_name in src_files:
    full_file_name = os.path.join('./www', file_name)
    if os.path.isfile(full_file_name):
        shutil.copy(full_file_name, './public')
    elif os.path.isdir(full_file_name):
        shutil.copytree(full_file_name, os.path.join('./public', file_name))

for page in data:
    renderPage(page, './public', template='template.html')
    renderPage(page, './public', template='embed.html', filename='embed.html')
    renderPage(page, './public', template='page.html', filename='page.html')


# run through twice so that you can put jinja/html directly into Notion
# perhaps this feature could be made optional
#template = env.from_string(outputHTML)
#outputHTML = template.render(**template_data)