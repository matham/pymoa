from setuptools import setup, find_packages
import moa


setup(
    name='Moa',
    version=moa.__version__,
    packages=find_packages(),
    package_data={
        'moa': ['data/*.kv'],
    },
    install_requires=['kivy>=1.8.1'],
    author='Matthew Einhorn',
    author_email='moiein2000@gmail.com',
    license='MIT',
    description=(
        'Kivy based experimental control.')
    )
