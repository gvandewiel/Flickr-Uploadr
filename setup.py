# Standard library modules.
import codecs
import os
import re

# De-facto standard solution for Python packaging.
from setuptools import find_packages, setup
from multiprocessing import Process


def get_contents(*args):
    """Get the contents of a file relative to the source distribution directory."""
    with codecs.open(get_absolute_path(*args), 'r', 'UTF-8') as handle:
        return handle.read()


def get_version(*args):
    """Extract the version number from a Python module."""
    contents = get_contents(*args)
    metadata = dict(re.findall('__([a-z]+)__ = [\'"]([^\'"]+)', contents))
    return metadata['version']


def get_requirements(*args):
    """Get requirements from pip requirement files."""
    requirements = set()
    with open(get_absolute_path(*args)) as handle:
        for line in handle:
            # Strip comments.
            line = re.sub(r'^#.*|\s#.*', '', line)
            # Ignore empty lines
            if line and not line.isspace():
                requirements.add(re.sub(r'\s+', '', line))
    return sorted(requirements)


def get_absolute_path(*args):
    """Transform relative pathnames into absolute pathnames."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *args)

if __name__ == '__main__':
    setups = [
            {'name':'FlickrUploadr',
             'version':get_version('flickr_uploadr', '__init__.py'),
             'description':"Flickr Photo Uploader",
             'long_description':get_contents('README.md'),
             'author':"Gijs van de Wiel",
             'packages':find_packages(),
             'entry_points':{
                 'console_scripts': ['FlickrUploadr = flickr_uploadr.threaded_uploadr:main'],
             },
             'install_requires':get_requirements('requirements.txt')
            },
            {'name':'FlickrUploadr-Console',
             'version':get_version('console','__init__.py'),
             'description':"Flickr Photo Uploader from console",
             'long_description':get_contents('gui','README.md'),
             'author':"Gijs van de Wiel",
             'packages':find_packages(where='console'),
             'entry_points':{
                 'console_scripts': ['FlickrUploadr.console = console.__main__:main'],
             },
             'install_requires':get_requirements('console','requirements.txt')
            },
            {'name':'FlickrUploadr-GUI',
             'version':get_version('gui','__init__.py'),
             'description':"Flickr Photo Uploader with Eel-based GUI",
             'long_description':get_contents('gui','README.md'),
             'author':"Gijs van de Wiel",
             'packages':find_packages(where='gui'),
             'entry_points':{
                 'gui_scripts': ['FlickrUploadr.GUI = gui,.__main__:main'],
             },
             'install_requires':get_requirements('gui','requirements.txt')
            }]
            
    for s in setups:
        name = s['name']
        print("Building '{}'.".format(name))
        p = Process(target=setup, kwargs=s)
        p.start()
        p.join()
        print("Building of '{}' done.\n".format(name))