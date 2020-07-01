"""Package installer."""
import os
from setuptools import setup
from setuptools import find_packages

LONG_DESCRIPTION = ''
if os.path.exists('README.md'):
    with open('README.md') as fp:
        LONG_DESCRIPTION = fp.read()

scripts = ['bin/pytoda-filter-invalid-smi']

setup(
    name='paper_scraper',
    version='0.1.0',
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
