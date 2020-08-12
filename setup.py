from setuptools import setup, find_packages
from io import open
from os import path

from pymoa import __version__

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

URL = 'https://github.com/matham/pymoa'

setup(
    name='pymoa',
    version=__version__,
    author='Matthew Einhorn',
    author_email='moiein2000@gmail.com',
    license='MIT',
    description='Scientific platform for running experiments.',
    long_description=long_description,
    url=URL,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: MIT License',
        'Topic :: Scientific/Engineering',
        'Topic :: System :: Hardware',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    packages=find_packages(),
    install_requires=['kivy', 'trio', 'pymoa_remote'],
    extras_require={
        'dev': [
            'pytest>=3.6', 'pytest-cov', 'flake8', 'sphinx-rtd-theme',
            'coveralls', 'pytest-trio', 'sphinxcontrib-trio'],
    },
    package_data={
        'pymoa':
            []},
    project_urls={
        'Bug Reports': URL + '/issues',
        'Source': URL,
    },
)
