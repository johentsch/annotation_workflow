#!/usr/bin/env python
# coding: utf-8

import argparse, os
from fractions import Fraction as frac
from ms3 import Parse, make_gantt_data, resolve_dir #transform, roman_numeral2fifths, roman_numeral2semitones, name2fifths, rel2abs_key, labels2global_tonic, resolve_relative_keys
from plotly.offline import plot
import plotly.figure_factory as ff
# import pandas as pd

INDEX_FNAME = 'index.md'
GANTT_FNAME = 'gantt.md'
JEKYLL_CFG_FNAME = '_config.yml'
STYLE_FNAME = 'assets/css/style.scss'

INDEX_FILE = f"""
* [Modulation plans]({GANTT_FNAME})
"""

JEKYLL_CFG_FILE = "theme: jekyll-theme-tactile "

STYLE_FILE = """---
---

@import "{{ site.theme }}";

.inner {
  max-width: 95%;
  width: 1024px;
}
"""



def create_gantt(d, task_column='Task', title='Gantt chart', lines=None, cadences=None):
    """Creates and returns ``fig`` and populates it with features.

    When plotted with plot() or iplot(), ``fig`` shows a Gantt chart representing
    the piece's tonalities as extracted by the class Keys().

    Parameters
    ----------
    d: pd.Dataframe
        DataFrame with at least the columns ['Start', 'Finish', 'Task', 'Resource'].
        Other columns can be selected as 'Task' by passing ``task_column``.
        Further possible columns: 'Description'
    task_column : str
        If ``d`` doesn't have a 'Task' column, pass the name of the column that you want to use as such.
    title: str
        Title to be plotted

    Examples
    --------

    >>> iplot(create_gantt(df))

    does the same as

    >>> fig = create_gantt(df)
    >>> iplot(fig)

    To save the chart to a file instead of displaying it directly, use

    >>> plot(fig,filename="filename.html")
    """

    colors = {'applied': 'rgb(228,26,28)', # 'rgb(220, 0, 0)',
              'local': 'rgb(55,126,184)',  # (1, 0.9, 0.16),
              'tonic of adjacent applied chord(s)': 'rgb(77,175,74)'} # 'rgb(0, 255, 100)'}
    # 'Bluered', 'Picnic', 'Viridis', 'Rainbow'

    if task_column != 'Task':
        d = d.rename(columns={task_column: 'Task'})


    fig = ff.create_gantt(d,colors=colors,group_tasks=True,index_col='Resource',show_colorbar=True,
                       showgrid_x=True, showgrid_y=True ,title=title)

    fig['layout']['xaxis'].update({'type': None, 'title': 'Measures'})
    fig['layout']['yaxis'].update({'title': 'Tonicized keys'})

    if lines is not None:
        linestyle = {'color':'rgb(0, 0, 0)','width': 0.2,'dash': 'longdash'}
        lines = [{'type': 'line','x0':position,'y0':0,'x1':position,'y1':20,'line':linestyle} for position in lines]
        fig['layout']['shapes'] = fig['layout']['shapes'] + tuple(lines)



    if cadences is not None:
        lines = []
        annos = []
        hover_x = []
        hover_y = []
        hover_text = []
        alt = 0
        for i,r in cadences.iterrows():
            m = r.m
            c = r.type
            try:
                key = r.key
            except:
                key = None

            if c == 'PAC':
                c = 'PC'
                w = 1
                d = 'solid'
            elif c == 'IAC':
                c = 'IC'
                w = 0.5
                d = 'solid'
            elif c == 'HC':
                w = 0.5
                d = 'dash'
            elif c == 'EVCAD':
                c = 'EC'
                w = 0.5
                d = 'dashdot'
            elif c == 'DEC':
                c = 'DC'
                w = 0.5
                d = 'dot'
            else:
                print(f"{c}: Kadenztyp nicht vorgesehen")
            #c = c + f"<br>{key}"
            linestyle = {'color':'rgb(55, 128, 191)','width': w,'dash':d}
            annos.append({'x':m,'y':-0.01+alt*0.03,'font':{'size':7},'showarrow':False,'text':c,'xref':'x','yref':'paper'})
            lines.append({'type': 'line','x0':m,'y0':0,'x1':m,'y1':20,'line':linestyle})
            alt = 0 if alt else 1
            hover_x.append(m)
            hover_y.append(-0.5 - alt * 0.5)
            text = "Cad: " + r.type
            if key is not None:
                text += "<br>Key: " + key
            text += "<br>Beat: " + str(r.beat)
            hover_text.append(text)



        fig['layout']['shapes'] = fig['layout']['shapes'] + tuple(lines)
        fig['layout']['annotations'] = annos

        hover_trace=dict(type='scatter',opacity=0,
                        x=hover_x,
                        y=hover_y,
                        marker= dict(size= 14,
                                    line= dict(width=1),
                                    color= 'red',
                                    opacity= 0.3),
                        name= "Cadences",
                        text= hover_text)
        #fig['data'].append(hover_trace)
        fig.add_traces([hover_trace])
    return fig


def get_phraseends(at):
    if 'mn_fraction' not in at.columns:
        mn_fraction = at.mn + (at.mn_onset.astype(float)/at.timesig.map(frac).astype(float))
        at.insert(at.columns.get_loc('mn')+1, 'mn_fraction', mn_fraction)
    return at.loc[at.phraseend.notna(), 'mn_fraction'].to_list()


def main(args):
    write_gantt_charts(args)
    write_to_file(args, INDEX_FNAME, INDEX_FILE)
    write_to_file(args, JEKYLL_CFG_FNAME, JEKYLL_CFG_FILE)
    write_to_file(args, STYLE_FNAME, STYLE_FILE)
    write_gantt_file(args)


