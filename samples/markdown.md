---
author: rstview
version: 0.1
---

# Markdown

Markdown documents go through [MyST](https://myst-parser.readthedocs.io) into
the same docutils tree reST produces, so they render with the same
components. Back to the [overview](index.rst), or jump to
[installing](guide.rst#installing) in the reST guide.

## Inline

Text with *emphasis*, **strong**, `code`, ~~strikethrough~~, a
[link](https://example.com), a bare https://example.org autolink, inline math
$e^{i\pi} + 1 = 0$, and a footnote[^note].
Press <kbd>Ctrl</kbd>+<kbd>C</kbd>; H<sub>2</sub>O; <mark>highlighted</mark>.\
After a hard line break.

[^note]: Footnotes land at the end, as in reST.

## Lists

- [x] Task lists
- [ ] with open items
- and plain ones

1. Ordered
2. lists

Term
: A definition list.

## Tables

| Left | Center | Right |
|:-----|:------:|------:|
| a    | b      | 1     |
| `c`  | **d**  | 22    |

## Admonitions

> [!NOTE]
> A GitHub-style alert.

:::{tip}
A MyST directive, fenced with colons.
:::

```{warning}
Or with backticks.
```

## Code and math

```python
def main():
    return 42
```

$$
\int_0^1 x^2 \, dx = \frac{1}{3}
$$

## Custom components

Directives from `rstview.config.json` work in Markdown too:

```{chart}
:series: [2, 5, 3, 8, 6]
:title: From Markdown
:height: 60
```

:::{callout} The body is Markdown here
:kind: info

So *emphasis* and `code` work inside.
:::

## HTML

<details>
<summary>Allowlisted HTML becomes real nodes</summary>

Tags with a docutils equivalent map onto it; the rest keep their text and lose
the tags. Nothing reaches the page as markup.

</details>

<p align="center"><img src="chart.svg" alt="A chart" width="160"></p>

## Embedded reST

```{eval-rst}
.. note::

   A reST block inside a Markdown document, with `a link <https://docutils.sourceforge.io>`_.
```
