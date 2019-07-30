from notion.client import NotionClient
import regex as re
import os
import shutil
import glob
import jinja2
from html5print import HTMLBeautifier
import jinja2_highlight

import requests
import urllib.parse

# Initialize jinja filesystem
templateLoader = jinja2.FileSystemLoader(searchpath="./templates")
templateEnv = jinja2.Environment(loader=templateLoader, extensions=['jinja2_highlight.HighlightExtension'])

templateEnv.extend(jinja2_highlight_cssclass = 'highlight')
templateEnv.filters['commafy'] = lambda v: "{:,}".format(v)

# Obtain the `token_v2` value by inspecting your browser cookies on a logged-in session on Notion.so
from secret import token
client = NotionClient(token_v2=token)

# Load databases
pages    = client.get_collection_view("https://www.notion.so/eidka/b539082b0b02490580f7fd5872d1798e?v=38b84447673746abb18521983b30abe0")
blog     = client.get_collection_view("https://www.notion.so/eidka/7dc1a478d8274055a1f7b9f04d29057b?v=d4fb4101b07649cd95c5fcf63cc7c232")
wiki     = client.get_collection_view("https://www.notion.so/eidka/df41aba6463b4d8cb3b6c2b40b0de634?v=bcea2c4e405441399470592c2a096be9")
projects = client.get_collection_view("https://www.notion.so/eidka/a1b4d1e913f0400d8baf0581caaedea7?v=52e1aaf92d1b4875a16ca2d09c7c60c8")

glossary = {}

processingQueue = {}

wordcount = 0

def addCollectionToQueue(database, folder):
    collectionArray = []

    for row in database.collection.get_rows():
        props = row.get_all_properties()
        data  = row.get()
        
        if props['published'] == True:
            block_ids = []
            if 'content' in data:
                block_ids = data['content']

            if props["permalink"].strip() == "":
                props["permalink"] = re.sub(" ", "_", props["name"].lower())
            
            path = os.path.join("/", folder, props["permalink"])
            print(path)

            itemData = {
                'block_ids': block_ids,
                'path': path
            }

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

                    before += '<a href="{}">'.format(href)
                    after  += '</a>'

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
                    before += '<a href="{}">'.format(prop[1])
                    after  += '</a>'

                elif prop_type == 'c':
                    before += '<code>'
                    after += '</code>'
            
            #wordcount = wordcount + len(text.split())

            output += before
            output += text
            output += after
        
        else:
            text = item[0]

            #wordcount = wordcount + len(text.split())

            output += text
    
    return output

