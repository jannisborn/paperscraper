"""Install package."""
import os
from setuptools import setup
from setuptools import find_packages
import io
import re

__version__ = re.search(
    r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
    io.open('paperscraper/__init__.py', encoding='utf_8_sig').read(),
).group(1)

LONG_DESCRIPTION = ''
if os.path.exists('README.md'):
    with open('README.md') as fp:
        LONG_DESCRIPTION = fp.read()

setup(
    name='paperscraper',
    version=__version__,
    description='paperscraper: Package to scrape papers.',
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author='Jannis Born, Matteo Manica',
    author_email=('jannis.born@gmx.de, drugilsberg@gmail.com'),
    url='https://github.com/PhosphorylatedRabbits/paperscraper',
    license='MIT',
    install_requires=[
        'arxiv',
        'pymed',
        'pandas',
        'requests',
        'tqdm',
        'scholarly',
        'seaborn',
        'matplotlib',
        'matplotlib_venn',
    ],
    keywords=[
        'Academics',
        'Science',
        'Publication',
        'Search',
        'PubMed',
        'Arxiv',
        'Medrxiv',
        'Biorxiv',
        'Chemrxiv',
    ],
    packages=find_packages('.'),
    package_data={'paperscraper.server_dumps': ['*']},
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
