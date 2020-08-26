from setuptools import setup

name = 'jsonsocket'

setup(
    name=name,
    version=0.1,
    description='This is a small Python library for sending data over sockets. ',
    author='github',
    author_email='',
    packages=[name],  #same as name
    requirements=["schedule"]
)