def componentToHTML(block, lt, nt):
    text = ''
    data = block.get()
    
    title = block.get('properties.title')
    if title != None:
        text = parseText(title)

        try:
            global wordcount
            
            wordcount += len(block.title.split())
            print(len(block.title.split()), wordcount)
        except:
            pass
        

    if block.type == 'text':
        if len(text) > 0:
            return '<p>{}</p>'.format(text)
        else:
            return ''
    elif block.type == 'header':
        return '<h1>{}</h1>'.format(text)
    elif block.type == 'sub_header':
        return '<h2>{}</h2>'.format(text)
    elif block.type == 'sub_sub_header':
        return '<h3>{}</h3>'.format(text)
    elif block.type == 'code':
        lang = data["properties"]["language"][0][0].lower()

        if lang == 'markup': # RESERVED FOR JINJA CODE AND SUCH
            return text

        return '<pre><code>{% highlight \'' + lang + '\' %}' + text + '{% endhighlight %}</code></pre>'
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
                
                glossary[category][item] = glossary_text.strip()
            return ''
        elif icon == '🗑️':
            return ''
        else:
            print(block.get())
            return ''
            ##return '<aside class="sidenote">{}</aside>'.format(text)
        
    elif block.type == 'quote':
        return '<blockquote>{}</blockquote>'.format(text)
    elif block.type == 'image':
        source = block.get('properties.source')[0][0]
        file_id = block.get('file_ids')[0]
        extension = re.match('.*(\..*)', source).group(1)
        
        dest = '/images/{}{}'.format(file_id, extension)

        r = client.session.get(block.source)
        with open('public' + dest, 'wb') as image:
            image.write(r.content)

        return '<img src="{}"/>'.format(dest)
    elif block.type == 'to_do':
        # TO BE IMPLEMENTED
        return ""
    elif block.type == 'divider':
        return '<hr/>'
    elif block.type == 'numbered_list':
        output = ''

        if lt != 'numbered_list':
            output += '<ol>'
        
        output += '<li>{}</li>'.format(text)

        if nt != 'numbered_list':
            output += '</ol>'
        
        return output
    elif block.type == 'bulleted_list':
        output = ''
        
        if lt != 'bulleted_list':
            output += '<ul>'
        
        output += '<li>{}</li>'.format(text)

        if nt != 'bulleted_list':
            output += '</ul>'
        
        return output
    elif block.type == 'column_list':
        block_ids = block.get('content')

        output = '<div style="display: flex">'
        for column_id in block.get('content'):
            column = client.get_block(column_id)
            output += '<div style="flex: {}">'.format(column.get('format.column_ratio'))

            block_ids = column.get('content')
            for i in range(len(block_ids)):
                last_block_type = ''
                if i > 0:
                    last_block_type = client.get_block(block_ids[i-1]).type
                
                next_block_type = ''
                if i < len(block_ids)-1:
                    next_block_type = client.get_block(block_ids[i+1]).type
                
                output += componentToHTML(client.get_block(block_ids[i]), last_block_type, next_block_type)
            
            output += '</div>'
        
        output += '</div>'
        
        return output
    else:
        print('ERROR UNIMPLEMENTED BLOCK TYPE:', block.type)
        return ''

def renderQueue():
    # Remove old files
    for old_file in glob.glob('public/*'):
        if os.path.isfile(old_file):
            os.unlink(old_file)
        else:
            shutil.rmtree(old_file)
    
    os.makedirs('public/images', exist_ok=True)

    src_files = os.listdir('www')
    for file_name in src_files:
        full_file_name = os.path.join('www', file_name)
        if os.path.isfile(full_file_name):
            shutil.copy(full_file_name, 'public')

    for page_id in processingQueue:
        page = processingQueue[page_id]

        page['html'] = ''

        for i in range(len(page['block_ids'])):
            block_id = page['block_ids'][i]
            block = client.get_block(block_id)
            
            last_block_type = ''
            if i > 0:
                last_block_type = client.get_block(page['block_ids'][i-1]).type
            
            next_block_type = ''
            if i < len(page['block_ids'])-1:
                next_block_type = client.get_block(page['block_ids'][i+1]).type
            
            page['html'] += componentToHTML(block, last_block_type, next_block_type)
    
    for page_id in processingQueue:

        page = processingQueue[page_id]
        # Beautifies HTML (and css/js if exists) but also breaks whitespace
        # content = HTMLBeautifier.beautify(content, 4)
        
        # print(page)

        template_data = {
            'content': page['html'],
            'site': {
                'wordcount': wordcount,
                'pagecount': len(processingQueue.keys())
            },
            'page': {
                'title': page['name'],
                'path': page['path']
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

        folder = os.path.join('public', page['path'][1:])
        os.makedirs(folder, exist_ok=True)

        #print(fullpath)
        with open(os.path.join(folder, 'index.html'), 'w') as f:
            f.write(outputText)

        

pageCollection    = addCollectionToQueue(pages, '')
blogCollection    = addCollectionToQueue(blog, 'blog')
wikiCollection    = addCollectionToQueue(wiki, 'wiki')
projectCollection = addCollectionToQueue(projects, 'projects')

renderQueue()


print(glossary)