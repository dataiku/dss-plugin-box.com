from dataiku.fsprovider import FSProvider
from boxsdk import OAuth2, Client

import os, shutil, json

from cache_handler import CacheHandler
from box_item import BoxItem
from utils import Utils


class BoxComFSProvider(FSProvider, Utils):
    def __init__(self, root, config, client):
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
        self.box_item = BoxItem(config, root, self.client)
        self.box_item.check_path_format(self.root_lnt)
    
    def close(self):
        """
        Perform any necessary cleanup
        """
        self.box_item.close()
            
    def stat(self, path):
        """
        Get the info about the object at the given path inside the provider's root, or None 
        if the object doesn't exist
        """
        full_path = self.get_full_path(path)
        box_item = self.box_item.get_by_path(full_path)
        if box_item.not_exists():
            return None
        ret = box_item.get_stat()
        return ret
        
    def set_last_modified(self, path, last_modified):
        """
        Set the modification time on the object denoted by path. Return False if not possible
        """
        return False

    def browse(self, path):
        """
        List the file or directory at the given path, and its children (if directory)
        """
        normalized_path = self.get_normalized_path(path)
        full_path = self.get_normalized_path(path)
        item = self.box_item.get_by_path(self.get_rel_path(full_path))
        if item.not_exists():
            return {'fullPath' : normalized_path, 'exists' : False}
        if item.is_folder():
            return {'fullPath' : normalized_path, 'exists' : True, 'directory' : True, 'children' : item.get_children()}
        else:
            return item.get_as_browse()
        
    def enumerate(self, path, first_non_empty):
        """
        Enumerate files recursively from prefix. If first_non_empty, stop at the first non-empty file.
        
        If the prefix doesn't denote a file or folder, return None
        """
        full_path = self.get_full_path(path)
        normalized_path = self.get_normalized_path(path)

        item = self.box_item.get_by_path(full_path)
        if item.not_exists():
            return None

        paths = []
        if item.is_folder():
            paths = self.list_recursive(path, item.id, first_non_empty)
        else:
            paths.append({'path':normalized_path.split("/")[-1], 'size':item.size, 'lastModified':int(0) * 1000})
        return paths
            
    def list_recursive(self, path, folder_id, first_non_empty):
        paths = []
        if path == "/":
            path = ""
        for child in self.client.folder(folder_id).get_items(fields = ['modified_at','name','type','size']):
            if child.type == self.box_item.BOX_FOLDER:
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
        item = self.box_item.get_by_path(full_path)
        if item.not_exists():
            raise Exception('Path doesn t exist')
        shutil.copyfileobj(item.get_stream(byte_range), stream)
        
    def write(self, path, stream):
        """
        Write the stream to the object denoted by path into the stream
        """
        raise Exception('write not implemented for box.com')