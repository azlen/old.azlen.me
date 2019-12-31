from notion.client import NotionClient
from notion.collection import NotionDate
import regex as re
import shutil
from datetime import datetime
import json
import os

import jinja2
#from html5print import HTMLBeautifier
import jinja2_highlight

import requests
import urllib.parse

# Obtain the `token_v2` value by inspecting your browser cookies on a logged-in session on Notion.so
from secret import token
#client = NotionClient(token_v2=token)

templates = {
    'blocks': {
        'text': '<p>{{ text }}</p>',
        'header': '<h1 id="{{ header_id }}">{{ text }}</h1>',
        'sub_header': '<h2 id="{{ header_id }}">{{ text }}</h2>',
        'sub_sub_header': '<h3 id="{{ header_id }}">{{ text }}</h3>',
        'code': {
            'markup': '{{ rawtext }}',
            'other': '<pre><code>{% highlight {{ code_lang }} %} {{ text }} {% endhighlight %}</code></pre>'
        },
        'callout': {},
        'quote': '<blockquote>{{ text }}</blockquote>',
        'image': """
            {% if caption %}
                <figure>
                    <img src="{{ image_path }}"/>
                    <figcaption>{{ caption }}</figcaption>
                </figure>
            {% else %}
                <img src="{{ image_path }}"/>
            {% endif %}
        """,
        'todo': '',
        'divider': '<div class="divider"></div>',
        'numbered_list': '<ol>{% for li in children %}{{ render(li) }}{% endfor %}</ol>',
        'bulleted_list': '<ul>{% for li in children %}{{ render(li) }}{% endfor %}</ul>',
        'list_item': '<li>{{ text }}</li>{% if children %}{% for sub_list in children %}{{ render(sub_list) }}{% endfor %}{% endif %}',
        'column_list': """
            <div class="column-container">
                {% for col in columns %}
                <div class="column" style="flex: {{ col.column_ratio }}">
                    {% for block in col.children %}
                        {{ render(block) }}
                    {% endfor %}
                </div>
                {% endfor %}
            </div>
        """

    },
    "text": {
        'p': '<a href="{{ href }}"><span>{{ text }}</span></a>',                     # internal link
        'b': '<strong>{{ text }}</strong>',                             # bold
        'i': '<em>{{ text }}</em>',                                     # italic
        's': '<s>{{ text }}</s>',                                       # strikethrough
        'h': '<span style="color: {{ color }}">{{ text }}</span>',      # text color
        'a': """
            <a href="{{ href }}" target="_blank">
                <span>{{ text }}</span>
                <svg xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" x="0px" y="0px" viewBox="0 0 100 125" enable-background="new 0 0 100 100" xml:space="preserve" xmlns="http://www.w3.org/2000/svg" style="fill: #ff3392;margin-left: 1px;margin-bottom: 4px;width: 0.5em;height: 0.5em;">
                    <path d="M83.865,97.5H2.5V16.134h45.301v13.635H15.987v54.244h54.244V52.346h13.634V97.5z M97.5,38.564H83.865V25.81L47.947,61.582  l-9.528-9.53l35.917-35.918H61.582V2.5H97.5V38.564z"></path>
                </svg>
            </a>
        """,                                                            # external link
        'c': '<code>{{ text }}</code>',                                 # code
        'd': '<span class="tag blue inline-date">{{ text }}</span>',    # date
    }
}

# Load databases
#pages    = client.get_collection_view("https://www.notion.so/eidka/b539082b0b02490580f7fd5872d1798e?v=38b84447673746abb18521983b30abe0")
#blog     = client.get_collection_view("https://www.notion.so/eidka/7dc1a478d8274055a1f7b9f04d29057b?v=d4fb4101b07649cd95c5fcf63cc7c232")
#wiki     = client.get_collection_view("https://www.notion.so/eidka/df41aba6463b4d8cb3b6c2b40b0de634?v=bcea2c4e405441399470592c2a096be9")
#projects = client.get_collection_view("https://www.notion.so/eidka/a1b4d1e913f0400d8baf0581caaedea7?v=52e1aaf92d1b4875a16ca2d09c7c60c8")

