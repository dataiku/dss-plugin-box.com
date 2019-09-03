from dataiku.fsprovider import FSProvider
from boxsdk import OAuth2, Client

import os, shutil, json
from StringIO import StringIO
from datetime import datetime

from cache_handler import CacheHandler

class BoxComFSProvider(FSProvider):
    def __init__(self, root, config, plugin_config):
        """
        :param root: the root path for this provider
        :param config: the dict of the configuration of the object
        :param plugin_config: contains the plugin settings
        """
        if len(root) > 0 and root[0] == '/':
            root = root[1:]
        self.root = root
        self.root_lnt = self.get_normalized_path(root)
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.access_token = config.get("access_token")
        auth = OAuth2(
            client_id=self.client_id,
            client_secret=self.client_secret,
            access_token=self.access_token
        )
        self.client = Client(auth)
        self.user = self.client.user().get()
        self.cache = CacheHandler(config)

    # util methods
    def get_rel_path(self, path):
        if len(path) > 0 and path[0] == '/':
            path = path[1:]
        return path
    def get_normalized_path(self, path):
        if len(path) == 0 or path == '/':
            return '/'
        elts = path.split('/')
        elts = [e for e in elts if len(e) > 0]
        return '/' + '/'.join(elts)
    def get_full_path(self, path):
        normalized_path = self.get_normalized_path(path)
        if normalized_path == '/':
            return self.root_lnt
        else:
            return self.root_lnt + normalized_path
    
    def close(self):
        """
        Perform any necessary cleanup
        """
        self.cache.dump_cache()
        print ('box.com:close')
            
    def stat(self, path):
        """
        Get the info about the object at the given path inside the provider's root, or None 
        if the object doesn't exist
        """
        full_path = self.get_full_path(path)
        item_id, item_type = self.get_box_item(full_path)

        if item_id is None:
            return None
        
        item_details = self.get_box_item_details(item_id, item_type)
        
        ret = {'path': self.get_normalized_path(path) , 'size':item_details.size if (item_details.type == 'file') else 0, 'isDirectory': item_details.type == 'folder'}
        
        if "modified_at" in item_details and item_details.modified_at is not None:
            utc_time = datetime.strptime(item_details.modified_at, "%Y-%m-%dT%H:%M:%S-%f:00")
            epoch_time = (utc_time - datetime(1970, 1, 1)).total_seconds()
            ret["lastModified"] = int(epoch_time) * 1000

        return ret
    
    def get_box_item(self, path):
        rel_path = self.get_rel_path(path)

        if rel_path == '':
            return '0', "folder"

        item_id, item_type = self.cache.query_cache(rel_path)
        if item_id is not None:
            return item_id, item_type
        else:
            item_id = '0'
            item_type = 'folder'

        elts = rel_path.split('/')
        
        for elt in elts:
            items_iter = self.client.folder(folder_id=item_id).get_items()
            found = False
            for item in items_iter:
                if item.name == elt:
                    item_id = item.id
                    item_type = item.type
                    found = True
                    break
            if found == False:
                return None, None
        
        self.cache.add_to_cache(rel_path, item_id, item_type)
        
        return item_id, item_type
        
    def set_last_modified(self, path, last_modified):
        """
        Set the modification time on the object denoted by path. Return False if not possible
        """
        return False

    def browse(self, path):
        """
        List the file or directory at the given path, and its children (if directory)
        """
        full_path = self.get_full_path(path)
        normalized_path = self.get_normalized_path(path)
        item_id, item_type = self.get_box_item(self.get_rel_path(full_path))
        if item_id == None:
            return {'fullPath' : normalized_path, 'exists' : False}
        if item_type == "folder":
            children = []
            folder_id = item_id
            for sub in self.client.folder(folder_id=folder_id).get_items(fields = ['modified_at','name','type','size']):
                sub_path = self.get_normalized_path(os.path.join(full_path, sub.name))
                ret = {'fullPath' : sub_path, 'exists' : True, 'directory' : sub.type == "folder", 'size' : sub.size}
                children.append(ret)
                self.cache.add_to_cache(self.get_rel_path(sub_path), sub.id, sub.type)
            return {'fullPath' : normalized_path, 'exists' : True, 'directory' : True, 'children' : children}
        else:
            details = self.client.file(item_id).get()
            file_size = details.get('size')
            ret = {'fullPath' : normalized_path, 'exists' : True, 'directory' : False, 'size' : file_size}
            return ret

    def get_box_item_details(self, item_id, item_type):
        if item_type == 'folder':
            ret = self.client.folder(item_id).get()
        else:
            ret = self.client.file(item_id).get()
        store = {"type":ret.get('type'), "size":ret.get('size')}#modified_at
        return ret
        
    def enumerate(self, path, first_non_empty):
        """
        Enumerate files recursively from prefix. If first_non_empty, stop at the first non-empty file.
        
        If the prefix doesn't denote a file or folder, return None
        """
        full_path = self.get_full_path(path)
        normalized_path = self.get_normalized_path(path)
        item_id = '0'
        item_id, item_type = self.get_box_item(full_path)
        if item_id is None:
            return None

        paths = []
        if item_type == 'folder':
            paths = self.list_recursive(path, item_id, first_non_empty)
        else:
            child_details = self.client.file(item_id).get()
            paths.append({'path':normalized_path.split("/")[-1], 'size':child_details.size, 'lastModified':int(0) * 1000})
        return paths
            
    def list_recursive(self, path, folder_id, first_non_empty):
        paths = []
        if path == "/":
            path = ""
        for child in self.client.folder(folder_id).get_items(fields = ['modified_at','name','type','size']):
            if child.type == 'folder':
                paths.extend(self.list_recursive(path + '/' + child.name, child.id, first_non_empty))
            else:
                paths.append({'path':path + '/' + child.name, 'size':child.size})
                if first_non_empty:
                    return paths
        return paths
        
    def delete_recursive(self, path):
        """
        Delete recursively from path. Return the number of deleted files (optional)
        """
        raise Exception('delete_recursive not implemented for box.com') 
            
    def move(self, from_path, to_path):
        """
        Move a file or folder to a new path inside the provider's root. Return false if the moved file didn't exist
        """
        raise Exception('move not implemented for box.com')

    def read(self, path, stream, limit):
        full_path = self.get_full_path(path)
        if limit is not None and limit is not "-1":
            int_limit = int(limit)
            if int_limit > 0:
                byte_range = (0, int(limit) - 1)
            else:
                byte_range = None
        file_id, _ = self.get_box_item(full_path)
        if file_id == None:
            raise Exception('Path doesn t exist')
        if byte_range:
            ws = self.client.file(file_id).content(byte_range = byte_range)
        else:
            ws = self.client.file(file_id).content()
        shutil.copyfileobj(StringIO(ws), stream)
        
    def write(self, path, stream):
        """
        Write the stream to the object denoted by path into the stream
        """
        raise Exception('write not implemented for box.com')