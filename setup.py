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

scripts = []

setup(
    name='paper_scraper',
    version=__version__,
    description='paper_scraper: Package to scrape paper.',
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author='Matteo Manica, Jannis Born',
    author_email=(
        'drugilsberg@gmail.com, jab@zurich.ibm.com, '
    ),
    url='https://github.com/PhosphorylatedRabbits/paper_scraper',
    license='MIT',
    install_requires=[
        'arxiv', 'pymed', 'pandas'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    packages=find_packages(),
    scripts=scripts
)
