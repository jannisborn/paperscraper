import logging
import math
import os
from typing import Iterable, List

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib_venn import venn2, venn2_circles, venn3, venn3_circles

# Set matplotlib logging depth
mpl_logger = logging.getLogger('matplotlib')
mpl_logger.setLevel(logging.WARNING)


def plot_comparison(
    data_dict: dict,
    keys: List[str],
    x_ticks: List[str] = ['2015', '2016', '2017', '2018', '2019', '2020'],
    show_preprint: bool = False,
    title_text: str = '',
    keyword_text=None,
    figpath: str = 'comparison_plot.pdf',
) -> None:
    """Plot temporal evolution of number of papers per keyword

    Args:
        data_dict (dict): A dictionary with keywords as keys. Each value should be a
            dictionary itself, with keys for the different APIs. For example
            data_dict = {
                'covid_19.jsonl': {
                    'pubmed': [0, 0, 0, 12345],
                    'arxiv': [0, 0, 0, 1234],
                    ...
                }
                'coronavirus.jsonl':
                    'pubmed': [234, 345, 456, 12345],
                    'arxiv': [123, 234, 345, 1234],
                    ...
                }
            }
        keys (List[str]): List of keys which should be plotted. This has to be a
           subset of data_dict.keys().
        x_ticks (List[str]): List of strings to be used for the x-ticks. Should have
            same length as data_dict[key][database]. Defaults to ['2015', '2016',
            '2017', '2018', '2019', '2020'], meaning that papers are aggregated per
            year.
        show_preprint (bool, optional): Whether preprint servers are aggregated or not.
            Defaults to False.
        title_text (str, optional): Title for the produced figure. Defaults to ''.
        keyword_text ([type], optional): Figure caption per keyword. Defaults to None,
            i.e. empty strings will be used.
        figpath (str, optional): Name under which figure is saved. Relative or absolute
            paths can be given. Defaults to 'comparison_plot.pdf'.

    Raises:
        KeyError: If a database is missing in data_dict.
    """

    sns.set_palette(sns.color_palette("colorblind", 10))
    plt.rcParams.update({'hatch.color': 'w'})
    plt.figure(figsize=(8, 5))

    arxiv, biorxiv, pubmed, medrxiv, chemrxiv, preprint = [], [], [], [], [], []

    for key in keys:
        try:
            arxiv.append(data_dict[key]['arxiv'])
            biorxiv.append(data_dict[key]['biorxiv'])
            medrxiv.append(data_dict[key]['medrxiv'])
            chemrxiv.append(data_dict[key]['chemrxiv'])
            pubmed.append(data_dict[key]['pubmed'])
        except KeyError:
            raise KeyError(
                f'Did not find all DBs for {key}, only found {data_dict[key].keys()}'
            )
        preprint.append(arxiv[-1] + biorxiv[-1] + medrxiv[-1] + chemrxiv[-1])

    ind = np.arange(len(arxiv[0]))  # the x locations for the groups
    width = [0.2] * len(ind)  # the width of the bars: can also be len(x) sequence
    if len(keys) == 2:
        pos = [-0.2, 0.2]
    elif len(keys) == 3:
        pos = [-0.3, 0.0, 0.3]

    plts = []
    legend_plts = []
    patterns = ('|||', 'oo', 'xx', '..', '**')
    if show_preprint:
        bars = [pubmed, preprint]
        legend_platform = ['PubMed', 'Preprint']
    else:
        bars = [pubmed, arxiv, biorxiv, chemrxiv, medrxiv]
        legend_platform = ['PubMed', 'ArXiv', 'BiorXiv', 'ChemRxiv', 'MedRxiv']
    for idx in range(len(keys)):
        bottom = 0

        for bidx, b in enumerate(bars):
            if idx == 0:
                p = plt.bar(
                    ind + pos[idx],
                    b[idx],
                    width,
                    linewidth=1,
                    edgecolor='k',
                    bottom=bottom,
                )
            else:
                p = plt.bar(
                    ind + pos[idx],
                    b[idx],
                    width,
                    color=next(iter(plts[bidx])).get_facecolor(),
                    linewidth=1,
                    edgecolor='k',
                    bottom=bottom,
                )

            bottom += b[idx]
            plts.append(p)
        legend_plts.append(
            plt.bar(ind + pos[idx], np.zeros((len(ind),)), color='k', bottom=bottom)
        )

    plt.ylabel('Counts', size=15)
    plt.xlabel('Years', size=15)
    plt.title(f"Keywords: {title_text}", size=14)
    # Customize minor tick labels
    plt.xticks(ind, x_ticks, size=10)

    legend = plt.legend(
        legend_platform,
        prop={'size': 12},
        loc='upper left',
        title='Platform:',
        title_fontsize=13,
        ncol=1,
    )

    # Now set the hatches to not destroy legend

    for idx, stackbar in enumerate(plts):
        pidx = int(np.floor(idx / len(bars)))
        for bar in stackbar:
            bar.set_hatch(patterns[pidx])

    for idx, stackbar in enumerate(legend_plts):
        for bar in stackbar:
            bar.set_hatch(patterns[idx])

    if not keyword_text:
        keyword_text = [''] * len(keys)

    plt.legend(
        legend_plts,
        keyword_text,
        loc='upper center',
        prop={'size': 12},
        title='Keywords (X):',
        title_fontsize=13,
    )
    plt.gca().add_artist(legend)

    get_step_size = lambda x: round(x / 10, -math.floor(math.log10(x)) + 1)
    ymax = plt.gca().get_ylim()[1]
    step_size = np.clip(get_step_size(ymax), 5, 1000)
    y_steps = np.arange(0, ymax, step_size)

    for y_step in y_steps:
        plt.hlines(y_step, xmax=10, xmin=-1, color='black', linewidth=0.1)
    plt.xlim([-0.5, len(ind)])
    plt.ylim([0, ymax * 1.02])

    plt.tight_layout()
    plt.savefig(figpath)
    plt.show()


