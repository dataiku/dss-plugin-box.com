class Utils():
    
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
    def get_full_path(self, root, path):
        normalized_path = self.get_normalized_path(path)
        if normalized_path == '/':
            return self.get_normalized_path(root)
        else:
            return self.get_normalized_path(root) + normalized_path