from dataiku.fsprovider import FSProvider
from boxsdk import OAuth2, Client

import os, shutil
from StringIO import StringIO
from datetime import datetime

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
        self.root_lnt = self.get_lnt_path(root)
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.access_token = config.get("access_token")
        auth = OAuth2(client_id=self.client_id,
            client_secret=self.client_secret,
            access_token=self.access_token
        )
        self.client = Client(auth)
        self.user = self.client.user().get()

    # util methods
    def get_rel_path(self, path):
        if len(path) > 0 and path[0] == '/':
            path = path[1:]
        return path
    def get_lnt_path(self, path):
        if len(path) == 0 or path == '/':
            return '/'
        elts = path.split('/')
        elts = [e for e in elts if len(e) > 0]
        return '/' + '/'.join(elts)
    def get_full_path(self, path):
        lnt_path = self.get_lnt_path(path)
        rel_path = self.get_rel_path(path)
        if lnt_path == '/':
            return self.root_lnt
        else:
            return self.root_lnt + lnt_path
        
    def close(self):
        """
        Perform any necessary cleanup
        """
        print ('box.com:close')

    def stat(self, path):
        """
        Get the info about the object at the given path inside the provider's root, or None 
        if the object doesn't exist
        """
        full_path = self.get_full_path(path)
        path_lnt = self.get_lnt_path(path)
        item_id, item_type = self.get_box_item(full_path)

        if item_id is None:
            return None
        
        item_details = self.get_box_item_details(item_id, item_type)
        
        ret = {'path': self.get_lnt_path(path) , 'size':item_details.size if (item_details.type == 'file') else 0, 'isDirectory': item_details.type == 'folder'}
        
        if "modified_at" in item_details and item_details.modified_at is not None:
            utc_time = datetime.strptime(item_details.modified_at, "%Y-%m-%dT%H:%M:%S-%f:00")
            epoch_time = (utc_time - datetime(1970, 1, 1)).total_seconds()
            ret["lastModified"] = int(epoch_time) * 1000

        return ret
    
    def get_box_item(self, path, create_if_not_exist=False):
        path = self.get_rel_path(path)
        item_id = '0'
        if path == '':
            return item_id, "folder"
        
        elts = path.split('/')
        
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
                if create_if_not_exist:
                    new_folder = self.client.folder(item_id).create_subfolder(elt)
                    item_id = new_folder.id
                else:
                    return None, None
        
        return item_id, item_type

    def set_last_modified(self, path, last_modified):
        """
        Set the modification time on the object denoted by path. Return False if not possible
        """
        raise Exception('set_last_modified on box.com not implemented')

    def browse(self, path):
        """
        List the file or directory at the given path, and its children (if directory)
        """
        full_path = self.get_full_path(path)
        path_lnt = self.get_lnt_path(path)
        item_id, item_type = self.get_box_item(self.get_rel_path(full_path))
        if item_id == None:
            return {'fullPath' : path_lnt, 'exists' : False}
        if item_type == "folder":
            children = []
            folder_id = item_id
            for sub in self.client.folder(folder_id=folder_id).get_items():
                print('sub:{0}'.format(sub))
                sub_full_path = os.path.join(full_path, sub.name)
                sub_path = self.get_lnt_path(os.path.join(full_path, sub.name))
                child_details = self.get_box_item_details(sub.id, sub.type)
                children.append({'fullPath' : sub_path, 'exists' : True, 'directory' : sub.type == "folder", 'size' : child_details.size})
            return {'fullPath' : path_lnt, 'exists' : True, 'directory' : True, 'children' : children}
        else:
            details = self.client.file(item_id).get()
            return {'fullPath' : path_lnt, 'exists' : True, 'directory' : False, 'size' : details.size}

    def get_box_item_details(self, item_id, item_type):
        if item_type == 'folder':
            return self.client.folder(item_id).get()
        else:
            return self.client.file(item_id).get()
        
    def enumerate(self, path, first_non_empty):
        """
        Enumerate files recursively from prefix. If first_non_empty, stop at the first non-empty file.
        
        If the prefix doesn't denote a file or folder, return None
        """
        
        full_path = self.get_full_path(path)
        path_lnt = self.get_lnt_path(path)
        item_id = '0'
        item_id, item_type = self.get_box_item(full_path)
        if item_id is None:
            return None

        paths = []
        if item_type == 'folder':
            paths = self.list_recursive(path, item_id, first_non_empty, False)
        else:
            child_details = self.client.file(item_id).get()
            paths.append({'path':path_lnt.split("/")[-1], 'size':child_details.size, 'lastModified':int(0) * 1000})
        return paths
            
    def list_recursive(self, path, folder_id, first_non_empty, box_id_only):
        paths = []
        if path == "/":
            path = ""
        for child in self.client.folder(folder_id).get_items():
            if child.type == 'folder':
                if box_id_only:
                    child_details = self.client.folder(child.id).get()
                    paths.append({'id': child_details.id, 'type': child_details.type})
                paths.extend(self.list_recursive(path + '/' + child.name, child.id, first_non_empty, box_id_only))
            else:
                child_details = self.client.file(child.id).get()
                if box_id_only:
                    paths.append({'id': child_details.id, 'type': child_details.type})
                elif "modified_at" in child_details and child_details.modified_at != None:
                    paths.append({'path':path + '/' + child_details.name, 'size':child_details.size})
                else:
                    paths.append({'path':path + '/' + child_details.name, 'size':child_details.size})
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
        file_id, item_type = self.get_box_item(full_path)
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