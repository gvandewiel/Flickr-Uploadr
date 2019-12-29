import os
from pprint import pprint

def path_to_dict(path, d):
    name = os.path.basename(path)

    if os.path.isdir(path):
        if name not in d['dirs']:
            d['dirs'][name] = {'dirs':{}}
        for x in os.listdir(path):
            path_to_dict(os.path.join(path,x), d['dirs'][name])
    else:
        pass
    self._notify('insert', parent=name, item=path.replace(name,''))
    return d

mydict = path_to_dict('/mnt/NAS/Media/Pictures', d={'dirs':{}})
pprint(mydict)