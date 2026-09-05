=========
 rstview
=========

Introduction
============

Hello *world*, with a `link <https://example.com>`_, ``inline code``, and a
footnote [#note]_.

Cross-document: read the `user guide <guide.rst>`_, browse every directive in
the `directive showcase <directives.rst>`_, or jump straight to
`installing <guide.rst#installing>`_. In this document, see `Tables`_.

- first item
- second item

.. note::

   Admonitions render through a shared component.

Custom components
=================

.. chart::
   :series: [3, 7, 2, 9, 4]
   :title: Build times
   :height: 60

.. callout:: Body is parsed reST
   :kind: warning

   So *emphasis* and ``literals`` still work in here.

Tables
======

+----------+---------+
| Language | Blocks  |
+==========+=========+
| Python   | 2       |
+----------+---------+
| YAML     | 1       |
+----------+---------+

Code
====

.. code-block:: python

   def main():
       v = "really long line of text that probably overflows with a smaller content window width and requires horizontal scrolling"
       return 42

Errors degrade locally
======================

.. nonexistent:: oops

   body text

.. [#note] Footnotes land at the end.

Admonition gallery
==================

.. tip::

   A tip.

.. warning::

   A warning.

.. danger::

   Danger.

.. important::

   Important.
