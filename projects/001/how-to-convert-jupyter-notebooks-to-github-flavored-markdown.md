---
title: How to convert Jupyter notebooks to GitHub flavored Markdown
---

***

**NOTE: This text has been automatically extracted from a [Colab/Jupyter notebook](https://colab.research.google.com/drive/1qJKbkTiAqWu9fCsLEdGJavFDgsGLmN82#revisionId=0BzK9MbvobeYaaW1SZGJ1OTh1bmt1S3dEYTU2eEEwQmR2Nm5FPQ){:target="_blank"}. If you have any questions, feel free to leave a comment there (requires sign in with a Google account).**

***

> **_NOTE_**: If you are on Colab, you can download the code below as a single script using **File ▶ Download ▶ Download .py**. The script can then be run with `python3 ipynbtomarkdown.py <notebook.ipynb>`

Given Jupyter Notebooks are JSON files, we need to import the `json` module. The `sys` module will be used to get the notebook file name from arguments.

```python
import json
import sys
```

For Markdown cells, print as is:

```python
def emit_markdown(src):
    return '\n{}\n'.format(''.join(src))
```

If a title is detected, print it as a [YAML front matter](https://jekyllrb.com/docs/front-matter/):

```python
def extract_front_matter(idx, src):
    if idx == 0 and src[0].startswith('#'):
        return src[1:], '---\ntitle: {}\n---'.format(src[0][1:].strip())
    else:
        return src, ''
```

For code cells, wrap in a code block with Python syntax highlighting, except for those that start with a `%%bash` cell magic, for which we print without any syntax highlighting.

```python
def emit_code(src):
    return '\n```{}\n{}\n```\n'.format('' if src[0] == '%%bash\n' else 'python',''.join(src))
```

Parse the JSON from the notebook and iterate on each cell, printing it based on the type:

```python
with open(sys.argv[1], 'r') as f:
    data = json.load(f)
    assert data['metadata']['language_info']['name'] == 'python'
    markdown = ''
    for idx, c in enumerate(data['cells']):
        if c['cell_type'] == 'markdown':
            src, front_matter = extract_front_matter(idx, c['source'])
            markdown += front_matter + emit_markdown(src)
        elif c['cell_type'] == 'code':
            markdown += emit_code(c['source'])
    print(markdown + '\n<!-- Generated with ipynbtomarkdown.py -->')
```

## Known issues

- Plain URLs (e.g. `https://example.com/`) are not converted to links automatically. The workaround is to use the `[...](...)` Markdown syntax.

<!-- Generated with ipynbtomarkdown.py -->
