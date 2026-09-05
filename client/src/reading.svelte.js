/** Tracks which section is currently being read.
 *
 *  Measured from the *heading* elements, not the sections: a section spans the
 *  rest of the document, so it is never fully visible and "unclipped" would be
 *  meaningless applied to it.
 */
import { untrack } from 'svelte';

const MARGIN = 4;

export function createReading(getEntries) {
  let active = $state(null);

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
    if (!entries.length) return null;

    const top = navHeight() + MARGIN;
    const bottom = window.innerHeight - MARGIN;

    let lastAbove = null;
    for (const entry of entries) {
      const heading = headingFor(entry.id);
      if (!heading) continue;
      const rect = heading.getBoundingClientRect();

      // First heading clipped by neither the sticky bar nor the viewport edge.
      if (rect.top >= top && rect.bottom <= bottom) return entry.id;

      // Otherwise remember the last one scrolled past, which is the section
      // whose body fills the screen.
      if (rect.top < top) lastAbove = entry.id;
    }
    return lastAbove ?? entries[0].id;
  }

  $effect(() => {
    const entries = getEntries();
    if (!entries.length) {
      active = null;
      return;
    }

    let frame = 0;
    const update = () => {
      frame = 0;
      active = compute(entries);
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
    get active() { return active; }
  };
}
