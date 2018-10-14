# Standard library modules.
import codecs
import os
import re

# De-facto standard solution for Python packaging.
from setuptools import find_packages, setup

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


def get_data_files(*args):
    """Retrieve data_files for gui"""
    _ret = list()
    for path, subdirs, files in os.walk(get_absolute_path(*args)):
        for name in files:
            _ret.append(os.path.join(path, name))
    return _ret


def get_absolute_path(*args):
    """Transform relative pathnames into absolute pathnames."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *args)

setup(name='flickruploadr',
      version=get_version('flickruploadr', '__init__.py'),
      description="Flickr Photo Uploader",
      long_description=get_contents('README.md'),
      author="Gijs van de Wiel",
      packages=find_packages('', exclude=["*.git"]),
      package_data={'flickruploadr': ['flickruploadr/web/*.html',
                                      'flickruploadr/web/css/*.css',
                                      'flickruploadr/web/js/*.js']
                    },
      include_package_data=True,
      setup_requires=["setuptools_git >= 0.3", ],
      install_requires=get_requirements('requirements.txt'),
      entry_points={
          'console_scripts': ['flickruploadr = flickruploadr.__main__:main'],
      }
      )
print('''
NOTE:
The FlickrUploadr.GUI requires Eel (and gevent, part of Eel dpependecies).
The should be installed manually by the user to prevent critical failure during installation of the FlickrUploadr. This can be done by running:
\t\tpip install Eel >= 0.9.7
On Synology systems this is not available.

''')
