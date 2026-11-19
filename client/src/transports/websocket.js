/** WebSocket transport for the standalone server.
 *
 *  The socket is the only thing here that can go away, so this is also the
 *  only place that reconnects. Callers see the drop as a status change.
 */
export function websocketTransport() {
  let socket = null;
  let retry = 0;
  let onMessage = () => {};
  let onStatus = () => {};

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(`${proto}//${location.host}/ws`);

    socket.onopen = () => {
      retry = 0;
      onStatus('live');
    };
    socket.onmessage = (event) => onMessage(JSON.parse(event.data));
    socket.onclose = () => {
      onStatus('offline');
      untilAnswering().then(connect);
    };
    socket.onerror = () => socket.close();
  }

  /** Wait out a server that is down over HTTP, not by redialling the socket.
   *
   *  Firefox follows RFC 6455 §7.2.3: after a failed WebSocket connection it
   *  delays the next one to that host:port, exponentially up to a minute, and
   *  the penalty is shared by every tab. A tab redialling a stopped server
   *  every few seconds ran it up so far that a fresh tab opened once the
   *  daemon was back sat on "Connecting…" for seconds. A fetch is not
   *  delayed, so the socket is only tried again once something answers.
   */
  async function untilAnswering() {
    for (;;) {
      retry = Math.min(retry + 1, 5);
      await new Promise((resolve) => setTimeout(resolve, 200 * 2 ** (retry - 1)));
      try {
        const response = await fetch('/api/info', { cache: 'no-store' });
        if (response.ok) return;
      } catch {
        // Still down; keep waiting.
      }
    }
  }

  connect();

  return {
    send(message) {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(message));
        return true;
      }
      return false;
    },
    onMessage(callback) { onMessage = callback; },
    onStatus(callback) { onStatus = callback; }
  };
}
