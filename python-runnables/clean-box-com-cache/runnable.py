from dataiku.runnables import Runnable
import os

class CleanCache(Runnable):

    def __init__(self, project_key, config, plugin_config):
        self.project_key = project_key
        self.config = config
        self.plugin_config = plugin_config
        self.client_id = self.config.get("client_id")
        self.cache_location = os.environ["DIP_HOME"] + '/caches/plugins/box-com/' + self.client_id
        
    def get_progress_target(self):
        return None

    def run(self, progress_callback):
        if os.path.isfile(self.cache_location):
            os.remove(self.cache_location)
            return "Done!"
        else:
            return "Error: no cache found"
        