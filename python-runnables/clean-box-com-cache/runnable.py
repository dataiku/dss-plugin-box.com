from dataiku.runnables import Runnable
import os, hashlib

class CleanCache(Runnable):

    def __init__(self, project_key, config, plugin_config):
        self.project_key = project_key
        self.config = config
        self.plugin_config = plugin_config
        self.connection = self.plugin_config.get("box_com_connection")
        self.access_token = self.connection['access_token']
        self.cache_location = os.environ["DIP_HOME"] + '/caches/plugins/box-com/' + hashlib.sha1(self.access_token.encode('utf-8')).hexdigest()
        
    def get_progress_target(self):
        return None

    def run(self, progress_callback):
        if os.path.isfile(self.cache_location):
            os.remove(self.cache_location)
            return "Done!"
        else:
            return "Error: no cache found"
        