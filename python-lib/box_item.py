import os, json, utils, shutil, time, string, logging

try:
    from BytesIO import BytesIO ## for Python 2
except ImportError:
    from io import BytesIO ## for Python 3

from datetime import datetime
from cache_handler import CacheHandler
from utils import get_full_path, get_rel_path, get_normalized_path
from boxsdk.exception import BoxAPIException


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format='box-com plugin %(levelname)s - %(message)s')

class BoxItem():

    BOX_FOLDER = "folder"
    BOX_FILE = "file"
    BOX_ERR_NOT_FOUND = 404
    BOX_ERR_CONFLICT = 409
    BOX_ERR_RESERVED = 'name_temporarily_reserved'
    BOX_ERR_DUPLICATE = 'item_name_in_use'

    def __init__(self, cache_file_name, root, client):
        self.path = ''
        self.id = "0"
        self.type = self.BOX_FOLDER
        self.modified_at = None
        self.size = 0
        self.cache = CacheHandler(cache_file_name)
        self.root = root
        self.client = client

    def get_by_path(self, path, create_if_not_exist = False, force_no_cache = False):
        rel_path = get_rel_path(path)
        if rel_path == '':
            self.set_root()
            return self

        item_id, item_type = self.cache.query(rel_path, force_no_cache)

        if item_id is not None:
            try:
                item = self.get_details(item_id, item_type)
                self.path = rel_path
                self.id = item_id
                self.type = item_type
                self.size = (item.size if self.is_file() else 0)
                return self
            except Exception as error:
                logger.info("Exception:{}".format(error))
                self.cache.reset()

        # Start iterating path from root id "0"
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
                    self.cache.add(current_path, item.id, item.type)
                    found = True
                    break
        
            if not found:
                if create_if_not_exist:
                    new_folder = self.create_subfolder(elt)
                    item_id = new_folder.id
                    self.cache.add(current_path, new_folder.id, self.BOX_FOLDER)
                else:
                    self.set_none()
        return self

    def get_details(self, id, type):
        if type == self.BOX_FOLDER:
            return self.client.folder(id).get(fields = ['modified_at','name','type','size'])
        elif type == self.BOX_FILE:
            return self.client.file(id).get(fields = ['modified_at','name','type','size'])

    def set_root(self):
        self.id = "0"
        self.type = self.BOX_FOLDER
        self.size = 0

    def set_none(self):
        self.id = None
        self.type = None
        self.modified_at = None
        self.size = None

    def create_subfolder(self, name):
        new_folder = {}
        new_id = None
        while new_id is None:
            try:
                new_folder = self.client.folder(self.id).create_subfolder(name)
                new_id = self.fix_any_duplicate(name, new_folder['id'])
            except BoxAPIException as err:
                if err.status == self.BOX_ERR_CONFLICT:
                    if err.code == self.BOX_ERR_RESERVED:
                        # Item name is reserved but there is no ID yet, so we have to loop until we get a BOX_ERR_DUPLICATE
                        time.sleep(1)
                        pass
                    elif err.code == self.BOX_ERR_DUPLICATE:
                        new_id = err.context_info['conflicts'][0]['id']
                    else:
                        raise Exception('Unimplemented Box.com conflict error while creating subfolder')
                else:
                    raise Exception('Unimplemented Box.com error while creating subfolder')
        self.id = new_id
        self.type = self.BOX_FOLDER
        self.size = 0
        return self

    def get_last_modified(self, item = None):
        if item is None:
            return self.modified_at
        elif "modified_at" in item:
            return self.format_date(item["modified_at"]) 
        else:
            return

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

    def is_file(self):
        return self.type == self.BOX_FILE

    def get_stat(self):
        ret = {'path': get_normalized_path(self.path) , 'size':self.size if self.is_file() else 0, 'isDirectory': self.is_folder()}
        if self.modified_at is not None:
            ret["lastModified"] = self.modified_at
        return ret

    def get_children(self, internal_path):
        full_path = get_full_path(self.root, self.path)
        intra_path = self.path.replace('/'+self.root, '')
        children = []
        for sub in self.client.folder(self.id).get_items(fields = ['modified_at','name','type','size']):
            sub_path = get_normalized_path(os.path.join(internal_path, sub.name))
            ret = {'fullPath' : sub_path, 'exists' : True, 'directory' : sub.type == self.BOX_FOLDER, 'size' : sub.size, 'lastModified' : self.get_last_modified(sub)}
            children.append(ret)
            self.cache.add(get_rel_path(sub.name), sub.id, sub.type)
        return children

    def get_id(self):
        return self.id

    def get_as_browse(self):
        return {'fullPath' : get_normalized_path(self.path), 'exists' : self.exists(), 'directory' : self.is_folder(), 'size' : self.size, 'lastModified' : self.get_last_modified()}

    def get_stream(self, byte_range = None):
        if byte_range:
            ws = self.client.file(self.id).content(byte_range = byte_range)
        else:
            ws = self.client.file(self.id).content()
        return BytesIO(ws)

    def write_stream(self, stream):
        file_name = self.path.split('/')[-1]
        sio = BytesIO()
        shutil.copyfileobj(stream, sio)
        sio.seek(0)
        ret = self.client.folder(self.id).upload_stream(sio, file_name=file_name)
        self.id = ret.id
        self.cache.add(self.path, ret.id, ret.type)
        return self

    def create_path(self, path, force_no_cache = False):
        target_path = '/'.join(path.split('/')[:-1])
        ret = self.get_by_path(target_path, create_if_not_exist=True, force_no_cache = force_no_cache)
        ret.path = path
        return ret

    def delete(self):
        if self.is_file():
            try:
                self.client.file(self.id).delete()
            except BoxAPIException as err:
                if err.status == self.BOX_ERR_NOT_FOUND:
                    # Probably deleted by competing process
                    pass
                else:
                    raise Exception("Error while deleting box.com item")
            self.cache.remove(self.id)
            return 1
        if self.is_folder():
            return self.recursive_delete()

    def recursive_delete(self, id = None):
        counter = 0
        if id is None:
            id = self.id
        try:
            for child in self.client.folder(id).get_items():
                if child.type == self.BOX_FOLDER:
                    counter = counter + self.recursive_delete(id = child.id)
                    try:
                        self.cache.remove(child.id)
                        counter = counter + 1
                    except Exception as error:
                        logger.info("Exception:{}".format(error))
                elif child.type == self.BOX_FILE:
                    try:
                        self.client.file(child.id).delete()
                        self.cache.remove(child.id)
                        counter = counter + 1
                    except Exception as error:
                        # File already deleted
                        logger.info("Exception:{}".format(error))
        except Exception as error:
            logger.info("Folder already deleted")
        self.cache.remove(self.id)
        return counter

    def fix_any_duplicate(self, name, new_id):
        # Several plugin instances creating the same folder on box.com can lead to duplicate folder names
        if self.is_duplicated(name, new_id):
            self.cache.reset()
            time.sleep(1) # waiting for dust to settle on box.com side
            id_default_folder = self.id_default_folder(name)
            if id_default_folder != new_id:
                try:
                    self.client.folder(new_id).delete()
                except Exception as error:
                    logger.info("Folder already deleted:{}".format(error))
                return id_default_folder
        return new_id

    def is_duplicated(self, name, new_id):
        instances = 0
        my_child = False
        try:
            for child in self.client.folder(self.id).get_items():
                if child.name == name:
                    instances = instances + 1
                    if child.id == new_id:
                        my_child = True
        except BoxAPIException as err:
            raise Exception('Error while accessing box.com item:{0}'.format(err))
        return (instances > 1) and my_child

    def id_default_folder(self,name):
        try:
            probe_folder = self.client.folder(self.id).create_subfolder(name)
            return probe_folder.id
        except BoxAPIException as err:
            if err.status == self.BOX_ERR_CONFLICT:
                if err.code == self.BOX_ERR_DUPLICATE:
                    return err.context_info['conflicts'][0]['id']
                else:
                    raise Exception('Unimplemented Box.com conflict error while creating subfolder')
            else:
                raise Exception('Unimplemented Box.com error while creating subfolder: {0}'.format(err))
        return None

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
        self.cache.write_onto_disk()
