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
      retry = Math.min(retry + 1, 5);
      setTimeout(connect, 200 * 2 ** (retry - 1));
    };
    socket.onerror = () => socket.close();
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
