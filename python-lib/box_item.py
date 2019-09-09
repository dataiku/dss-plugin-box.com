import os, json, utils, string
from StringIO import StringIO
from datetime import datetime
from cache_handler import CacheHandler
from utils import Utils

class BoxItem(Utils):
    BOX_FOLDER = "folder"
    BOX_FILE = "file"
    def __init__(self, config, root, client):
        self.path = ''
        self.id = "0"
        self.type = self.BOX_FOLDER
        self.modified_at = None
        self.size = 0
        self.cache = CacheHandler(config)
        self.root_lnt = self.get_normalized_path(root)
        self.client = client
        
    def get_by_path(self, path):
        rel_path = self.get_rel_path(path)

        if rel_path == '':
            self.id = "0"
            self.type = self.BOX_FOLDER
            self.size = 0
            return self

        item_id, item_type = self.cache.query_cache(rel_path)
        if item_id is not None:
            self.path = rel_path
            self.id = item_id
            self.type = item_type
            return self
        else:
            item_id = '0'
            item_type = self.BOX_FOLDER

        elts = rel_path.split('/')

        current_path = ''
        for elt in elts:
            current_path = os.path.join(current_path, elt)
            items_iter = self.client.folder(folder_id=item_id).get_items(fields = ['modified_at','name','type','size'])
            found = False
            for item in items_iter:
                if item.name == elt:
                    self.path = rel_path
                    self.id = item.id
                    item_id = item.id
                    self.type = item.type
                    self.modified_at = self.format_date(item.modified_at)
                    self.size = item.size
                    self.cache.add_to_cache(current_path, item.id, item.type)
                    found = True
                    break
        
        if not found:
            self.id = None
            self.type = None
            self.modified_at = None
            self.size = None
        return self
    
    def format_date(self, date):
        if date is not None:
            utc_time = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S-%f:00")
            epoch_time = (utc_time - datetime(1970, 1, 1)).total_seconds()
            return int(epoch_time) * 1000
        else:
            return None
            
    def not_exists(self):
        return (self.id == None)
    
    def exists(self):
        return (self.id is not None)
    
    def is_folder(self):
        return self.type == self.BOX_FOLDER
    
    def get_stat(self):
        ret = {'path': self.get_normalized_path(self.path) , 'size':self.size if self.is_folder() else 0, 'isDirectory': self.is_folder()}
        if self.modified_at is not None:
            ret["lastModified"] = self.modified_at
        return ret
        
    def get_children(self):
        full_path = self.get_full_path(self.path)
        children = []
        for sub in self.client.folder(self.id).get_items(fields = ['modified_at','name','type','size']):
            sub_path = self.get_normalized_path(os.path.join(full_path, sub.name))
            ret = {'fullPath' : sub_path, 'exists' : True, 'directory' : sub.type == self.BOX_FOLDER, 'size' : sub.size}
            children.append(ret)
            self.cache.add_to_cache(self.get_rel_path(sub_path), sub.id, sub.type)
        return children

    def get_id(self):
        return self.id
    
    def get_as_browse(self):
        return {'fullPath' : self.get_normalized_path(self.path), 'exists' : self.exists(), 'directory' : self.is_folder(), 'size' : self.size}
    
    def get_stream(self, byte_range = None):
        if byte_range:
            ws = self.client.file(self.id).content(byte_range = byte_range)
        else:
            ws = self.client.file(self.id).content()
        return StringIO(ws)

    def check_path_format(self, path):
        special_names = [".",".."]
        if not all(c in string.printable for c in path):
            raise Exception('The path contains non-printable char(s)')
        for element in path.split('/'):
            if len(element) > 255:
                raise Exception('An element of the path is longer than the allowed 255 characters')
            if element in special_names:
                raise Exception('Special name "{0}" is not allowed in a box.com path'.format(element))
            if element.endswith(' '):
                raise Exception('An element of the path contains a trailing space')

    def close(self):
        self.cache.dump_cache()