def write_gantt_charts(args):
    p = Parse(args.dir, paths=args.file, file_re=args.regex, exclude_re=args.exclude, recursive=args.nonrecursive, logger_cfg=dict(level=args.level))
    p.parse_mscx()
    gantt_path = check_and_create('gantt') if args.out is None else check_and_create(os.path.join(args.out, 'gantt'))
    for (key, i, _), at in p.get_lists(expanded=True).items(): # at stands for annotation table, i.e. DataFrame of expanded labels
        fname = p.fnames[key][i]
        score_obj = p._parsed_mscx[(key, i)]
        metadata = score_obj.mscx.metadata
        logger = score_obj.mscx.logger
        last_mn = metadata['last_mn']
        globalkey = metadata['annotated_key']
        logger.debug(f"Creating Gantt data for {fname}...")
        data = make_gantt_data(at)
        phrases = get_phraseends(at)
        data.sort_values(args.yaxis, ascending=False, inplace=True)
        logger.debug(f"Making and storing Gantt chart for {fname}...")
        fig = create_gantt(data, title=f"{fname} ({globalkey})", task_column=args.yaxis, lines=phrases)
        out_path = os.path.join(gantt_path, f'{fname}.html')
        plot(fig, filename=out_path)
        logger.debug(f"Stored as {out_path}")


def write_to_file(args, filename, content_str):
    path = check_dir('.') if args.out is None else args.out
    fname = os.path.join(path, filename)
    _ = check_and_create(os.path.dirname(fname)) # in case the file name included path components
    with open(fname, 'w', encoding='utf-8') as f:
        f.writelines(content_str)


def write_gantt_file(args):
    gantt_path = check_dir('gantt') if args.out is None else check_dir(os.path.join(args.out, 'gantt'))
    fnames = sorted(os.listdir(gantt_path))
    file_content = '\n'.join(f'<iframe id="igraph" scrolling="no" style="border:none;" seamless="seamless" src="gantt/{f}" height="600" width="100%"></iframe>' for f in fnames)
    write_to_file(args, GANTT_FNAME, file_content)


def test():
    p = Parse('/home/hentsche/annotation_workflow')
    p.parse_mscx()
    for (key, i, _), at in p.get_lists(expanded=True).items(): # at stands for annotation table, i.e. DataFrame of expanded labels
        fname = p.fnames[key][i]
        ID = (key, i)
        metadata = p._parsed_mscx[ID].mscx.metadata
        last_mn = metadata['last_mn']
        globalkey = metadata['annotated_key']
        data = make_gantt_data(at)
        phrases = get_phraseends(at)
        data.sort_values('semitones', ascending=False, inplace=True)
        fig = create_gantt(data, title=f"{fname} ({globalkey})", task_column='semitones', lines=phrases)
        print(plot(fig, filename=f'{fname}.html'))


def check_and_create(d):
    """ Turn input into an existing, absolute directory path.
    """
    if not os.path.isdir(d):
        d = resolve_dir(os.path.join(os.getcwd(), d))
        if not os.path.isdir(d):
            os.makedirs(d)
            print(f"Created directory {d}")
    return resolve_dir(d)


def check_dir(d):
    if not os.path.isdir(d):
        d = resolve_dir(os.path.join(os.getcwd(), d))
        if not os.path.isdir(d):
            raise argparse.ArgumentTypeError(d + ' needs to be an existing directory')
    return resolve_dir(d)



################################################################################
#                           COMMANDLINE INTERFACE
################################################################################
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description = '''\
---------------------------------------------------------
| Script for updating GitHub pages for a DCML subcorpus |
---------------------------------------------------------

Description goes here

''')
    parser.add_argument('-d', '--dir', metavar='DIR', nargs='+', type=check_dir, help='Folder(s) that will be scanned for input files. Defaults to current working directory if no individual files are passed via -f.')
    parser.add_argument('-n', '--nonrecursive', action='store_false', help="Don't scan folders recursively, i.e. parse only files in DIR.")
    parser.add_argument('-f', '--file', metavar='PATHs', nargs='+', help='Add path(s) of individual file(s) to be checked.')
    parser.add_argument('-r', '--regex', metavar="REGEX", default=r'\.mscx$', help="Select only file names including this string or regular expression. Defaults to MSCX files only.")
    parser.add_argument('-e', '--exclude', metavar="regex", default=r'(^(\.|_)|_reviewed)', help="Any files or folders (and their subfolders) including this regex will be disregarded."
                                     "By default, files including '_reviewed' or starting with . or _ are excluded.")
    parser.add_argument('-o', '--out', metavar='OUT_DIR', type=check_and_create, help="""Output directory.""")
    parser.add_argument('-y', '--yaxis', default='semitones', help="Ordering of keys on the y-axis: can be {semitones, fifths, numeral}.")
    parser.add_argument('-l','--level',default='INFO',help="Set logging to one of the levels {DEBUG, INFO, WARNING, ERROR, CRITICAL}.")
    args = parser.parse_args()
    # logging_levels = {
    #     'DEBUG':    logging.DEBUG,
    #     'INFO':     logging.INFO,
    #     'WARNING':  logging.WARNING,
    #     'ERROR':    logging.ERROR,
    #     'CRITICAL':  logging.CRITICAL,
    #     'D':    logging.DEBUG,
    #     'I':     logging.INFO,
    #     'W':  logging.WARNING,
    #     'E':    logging.ERROR,
    #     'C':  logging.CRITICAL
    #     }
    # logging.basicConfig(level=logging_levels[args.level.upper()])
    if args.file is None and args.dir is None:
        args.dir = os.getcwd()
    main(args)
