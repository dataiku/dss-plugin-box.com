from dataiku.fsprovider import FSProvider
from boxsdk import OAuth2, Client

import os, shutil, json, hashlib, logging

from box_item import BoxItem
from utils import get_full_path, get_rel_path, get_normalized_path


# The DefaultNetwork of box.com logs all network queries and responses, INCLUDING CONTENT
# This is crazy but it is how it is, and it of course lead to incredible disk usage
# and various failures because these insane log lines can find their way to a LogTail in DSS
#
# The DefaultNetwork has provision to avoid logging when the response is a stream
# (see response_as_stream in DefaultNetworkResponse), but boxsdk.object.file always uses
# the .content instead of the .raw, so it always goes through logging
#
# So we override the DefaultNetwork's log function to avoid logging big things
#
# Note: another option would be to try to use response_as_stream instead, but it would
# require rewrapping boxsdk.object.file, so looks more dangerous
MAX_LOGGED_RESPONSE_SIZE = 2048

from boxsdk.network.default_network import DefaultNetwork, DefaultNetworkResponse
from boxsdk.session.session import AuthorizedSession
from six import text_type
from pprint import pformat
from boxsdk.util.log import sanitize_dictionary

class LessVerboseLoggingNetwork(DefaultNetwork):
    @property
    def network_response_constructor(self):
        return LessVerboseLoggingNetworkResponse

class LessVerboseLoggingNetworkResponse(DefaultNetworkResponse):
    def log(self, can_safely_log_content=False):
        if self._did_log:
            return
        self._did_log = True
        content_length = self.headers.get('Content-Length', None)
        content = self.STREAM_CONTENT_NOT_LOGGED

        if can_safely_log_content:
            if content_length is None:
                content_length = text_type(len(self.content))

            if len(self.content) > MAX_LOGGED_RESPONSE_SIZE:
                content = "<Content not logged (size=%s)>" % len(self.content)
            else:
                # If possible, get the content as a JSON `dict`, that way
                # `pformat(content)` will return pretty-printed JSON.
                try:
                    content = self.json()
                except ValueError:
                    content = self.content
                content = pformat(sanitize_dictionary(content))
        if content_length is None:
            content_length = '?'
        if self.ok:
            logger_method, response_format = self._logger.info, self.SUCCESSFUL_RESPONSE_FORMAT
        else:
            logger_method, response_format = self._logger.warning, self.ERROR_RESPONSE_FORMAT
        logger_method(
            response_format,
            {
                'method': self.request_response.request.method,
                'url': self.request_response.request.url,
                'status_code': self.status_code,
                'content_length': content_length,
                'headers': pformat(self.headers),
                'content': content,
            },
        )

# End of logging fixes
############################


class BoxComFSProvider(FSProvider):
    def __init__(self, root, config, client):
        """
        :param root: the root path for this provider
        :param config: the dict of the configuration of the object
        :param plugin_config: contains the plugin settings
        """
        if len(root) > 0 and root[0] == '/':
            root = root[1:]
        self.root = root
        self.connection = client.get("box_com_connection")
        self.access_token = self.connection['access_token']
        self.cache_enabled = config.get("cache_enabled")
        if self.cache_enabled:
            cache_file_name = hashlib.sha1(self.access_token.encode('utf-8')).hexdigest()
        else:
            cache_file_name = None

        auth = OAuth2(
            client_id="",
            client_secret="",
            access_token=self.access_token
        )

        main_session = AuthorizedSession(auth, network_layer=LessVerboseLoggingNetwork())
        self.client = Client(auth, main_session)
        self.user = self.client.user().get()
        self.box_item = BoxItem(cache_file_name, root, self.client)
        self.box_item.check_path_format(get_normalized_path(root))

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
        full_path = get_full_path(self.root, path)
        box_item = self.box_item.get_by_path(full_path)
        if box_item.not_exists():
            return None
        return box_item.get_stat()

    def set_last_modified(self, path, last_modified):
        """
        Set the modification time on the object denoted by path. Return False if not possible
        """
        return False

    def browse(self, path):
        """
        List the file or directory at the given path, and its children (if directory)
        """
        normalized_path = get_normalized_path(path)
        full_path = get_full_path(self.root, path)
        item = self.box_item.get_by_path(get_rel_path(full_path))
        if item.not_exists():
            return {'fullPath' : normalized_path, 'exists' : False}
        if item.is_folder():
            return {'fullPath' : normalized_path, 'exists' : True, 'directory' : True, 'children' : item.get_children(normalized_path), 'lastModified' : item.get_last_modified()}
        else:
            return item.get_as_browse()
    
    def enumerate(self, path, first_non_empty):
        """
        Enumerate files recursively from prefix. If first_non_empty, stop at the first non-empty file.
        
        If the prefix doesn't denote a file or folder, return None
        """
        full_path = get_full_path(self.root, path)
        normalized_path = get_normalized_path(path)

        item = self.box_item.get_by_path(full_path)
        if item.not_exists():
            return None

        paths = []
        if item.is_folder():
            paths = self.list_recursive(normalized_path, item.id, first_non_empty)
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
        full_path = get_full_path(self.root, path)
        item = self.box_item.get_by_path(full_path, force_no_cache = True)
        if item.not_exists():
            return 0
        else:
            ret = item.delete()
            self.box_item.cache.reset()
            return ret

    def move(self, from_path, to_path):
        """
        Move a file or folder to a new path inside the provider's root. Return false if the moved file didn't exist
        """
        full_from_path = get_full_path(self.root, from_path)
        full_to_path = get_full_path(self.root, to_path)
        from_base, from_item_name = os.path.split(full_from_path)
        to_base, to_item_name = os.path.split(full_to_path)

        from_item = self.box_item.get_by_path(full_from_path, force_no_cache = True)

        if from_item.not_exists():
            return False

        from_item_id = from_item.get_id()
        from_item_is_folder = from_item.is_folder()

        to_item =  self.box_item.get_by_path(full_to_path, force_no_cache = True)
        if to_item.not_exists():
            to_item =  self.box_item.get_by_path(to_base, force_no_cache = True)

        destination_folder = self.client.folder(to_item.get_id())

        if from_item_is_folder:
            source = self.client.folder(from_item_id)
        else:
            source = self.client.file(from_item_id)

        if from_item_name == to_item_name:
            source.move(destination_folder)
        else:
            source.rename(to_item_name)

        return True

    def read(self, path, stream, limit):
        full_path = get_full_path(self.root, path)
        byte_range = None

        if limit is not None and limit is not "-1":
            int_limit = int(limit)
            if int_limit > 0:
                byte_range = (0, int(limit) - 1)

        item = self.box_item.get_by_path(full_path)
        if item.not_exists():
            raise Exception('Path doesn t exist')
        shutil.copyfileobj(item.get_stream(byte_range), stream)

    def write(self, path, stream):
        """
        Write the stream to the object denoted by path into the stream
        """
        full_path = get_full_path(self.root, path)
        item = self.box_item.create_path(full_path, force_no_cache = True)
        if item.is_folder():
            item.write_stream(stream)
        else:
            raise Exception('Not a file name')