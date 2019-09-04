import os, json, uuid
from shutil import move

class CacheHandler():
    def __init__(self, config):
        self.cache_enabled = config.get("cache_enabled")
        self.client_id = config.get("client_id")
        if self.cache_enabled:
            self.cache_location = os.environ["DIP_HOME"] + '/caches/plugins/box-com/' + self.client_id
            self.load_cache()
            self.uuid = uuid.uuid4()
            
    def load_cache(self):
        try:
            with open(self.cache_location, "r") as file_handle:
                self.cache = json.load(file_handle)
                file_handle.close()
        except:
            self.cache = {}
        
    def dump_cache(self):
        if not self.cache_enabled:
            return
        try:
            tempo_location = self.cache_location + str(self.uuid)
            self.create_dir(tempo_location)
            with open(tempo_location, "w") as file_handle:
                file_handle.write(json.dumps(self.cache))
                file_handle.close()
            move(tempo_location, self.cache_location)
        except (IOError, ValueError, EOFError) as e:
            print('Error while saving cache:' + e)
        except:
            print('Error while saving cache')
            
    def create_dir(self,filename):
        if not os.path.exists(os.path.dirname(filename)):
            try:
                os.makedirs(os.path.dirname(filename))
            except OSError as exc: # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise
                    
    def add_to_cache(self, path, item_id, item_type):
        if not self.cache_enabled:
            return
        self.cache[path] = {"item_id":item_id, "item_type":item_type}
        self.dump_cache()
        
    def query_cache(self, path):
        if not self.cache_enabled:
            return None, None
        if path in self.cache:
            return self.cache[path]["item_id"], self.cache[path]["item_type"]
        else:
            return None, None
            