# Initialize jinja filesystem

"""
templateLoader = jinja2.FileSystemLoader(searchpath="./templates")
templateEnv = jinja2.Environment(loader=templateLoader, extensions=['jinja2_highlight.HighlightExtension'])

templateEnv.extend(jinja2_highlight_cssclass = 'highlight')
templateEnv.filters['commafy'] = lambda v: "{:,}".format(v)
templateEnv.filters['flatten'] = lambda A: [y for x in A for y in x]

def test(c):
    return {'test': 1}

@jinja2.contextfunction
def jinja_render(c, data):
    #return dict(filter(lambda x: not callable(x[1]), c.items()))
    return test(c)

#tmpl = 
#    {% for key, value in context().items() %}
#        {{ key }}:{{ value }}
#    {% endfor %}
#

template = jinja2.Template(tmpl)
template.globals['context'] = get_context
context = {'a': 1, 'b': 2, 'c': 3}
print(template.render(**context))
"""

def isoformat(date):
    if date != None:
        return date.isoformat()

class NotionWebsiteBuilder:
    id_cache = []

    cache = {}
    old_cache = {}
    
    collections = {}

    callbacks = {}

    def __init__(self, token_v2, public_dir='./public', build_dir='./temp', cache_dir='./cache', init_dir='./www', template_dir='./templates'):
        self.client = NotionClient(token_v2=token_v2)

        self.public_dir = public_dir        # public directory for final static website
        self.build_dir = build_dir          # temporary build directory, deleted after use
        self.cache_dir = cache_dir          # store cached files here
        self.init_dir = init_dir            # directly copied over to initialize public directory
        self.template_dir = template_dir    # html templates along with associated css and svg

        os.makedirs(cache_dir, exist_ok=True)
        #os.makedirs(build_dir, exist_ok=True)

        # initialize jinja2 template environment
        templateLoader = jinja2.FileSystemLoader(searchpath="./templates")
        self.env = jinja2.Environment(loader=templateLoader, extensions=['jinja2_highlight.HighlightExtension'])

        # add specific functionality to jinja2 environment
        self.env.extend(jinja2_highlight_cssclass = 'highlight')               # code highlighting
        self.env.filters['commafy'] = lambda v: "{:,}".format(v)               # format number with commas 1200 -> "1,200"
        self.env.filters['flatten'] = lambda A: [y for x in A for y in x]      # flatten array? I'm not sure where I'm using this

        # initialize and load cache
        self.loadCache()

        # keep copy of templates for flexibility
        self.templates = templates.copy()

    # load cache
    def loadCache(self):
        cache_path = os.path.join(self.cache_dir, 'cache.json')
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                self.old_cache = json.loads(f.read())
    
    # save cache
    def saveCache(self):
        cache_path = os.path.join(self.cache_dir, 'cache.json')
        temp_cache_path = os.path.join(self.cache_dir, 'newcache.json')

        with open(temp_cache_path, 'w') as f:
            f.write(json.dumps(self.cache))

        if os.path.exists(cache_path):
            os.remove(cache_path)

        os.rename(temp_cache_path, cache_path)

    # add callback
    def listen(self, attribute, function):
        if attribute not in self.callbacks:
            self.callbacks[attribute] = []
        
        self.callbacks[attribute].append(function)
    
    # run callback
    def _cb(self, attribute, data):
        if attribute in self.callbacks:
            for fn in self.callbacks[attribute]:
                fn(data)

    # generate unique string-id: "test", "test1", "test2", "test3", etc. without repeats
    def _idfy(self, string_to_idfy):
        a = string_to_idfy.lower()
        a = re.sub(r'\s+', '_', a)
        a = re.sub(r'\W+', '', a)

        out = a
        i = 1
        while out in self.id_cache:
            out = a + str(i)
            i += 1
        
        self.id_cache.append(out)
        return out

    def iterateBlocks(self, data):
        array = []
        if type(data) == list:
            for item in data:
                array += self.iterateBlocks(item)
        else:
            # don't append pages as blocks
            if 'type' in data:
                array.append(data)
            
            # iterate through children (perhaps I should rename "columns" to children to make things simpler?)
            if 'children' in data:
                array += self.iterateBlocks(data['children'])
            elif 'columns' in data:
                array += self.iterateBlocks(data['columns'])
        
        return array

    # send block callbacks for page
    def generateBlockCallbacks(self, page):
        self._cb('pages', page)

        blocks = self.iterateBlocks(page)
        
        print(page['name'])

        for block in blocks:
            self._cb('blocks', block)
            self._cb('blocks/%s' % block['type'], block)
            if block['type'] == 'callout':
                self._cb('blocks/callout/%s' % block['icon'], block)
            elif block['type'] == 'code':
                self._cb('blocks/code/%s' % block['code_lang'], block)

    # convert relevant data to JSON to be able to cache website before HTML is generated
    def pageToJSON(self, page_id, cache_path=None):
        _pageblock = self.client.get_block(page_id)

        if _pageblock.id in self.cache:
            page = self.cache[_pageblock.id]
            return page

        _pagedata = _pageblock.get()
        _metadata = _pageblock.get_all_properties()
        
        page = {
            'id': page_id,
            'version': _pagedata['version']
        }

        for key in _metadata:
            value = _metadata[key]

            if type(value) == datetime:
                value = isoformat(value)
            elif type(value) == NotionDate:
                value = {
                    'start': isoformat(value.start),
                    'end': isoformat(value.end),
                    #'timezone': value.timezone,
                }
            
            page[key] = value

        page['children'] = self.blocksToJSONArray(_pageblock.children)

        if cache_path != None:
            page['path'] = cache_path
            self.cache[page['id']] = page

        return page

    # convert array of Notion blocks to JSON data, each containing relevant information for their respective HTML templates
    def blocksToJSONArray(self, blocks):
        output = []

        prev_data = {'type':''}
        for block in blocks:
            append_to_array = True

            data = {
                "type": block.type
            }

            title = block.get('properties.title')
            if title != None:
                data["text"] = title # pre-processing
                data["rawtext"] = ''.join(list(map(lambda x: x[0], title)))
            
            elif data['type'] == 'text': # get rid of empty text blocks
                append_to_array = False 
            
            if block.type in ['header', 'sub_header', 'sub_sub_header']:
                data['id'] = self._idfy(data['rawtext'])
            
            if block.type == 'code':
                data['code_lang'] = block.get('properties.language')[0][0].lower()
                #self._cb('blocks/code/%s' % data['code_lang'], data)

            if block.type == 'callout':
                data['icon'] = block.get('format.page_icon')
                #self._cb('blocks/callout/%s' % data['icon'], data)

            if block.type == 'image':
                #data['image_source'] = block.get('properties.source')[0][0]
                data['image_source'] = block.source

                file_id = block.get('id')
                extension = re.match('.*(\..*)', data['image_source']).group(1)

                caption = block.get('properties.caption')
                if caption != None:
                    data['image_caption'] = caption[0][0]

                data['image_name'] = file_id + extension
                data['image_path'] = os.path.join('/images', data['image_name'])

                """print(data['image_source'])
                os.makedirs(os.path.join(self.cache_dir, 'images'), exist_ok=True)
                os.makedirs(os.path.join(self.build_dir, 'images'), exist_ok=True)

                image_cache_path = os.path.join(self.cache_dir, data['image_path'][1:])
                image_build_path = os.path.join(self.build_dir, data['image_path'][1:])

                if not os.path.isfile(image_cache_path):
                    req = self.client.session.get(data['image_source'])
                    print(req)
                    with open(image_cache_path, 'wb') as image:
                        image.write(req.content)
                
                if not os.path.isfile(image_build_path): # make sure not to copy same image twice... if that's even possible?
                    shutil.copy2(image_cache_path, image_build_path)"""
            
            if block.type in ['numbered_list', 'bulleted_list']:
                item = {
                    #'type':  block.type + '_item',
                    'type': 'list_item',
                    'text': data.pop('text', None),
                    'rawtext': data.pop('rawtext', None),
                    'children': []
                }

                # can I just do block.children ?
                children = block.get('content')
                if children != None:
                    children = list(map(self.client.get_block, children))

                    item['children'] += self.blocksToJSONArray(children)

                if block.type == prev_data['type']:
                    append_to_array = False

                    prev_data['children'].append(item)
                else:
                    data['children'] = [item]
            
            if block.type == 'column_list':
                data['columns'] = []

                for column_id in block.get('content'):
                    column = self.client.get_block(column_id)

                    column_data = {
                        'column_ratio':  column.get('format.column_ratio'),
                        'children': []
                    }

                    block_ids = column.get('content')
                    if block_ids != None:
                        column_data['children'] = self.blocksToJSONArray(list(map(self.client.get_block, block_ids)))
                    
                    data['columns'].append(column_data)

            if block.type not in templates['blocks']:
                print("ERROR: UNIMPLEMENTED BLOCK TYPE %s" % block.type)


            if append_to_array:
                output.append(data)
                prev_data = data

                #self._cb('blocks', data)
                #self._cb('blocks/%s' % block.type, data)
        
        return output

    # add collection to cache/queue from notion url
    def addCollection(self, name, url, folder=None):
        subpages = []
        database = self.client.get_collection_view(url)

        folder = folder if folder is not None else name

        for row in database.collection.get_rows():
            if row.published is not True:
                continue

            if row.id in self.old_cache and self.old_cache[row.id]['version'] >= row.get('version'):
                cached_page = self.old_cache[row.id]
                self.cache[row.id] = cached_page
                subpages.append(cached_page)

                #self.generateBlockCallbacks(cached_page)
                continue

            props = row.get_all_properties()
            permalink = props['permalink']

            print(row.id)
            print(row.get('version'))

            if permalink.strip() == "":
                permalink = props['name'].lower()
                permalink = re.sub(r'[^\w -]', '', permalink) # remove symbols
                permalink = re.sub(r'\s+', '_', permalink.strip()) # convert spaces to underscore
            elif permalink.startswith('/'):
                permalink = permalink[1:]

            path = os.path.join('/', folder, permalink)
            
            page = self.pageToJSON(row.id, cache_path=path)
            subpages.append(page)
            
            #self.generateBlockCallbacks(page)
        
        self.collections[name] = subpages


    def render(self, data={}):
        for page in self.cache.values():
            self.generateBlockCallbacks(page)

        # Remove temporary build dir if already exists
        if os.path.isdir(self.build_dir):
            shutil.rmtree(self.build_dir)
        
        # create temporary build directory
        os.makedirs(self.build_dir, exist_ok=True)

        # move cached images to build directory
        #cached_image_dir = os.path.join(self.cache_dir, 'images')
        #if  os.path.exists(cached_image_dir):
        #    shutil.copytree(cached_image_dir, os.path.join(self.build_dir, 'images'))
        #else:
        #    os.makedirs(os.path.join(self.build_dir, 'images'), exist_ok=True)

        os.makedirs(os.path.join(self.cache_dir, 'images'), exist_ok=True)
        os.makedirs(os.path.join(self.build_dir, 'images'), exist_ok=True)

        # initialize build directory
        src_files = os.listdir(self.init_dir)
        for file_name in src_files:
            full_file_name = os.path.join(self.init_dir, file_name)
            if os.path.isfile(full_file_name):
                shutil.copy(full_file_name, self.build_dir)
            elif os.path.isdir(full_file_name):
                shutil.copytree(full_file_name, os.path.join(self.build_dir, file_name))
        

        for page in self.cache.values():
            html = self.renderPage(page, data)

            page_dir = os.path.join(self.build_dir, page['path'][1:])

            # create directory just in case!
            os.makedirs(page_dir, exist_ok=True)

            with open(os.path.join(page_dir, 'index.html'), 'w') as f:
                f.write(html)
        
        shutil.rmtree(self.public_dir)
        os.rename(self.build_dir, self.public_dir)
        

            

    def renderPage(self, page, data={}):
        #self._cb('pages', page)

        content = ''
        for block in page['children']:
            content += self.renderBlock(block)

        page_data = page.copy()
        del page_data['children']

        template_data = {
            **data,
            'content': content,
            'page': page_data,
            'collection': self.collections,
        }

        template_name = page['template'] if page['template'] is not None else 'default'

        # render html
        template = self.env.get_template('{}.html'.format(template_name))
        outputHTML = template.render(**template_data)

        # run through twice so that you can put jinja/html directly into Notion
        # perhaps this feature could be made optional
        template = self.env.from_string(outputHTML)
        outputHTML = template.render(**template_data)

        return outputHTML
        

    def renderBlock(self, data):
        #self._cb('blocks', data)
        #self._cb('blocks/%s' % data['type'], data)
        
        #if data['type'] == 'callout':
        #    self._cb('blocks/callout/%s' % data['icon'], data)
        #elif data['type'] == 'code':
        #    self._cb('blocks/code/%s' % data['code_lang'], data)


        data = data.copy()

        #if 'rawtext' in data:
        #    print(data['rawtext'])

        # shorthand
        _bls = self.templates['blocks']

        # special modes for callouts and code
        if data['type'] == 'callout':
            template_string = _bls['callout'][data['icon']] if data['icon'] in _bls['callout'] else ''
        elif data['type'] == 'code':
            template_string = _bls['code'][data['code_lang']] if data['code_lang'] in _bls['code'] else _bls['code']['other']
        else:
            template_string = _bls[data['type']]
        
        if data['type'] == 'image':
            image_cache_path = os.path.join(self.cache_dir, data['image_path'][1:])
            image_build_path = os.path.join(self.build_dir, data['image_path'][1:])

            if not os.path.isfile(image_cache_path):
                req = self.client.session.get(data['image_source'])
                print(req)
                with open(image_cache_path, 'wb') as image:
                    image.write(req.content)
            
            if not os.path.isfile(image_build_path): # make sure not to copy same image twice... if that's even possible?
                shutil.copy2(image_cache_path, image_build_path)

        # create template
        template = jinja2.Template(template_string)

        # recursive render function within jinja to render nested blocks
        template.globals['render'] = lambda x: self.renderBlock(x)

        # return html
        if 'text' in data:
            data.update({ 'text': self.renderText(data['text']) })
        
        return template.render(**data)


    def renderText(self, text_data):
        output = ""
        for item in text_data:
            text = item[0]
            text = text.replace('\n', '<br/>')

            props = item[1] if len(item) == 2 else []

            for prop in props:
                prop_type = prop[0]

                if prop_type in templates['text']:
                    #template.globals['context'] = get_context
                    data = { 'text': text }

                    if prop_type == 'p':            # internal link
                        link_id = prop[1]

                        # set text content of link to page name
                        data['text'] = self.client.get_block(link_id).name

                        # link to page if it exists
                        if link_id in self.cache:
                            data['href'] = self.cache[link_id]['path']
                        else:
                            data['href'] = ''
                            print('WARNING: BROKEN INTERNAL LINK %s' % link_id)
                    
                    if prop_type == 'h':            # color text
                        data['color'] = prop[1]
                    
                    if prop_type == 'a':            # external link
                        data['href'] = prop[1]

                        if re.search(r'^(https://azlen\.me)', data['href']) is not None:
                            # actually internal link
                            prop_type = 'p'
                    
                    if prop_type == 'd':            # date
                        data['text'] = prop[1]['start_date']

                        if 'end_date' in prop[1]:
                            data['text'] += ' – ' + prop[1]['end_date']
                    
                    template = jinja2.Template(self.templates['text'][prop_type])
                    text = template.render(**data)
                else:
                    print('UNKNOWN TEXT TYPE %s' % prop_type)
            
            output += text
        
        return output