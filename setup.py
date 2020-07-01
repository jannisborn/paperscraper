"""Install package."""
import os
from setuptools import setup
from setuptools import find_packages
import io
import re

__version__ = re.search(
    r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
    io.open('paper_scraper/__init__.py', encoding='utf_8_sig').read()
).group(1)

LONG_DESCRIPTION = ''
if os.path.exists('README.md'):
    with open('README.md') as fp:
        LONG_DESCRIPTION = fp.read()

setup(
    name='paper_scraper',
    version=__version__,
    description=('Paper scraper for arXiv, PubMed, bio/medRxiv.'),
    long_description=LONG_DESCRIPTION,
    author='IBM RXN team.',
    url='https://github.com/PhosphorylatedRabbits/paper_scraper',
    install_requires=[
        'requests==2.24.0'
    ],
    classifiers=[
        'Intended Audience :: Developers', 'Intended Audience :: Science/Research',
        'Programming Language :: Python :: 3', 'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    packages=find_packages(),
    scripts=[]
)
