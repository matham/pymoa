from setuptools import setup, find_packages
import moa

with open('README.rst') as fh:
    long_description = fh.read()

setup(
    name='PyMoa',
    version=moa.__version__,
    author='Matthew Einhorn',
    author_email='moiein2000@gmail.com',
    license='MIT',
    description='Kivy based scientific platform for running experiments.',
    url='http://matham.github.io/moa/',
    long_description=long_description,
    classifiers=['License :: OSI Approved :: MIT License',
                 'Topic :: Scientific/Engineering',
                 'Topic :: System :: Hardware',
                 'Programming Language :: Python :: 2.7',
                 'Programming Language :: Python :: 3.3',
                 'Programming Language :: Python :: 3.4',
                 'Programming Language :: Python :: 3.5',
                 'Operating System :: Microsoft :: Windows',
                 'Intended Audience :: Developers'],
    packages=find_packages(),
    package_data={'moa': ['data/*.kv']},
    install_requires=['kivy']
    )
