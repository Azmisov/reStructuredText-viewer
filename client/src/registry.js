import Section from './nodes/Section.svelte';
import Title from './nodes/Title.svelte';
import Reference from './nodes/Reference.svelte';
import LiteralBlock from './nodes/LiteralBlock.svelte';
import SystemMessage from './nodes/SystemMessage.svelte';
import Component from './nodes/Component.svelte';
import Image from './nodes/Image.svelte';
import Figure from './nodes/Figure.svelte';
import Admonition from './nodes/Admonition.svelte';
import Entry from './nodes/Entry.svelte';
import TableHead from './nodes/TableHead.svelte';
import Footnote from './nodes/Footnote.svelte';
import FootnoteReference from './nodes/FootnoteReference.svelte';
import Math from './nodes/Math.svelte';
import MathBlock from './nodes/MathBlock.svelte';
import Document from './nodes/Document.svelte';
import Table from './nodes/Table.svelte';
import Aside from './nodes/Aside.svelte';
import Raw from './nodes/Raw.svelte';
import Unknown from './nodes/Unknown.svelte';

/** docutils types that map cleanly onto a single HTML element. */
export const SIMPLE = {
  paragraph: 'p',
  emphasis: 'em',
  strong: 'strong',
  literal: 'code',
  subscript: 'sub',
  superscript: 'sup',
  title_reference: 'cite',
  abbreviation: 'abbr',
  acronym: 'abbr',
  bullet_list: 'ul',
  enumerated_list: 'ol',
  list_item: 'li',
  definition_list: 'dl',
  definition_list_item: 'div',
  term: 'dt',
  definition: 'dd',
  field_list: 'dl',
  field: 'div',
  field_name: 'dt',
  field_body: 'dd',
  option_list: 'dl',
  block_quote: 'blockquote',
  attribution: 'cite',
  transition: 'hr',
  line_block: 'div',
  line: 'div',
  inline: 'span',
  // `.. sectnum::` puts the number in a `generated` node inside the title.
  generated: 'span',
  container: 'div',
  compound: 'div',
  // `.. header::` / `.. footer::` are page decoration meant for print output.
  // docutils puts both in a `decoration` node at the *top* of the doctree, so
  // a footer renders above the body here rather than below it. Showing the
  // content in the wrong place beats dropping it silently; hoisting it would
  // mean the renderer reaching outside its own subtree.
  header: 'div',
  footer: 'div',
  rubric: 'p',
  doctest_block: 'pre',
  tbody: 'tbody',
  row: 'tr',
  caption: 'figcaption',
  legend: 'div',
  label: 'span',
  problematic: 'span'
};

/** Types needing real structure or behaviour get a component. */
export const COMPONENTS = {
  document: Document,
  section: Section,
  table: Table,
  topic: Aside,
  sidebar: Aside,
  raw: Raw,
  title: Title,
  subtitle: Title,
  reference: Reference,
  literal_block: LiteralBlock,
  system_message: SystemMessage,
  component: Component,
  image: Image,
  math: Math,
  math_block: MathBlock,
  figure: Figure,
  entry: Entry,
  thead: TableHead,
  footnote: Footnote,
  citation: Footnote,
  footnote_reference: FootnoteReference,
  citation_reference: FootnoteReference,
  admonition: Admonition,
  note: Admonition,
  warning: Admonition,
  tip: Admonition,
  hint: Admonition,
  important: Admonition,
  caution: Admonition,
  attention: Admonition,
  danger: Admonition,
  error: Admonition
};

/** Rendered as their children, with no wrapper element of their own. */
export const TRANSPARENT = new Set([
  'tgroup', 'description', 'option_group', 'decoration'
]);

/** Present in the doctree but with nothing to show. */
export const HIDDEN = new Set([
  'comment',
  'substitution_definition',
  'colspec',
  'target',
  'meta'
]);

/** Types that need a class hook for styling but get none from docutils.
 *
 *  `epigraph`, `pull-quote` and `highlights` arrive with their class already
 *  set - they are all `block_quote` and would be indistinguishable otherwise -
 *  but `legend` and `compound` are their own node types carrying nothing, so
 *  the type has to become the hook. Only the ones CSS actually targets are
 *  listed; tagging every paragraph would be DOM weight for nothing. */
export const TYPE_CLASS = {
  legend: 'rst-legend',
  compound: 'rst-compound',
  // A line block expresses indentation by *nesting* another line_block, so
  // both levels need a hook or there is nothing for the indent to hang on.
  line_block: 'rst-line-block',
  line: 'rst-line',
  rubric: 'rst-rubric',
  // Both `title_reference` and `attribution` render as <cite>, so styling the
  // element would catch both. The hook keeps the two apart.
  title_reference: 'rst-title-ref'
};

/** Block-level text containers, which need their own base direction so a
 *  mixed-language document resolves each block independently. */
export const AUTO_DIR = new Set([
  'paragraph', 'list_item', 'term', 'definition', 'block_quote',
  'entry', 'field_body', 'attribution', 'line', 'caption', 'rubric'
]);

export { Unknown };
