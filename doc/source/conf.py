# -*- coding: utf-8 -*-

import moa

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.intersphinx'
]

html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',
        'searchbox.html',
        'sourcelink.html'
    ]
}

html_theme_options = {
    'github_button': 'true',
    'github_banner': 'true',
    'github_user': 'matham',
    'github_repo': 'moa'
}

intersphinx_mapping = {
    'kivy': ('https://kivy.org/docs/', None)
}

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'Moa'

# The short X.Y version.
version = moa.__version__
# The full version, including alpha/beta/rc tags.
release = moa.__version__

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = []

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'alabaster'

# Output file base name for HTML help builder.
htmlhelp_basename = 'Moadoc'

latex_elements = {}

latex_documents = [
  ('index', 'Moa.tex', u'Moa Documentation',
   u'Matthew Einhorn', 'manual'),
]

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'Moa', u'Moa Documentation',
     [u'Matthew Einhorn'], 1)
]

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'Moa', u'Moa Documentation',
   u'Matthew Einhorn', 'Moa', 'One line description of project.',
   'Miscellaneous'),
]
