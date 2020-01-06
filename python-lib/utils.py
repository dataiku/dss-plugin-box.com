def get_rel_path(path):
    if len(path) > 0 and path[0] == '/':
        path = path[1:]
    return path
def get_normalized_path(path):
    if len(path) == 0 or path == '/':
        return '/'
    elts = path.split('/')
    elts = [e for e in elts if len(e) > 0]
    return '/' + '/'.join(elts)
def get_full_path(root, path):
    normalized_path = get_normalized_path(path)
    if normalized_path == '/':
        return get_normalized_path(root)
    else:
        return get_normalized_path(root) + normalized_path