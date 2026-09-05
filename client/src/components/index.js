import Chart from './Chart.svelte';
import Callout from './Callout.svelte';

/** Maps a directive name to the component it renders.
 *  Must agree with the `components` block of rstview.config.json. */
export const COMPONENTS = {
  chart: Chart,
  callout: Callout
};
