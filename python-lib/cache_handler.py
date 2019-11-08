import os, json, uuid, time, errno, logging
from shutil import move
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,  # avoid getting log from 3rd party module
                    format='box-com plugin %(levelname)s - %(message)s')

class CacheHandler():
    def __init__(self, cache_file_name):
        if cache_file_name is None:
            self.cache_enabled = False
        else:
            self.cache_enabled = True
        if self.cache_enabled:
            self.cache_location = os.environ["DIP_HOME"] + '/caches/plugins/box-com/' + cache_file_name
            self.load_cache()
            self.uuid = uuid.uuid4()
            self.removed = []

    def load_cache(self):
        try:
            with open(self.cache_location, "r") as file_handle:
                self.cache = json.load(file_handle)
                file_handle.close()
        except Exception as error:
            self.cache = {}

    def reset(self):
        if not self.cache_enabled:
            return
        if self.cache != {}:
            self.cache = {}
            self.write_onto_disk()

    def write_onto_disk(self):
        if not self.cache_enabled:
            return
        try:
            temporary_location = self.cache_location + str(self.uuid)
            self.create_dir(temporary_location)
            with open(temporary_location, "w") as file_handle:
                file_handle.write(json.dumps(self.cache))
                file_handle.close()
            move(temporary_location, self.cache_location)
        except (IOError, ValueError, EOFError) as error:
            logger.error('Error while saving cache:' + error)
        except Exception as error:
            logger.error('Error while saving cache' + error)

    def create_dir(self,filename):
        if not os.path.exists(os.path.dirname(filename)):
            try:
                os.makedirs(os.path.dirname(filename))
                return 1
            except OSError as error: # Guard against race condition
                if error.errno != errno.EEXIST:
                    raise
                logger.info("Error :" + error)
                return 0
        return 0

    def add(self, path, item_id, item_type):
        if not self.cache_enabled:
            return
        self.cache[path] = {"item_id":item_id, "item_type":item_type}
        self.write_onto_disk()

    def query(self, path, force_no_cache = False):
        if not self.cache_enabled or force_no_cache:
            return None, None
        if path in self.cache:
            return self.cache[path]["item_id"], self.cache[path]["item_type"]
        else:
            return None, None

    def remove(self, id):
        if not self.cache_enabled:
            return 0
        for key, value in self.cache.items():
            if value["item_id"] == id:
                self.removed.append(key)
                self.cache.pop(key, None)
                return 1
        return 0