get_name = lambda n: ' vs. '.join(list(map(lambda x: x.split(' ')[0], n)))


def plot_venn_two(
    sizes: List[int],
    labels: List[str],
    figpath: str = 'venn_two.pdf',
    title: str = '',
    **kwargs,
) -> None:
    """Plot a single Venn Diagram with two terms.

    Args:
        sizes (List[int]): List of ints of length 3. First two elements correspond to
            the labels, third one to the intersection.
        labels ([type]): List of str of length 2, containing names of circles.
        figpath (str): Name under which figure is saved. Defaults to 'venn_two.pdf', i.e. it is
            inferred from labels.
        title (str): Title of the plot. Defaults to '', i.e. it is inferred from
            labels.
        **kwargs: Additional keyword arguments for venn2.
    """
    assert len(sizes) == 3, 'Incorrect type/length of sizes'
    assert len(labels) == 2, 'Incorrect type/length of labels'

    title = get_name(labels) if title == '' else title
    figname = title.lower().replace(' vs. ', '_') if figname == '' else figname
    venn2(subsets=sizes, set_labels=labels, alpha=0.6, **kwargs)
    venn2_circles(
        subsets=sizes, linestyle='solid', linewidth=0.6, color='grey', **kwargs
    )
    if kwargs.get('ax', False):
        print(kwargs, type(kwargs))
        print(kwargs['ax'])
        kwargs['ax'].set_title(title, fontdict={'fontweight': 'bold'}, size=15)
    else:
        plt.title(title, fontdict={'fontweight': 'bold'}, size=15)
        plt.savefig(os.path.join(SAVE_PATH, f'{figname}.pdf'))


def plot_venn_three(
    sizes: List[int], labels: List[str], figname: str = '', title: str = '', **kwargs
) -> None:
    """Plot a single Venn Diagram with two terms.

    Args:
        sizes (List[int]): List of ints of length 3. First two elements correspond to
            the labels, third one to the intersection.
        labels (List[str]): List of str of length 2, containing names of circles.
        figname (str): Name under which figure is saved. Defaults to '', i.e. it is
            inferred from labels.
        title (str): Title of the plot. Defaults to '', i.e. it is inferred from
            labels.
        **kwargs: Additional keyword arguments for venn3.
    """
    assert len(sizes) == 7, 'Incorrect type/length of sizes'
    assert len(labels) == 3, 'Incorrect type/length of labels'

    title = get_name(labels) if title == '' else title
    figname = title.lower().replace(' vs. ', '_') if figname == '' else figname

    venn3(subsets=sizes, set_labels=labels, alpha=0.6, **kwargs)
    venn3_circles(
        subsets=sizes, linestyle='solid', linewidth=0.6, color='grey', **kwargs
    )

    if kwargs.get('ax', False):
        kwargs['ax'].set_title(title, fontdict={'fontweight': 'bold'}, size=15)
    else:
        plt.title(title, fontdict={'fontweight': 'bold'}, size=15)
        plt.savefig(os.path.join(SAVE_PATH, f'{figname}.pdf'))


def plot_multiple_venn(
    sizes: List[List[int]],
    labels: List[List[str]],
    figname: str,
    titles: List[str],
    suptitle: str = '',
    gridspec_kw: dict = {},
    figsize: Iterable = (8, 4.5),
    **kwargs,
) -> None:
    """Plots multiple Venn Diagrams next to each other

    Args:
        sizes (List[List[int]]): List of lists with sizes, one per Venn Diagram.
            Lengths of lists should be either 3 (plot_venn_two) or 7
            (plot_venn_two).
        labels (List[List[str]]): List of Lists of str containing names of circles.
            Lengths of lists should be either 2 or 3.
        figname (str): Name under which figure is saved. Defaults to '', i.e. it is
            inferred from labels.
        titles (List[str]): Titles of subplots. Should have same length like labels
            and sizes.
        suptitle (str): Title of entire plot. Defaults to '', i.e. no title.
        gridspec_kw (dict): Additional keyword args for plt.subplots. Useful to
            adjust width of plots. E.g.
                gridspec_kw={'width_ratios': [1, 2]}
            will make the second Venn Diagram double as wide as first one.
        **kwargs: Additional keyword arguments for venn3.
    """

    assert len(sizes) == len(labels), 'Length of labels & sizes dont match.'
    assert len(sizes) == len(titles), 'Length of titles & sizes dont match.'
    assert len(sizes) > 1, 'At least 2 items should be provided.'
    assert all(list(map(lambda x: len(x) in [2, 3], labels))), 'Wrong label sizes.'
    assert all(list(map(lambda x: len(x) in [3, 7], sizes))), 'Wrong label sizes.'

    fig, axes = plt.subplots(1, len(sizes), gridspec_kw=gridspec_kw, figsize=figsize)
    plt.suptitle(suptitle, size=18, fontweight='bold')

    for idx, (size, label, title) in enumerate(zip(sizes, labels, titles)):
        if len(label) == 2:
            plot_venn_two(size, label, title=title, ax=axes[idx])
        elif len(label) == 3:
            plot_venn_three(size, label, title=title, ax=axes[idx])

    plt.savefig(os.path.join(SAVE_PATH, f'{figname}.pdf'))
