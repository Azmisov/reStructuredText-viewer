<script>
  /** Marks the section currently in reading position. */
  let { title = 'Currently reading' } = $props();
</script>

<svg class="eye" viewBox="0 0 24 16" aria-hidden="true" focusable="false"><title>{title}</title>
  <path
    d="M1 8s4-6 11-6 11 6 11 6-4 6-11 6S1 8 1 8Z"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
  />
  <circle cx="12" cy="8" r="2.6" fill="currentColor" />
</svg>

<style>
  .eye {
    width: 0.95em;
    height: 0.63em;
    flex: none;
    opacity: 0.75;
  }
</style>
