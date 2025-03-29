"""Install package."""

import io
import os
import re

from setuptools import find_packages, setup

__version__ = re.search(
    r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
    io.open("paperscraper/__init__.py", encoding="utf_8_sig").read(),
).group(1)

LONG_DESCRIPTION = ""
if os.path.exists("README.md"):
    with open("README.md") as fp:
        LONG_DESCRIPTION = fp.read()

setup(
    name="paperscraper",
    version=__version__,
    description="paperscraper: Package to scrape papers.",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="Jannis Born, Matteo Manica",
    author_email=("jannis.born@gmx.de, drugilsberg@gmail.com"),
    url="https://github.com/jannisborn/paperscraper",
    license="MIT",
    install_requires=[
        "arxiv>=1.4.2",
        "pymed-paperscraper>=1.0.3",
        "pandas",
        "requests",
        "tqdm",
        "scholarly>=1.0.0",
        "seaborn",
        "matplotlib",
        "matplotlib_venn",
        "bs4",
        "impact-factor>=1.1.1",
        "thefuzz",
        "pytest",
        "tldextract",
        "semanticscholar",
        "pydantic",
        "unidecode",
    ],
    keywords=[
        "Academics",
        "Science",
        "Publication",
        "Search",
        "PubMed",
        "Arxiv",
        "Medrxiv",
        "Biorxiv",
        "Chemrxiv",
        "Google Scholar",
    ],
    packages=find_packages("."),
    package_data={"paperscraper.server_dumps": ["*"]},
    zip_safe=False,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
