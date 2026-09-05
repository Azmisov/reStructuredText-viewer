==========
Directives
==========

Every directive docutils ships with, so the renderer's coverage is visible
rather than assumed. Back to the `overview <index.rst>`_.

.. sectnum::

.. contents:: On this page
   :depth: 1
   :local:

The headings on this page are numbered by ``sectnum``, which is the directive
demonstrating itself - it applies to the whole document, so there is nowhere
to show it in isolation.

Admonitions
===========

The nine named ones, plus the generic form.

.. attention:: Attention.

.. caution:: Caution.

.. danger:: Danger.

.. error:: Error.

.. hint:: Hint.

.. important:: Important.

.. note:: Note.

.. tip:: Tip.

.. warning:: Warning.

.. admonition:: A title of your own

   The generic ``admonition`` takes any title. With ``:class: tip`` it borrows
   another one's styling.

Images and figures
==================

``image`` places a picture inline in the flow:

.. image:: chart.svg
   :alt: A small bar chart
   :width: 220px

``figure`` wraps one with a caption and, optionally, a legend:

.. figure:: chart.svg
   :alt: The same chart
   :width: 220px
   :align: center

   The caption is the first paragraph.

   Everything after it is the legend, which can hold any body markup at all -
   lists, code, another table.

Body elements
=============

.. topic:: A topic

   A self-contained aside with a title. Unlike a sidebar it does not float.

.. sidebar:: A sidebar
   :subtitle: With a subtitle

   Meant to sit beside the text it accompanies.

.. rubric:: A rubric is an unnumbered heading

.. epigraph::

   An epigraph is a block quote with a class.

   -- Attribution goes here

.. highlights::

   Highlights summarise what follows.

.. pull-quote::

   A pull-quote lifts a phrase out of the body.

A ``compound`` is one paragraph interrupted by something block-level, rather
than several paragraphs in a row. The parts run together instead of being
separated, and continuations are indented the way a broken paragraph is:

.. compound::

   The processing system will produce the following files:

   * ``report.pdf``
   * ``report.html``

   depending on the options given, and will leave them in the output directory
   named on the command line.

.. container:: custom-class

   A container passes its class straight through to the rendered element, which
   is the escape hatch for styling something the markup has no name for.

Tables
======

``list-table`` avoids drawing any grid art:

.. list-table:: Formats
   :header-rows: 1
   :widths: 20 30 50

   * - Format
     - Suffix
     - Notes
   * - reStructuredText
     - ``.rst``
     - The one you are reading
   * - Plain text
     - ``.txt``
     - Parsed the same way
   * - Legacy
     - ``.rest``
     - Also recognised

``csv-table`` reads its cells as CSV:

.. csv-table:: Measurements
   :header: "Sample", "Mass", "Notes"
   :widths: 20, 15, 65

   "A", "1.2 kg", "Nominal"
   "B", "0.8 kg", "Light, but within tolerance"

And a grid table, written by hand:

+------------+------------+-----------+
| Header 1   | Header 2   | Header 3  |
+============+============+===========+
| body row 1 | column 2   | column 3  |
+------------+------------+-----------+
| body row 2 | Cells span vertically  |
+------------+------------+-----------+

The ``table`` directive adds a title to any of them:

.. table:: A titled table

   =====  =====
   Input  Output
   =====  =====
   1      2
   3      4
   =====  =====

Code and literals
=================

``code-block`` (and its alias ``code``) highlights on the client:

.. code-block:: python

   def fibonacci(n):
       a, b = 0, 1
       for _ in range(n):
           yield a
           a, b = b, a + b

.. code:: javascript

   const sum = (xs) => xs.reduce((a, b) => a + b, 0);

``parsed-literal`` keeps the whitespace but still parses markup, which is how
you annotate a listing:

.. parsed-literal::

   $ rstview **samples/index.rst** --port 5686
     serving on http://localhost:5686/   *<- click it*

``line-block`` preserves line breaks without preserving spacing:

.. line-block::

   Line breaks are preserved exactly as written,
       and each level of indentation nests,
           compounding as it goes,

   while a blank line keeps the stanza break,
   and a line long enough to reach the edge of the column still wraps like any
   other paragraph would.

Maths
=====

Inline maths sits in a sentence: :math:`e^{i\pi} + 1 = 0`.

The ``math`` directive sets a formula on its own line:

.. math::

   \int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}

Several lines are aligned with the usual TeX environments:

.. math::

   \begin{aligned}
     \nabla \cdot \mathbf{E} &= \frac{\rho}{\varepsilon_0} \\
     \nabla \cdot \mathbf{B} &= 0 \\
     \nabla \times \mathbf{E} &= -\frac{\partial \mathbf{B}}{\partial t}
   \end{aligned}

A formula that does not parse renders as an error in place, rather than taking
the page down with it:

.. math::

   \notarealcommand{x}

Substitutions and roles
=======================

.. |project| replace:: reStructuredText-viewer
.. |dash| unicode:: U+2014
.. |today| date:: %Y-%m-%d

|project| |dash| built |today|.

Roles mark up a run of text: :emphasis:`emphasis`, :strong:`strong`,
:literal:`literal`, :subscript:`sub` and :superscript:`sup`,
:title-reference:`a title`, and :abbreviation:`abbr`.

``raw`` passes content straight through to one output format. **This viewer
drops it**: the renderer builds a component tree from an AST, and injecting
arbitrary markup would mean handing a document authority over the page it is
displayed in. The directive parses without error, and nothing appears:

.. raw:: html

   <p>If you can read this, raw HTML is no longer being dropped.</p>

Structure
=========

``sectnum`` numbers headings, ``contents`` builds the table at the top of this
page, and ``include`` pulls in another file. ``class`` attaches a class to the
next element:

.. class:: highlighted

This paragraph carries a class of its own.

``default-role`` changes what single backticks mean, and ``role`` defines a new
one:

.. role:: custom-role

Which then applies as :custom-role:`this`.

``target-notes`` turns external links into numbered footnotes, so a printed
copy still carries its URLs. It only sees *named* targets - the ``.. _name:
url`` form - and not URLs embedded directly in a link, which is why these two
are written separately from the links that use them:

Reading: docutils_ and its `specification <spec_>`_.

.. _docutils: https://docutils.sourceforge.io/
.. _spec: https://docutils.sourceforge.io/rst.html

.. target-notes::

A transition is four or more punctuation characters on their own line:

----

And that is the end of it.

.. footer:: Rendered by |project|.
