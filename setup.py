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


def get_absolute_path(*args):
    """Transform relative pathnames into absolute pathnames."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *args)


setup(name='FlickrUploadr',
      version=get_version('flickr_uploadr', '__init__.py'),
      description="Flickr Photo Uploader with Eel based GUI",
      long_description=get_contents('README.md'),
      author="Gijs van de Wiel",
      packages=find_packages(),
      entry_points={
        'console_scripts': [
            'ConsoleUploadr = console.__main__:main',
          ],
        'gui_scripts': [
            'FlickrUploadr = gui.__main__:main',
          ]},
      install_requires=get_requirements('requirements.txt')
)
