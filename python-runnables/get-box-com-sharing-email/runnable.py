from dataiku.runnables import Runnable
from boxsdk import OAuth2, Client

class GetBoxSharingEmail(Runnable):

    def __init__(self, project_key, config, plugin_config):
        self.project_key = project_key
        self.config = config
        self.plugin_config = plugin_config
        
        self.connection = self.plugin_config.get("box_com_connection")
        self.access_token = self.connection['access_token']
        
        auth = OAuth2(
            client_id="",
            client_secret="",
            access_token=self.access_token
        )
        self.client = Client(auth)
        self.user = self.client.user().get()
        
    def get_progress_target(self):
        return None

    def run(self, progress_callback):
        return self.user.login
        