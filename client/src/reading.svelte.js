/** Tracks what is on screen, and which one section is being read.
 *
 *  Two different questions, measured from two different elements:
 *
 *  - *visible* is every section any part of which is on screen, measured from
 *    the section elements. Because sections nest, a subsection being on screen
 *    keeps its ancestors marked too, which is what makes the outline read as a
 *    breadcrumb rather than a single jumping highlight.
 *  - *active* is the one section the eye marks, measured from the *heading*
 *    elements. A section spans the rest of the document, so "unclipped" is
 *    meaningless applied to one; only a heading can be clipped or not.
 */
import { untrack } from 'svelte';

const MARGIN = 4;

export function createReading(getEntries) {
  let active = $state(null);
  let visible = $state(new Set());

  function navHeight() {
    const styles = getComputedStyle(document.documentElement);
    const rem = parseFloat(styles.fontSize) || 16;
    return (parseFloat(styles.getPropertyValue('--nav-height')) || 2.6) * rem;
  }

  /** The heading a section is titled by: its first heading descendant. */
  function headingFor(id) {
    const section = document.getElementById(id);
    return section?.matches('h1,h2,h3,h4,h5,h6')
      ? section
      : section?.querySelector('h1,h2,h3,h4,h5,h6') ?? null;
  }

  function compute(entries) {
    if (!entries.length) return { active: null, visible: new Set() };

    const top = navHeight() + MARGIN;
    const bottom = window.innerHeight - MARGIN;

    const onScreen = new Set();
    let current = null;
    let lastAbove = null;

    for (const entry of entries) {
      const section = document.getElementById(entry.id);
      if (section) {
        const box = section.getBoundingClientRect();
        // Any overlap at all with the readable band, not containment.
        if (box.bottom > top && box.top < bottom) onScreen.add(entry.id);
      }

      const heading = headingFor(entry.id);
      if (!heading) continue;
      const rect = heading.getBoundingClientRect();

      // The first heading clipped by neither the sticky bar nor the viewport
      // edge. Not an early return: the visible set still needs the rest.
      if (current === null && rect.top >= top && rect.bottom <= bottom) {
        current = entry.id;
      }
      // Otherwise the last heading scrolled past is the section whose body
      // fills the screen.
      if (rect.top < top) lastAbove = entry.id;
    }

    return {
      active: current ?? lastAbove ?? entries[0].id,
      visible: onScreen
    };
  }

  /** Sets are compared by identity, so a fresh one every frame would rerender
   *  the whole outline on every scroll tick even when nothing moved. */
  function same(a, b) {
    if (a.size !== b.size) return false;
    for (const value of a) if (!b.has(value)) return false;
    return true;
  }

  $effect(() => {
    const entries = getEntries();
    if (!entries.length) {
      active = null;
      visible = new Set();
      return;
    }

    let frame = 0;
    const update = () => {
      frame = 0;
      const next = compute(entries);
      active = next.active;
      if (!same(next.visible, untrack(() => visible))) visible = next.visible;
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };

    untrack(update);
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    return () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      if (frame) cancelAnimationFrame(frame);
    };
  });

  return {
    get active() { return active; },
    get visible() { return visible; }
  };
}
