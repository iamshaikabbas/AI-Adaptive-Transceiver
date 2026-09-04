import type { WSFrameEvent } from "../types/api";

type WSCallback = (event: WSFrameEvent) => void;

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectDelay = 1000;
const MAX_DELAY = 30000;
let listeners: WSCallback[] = [];
let intentionalClose = false;

function getWsUrl(): string {
  return "ws://127.0.0.1:8000/ws/simulation";
}

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  intentionalClose = false;

  try {
    ws = new WebSocket(getWsUrl());
  } catch {
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    reconnectDelay = 1000;
  };

  ws.onmessage = (ev) => {
    try {
      const event = JSON.parse(ev.data) as WSFrameEvent;
      for (const cb of listeners) cb(event);
    } catch {
      // ignore malformed messages
    }
  };

  ws.onclose = () => {
    ws = null;
    if (!intentionalClose) scheduleReconnect();
  };

  ws.onerror = () => {
    ws?.close();
  };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    reconnectDelay = Math.min(reconnectDelay * 2, MAX_DELAY);
    connect();
  }, reconnectDelay);
}

export const wsService = {
  connect() {
    connect();
  },

  disconnect() {
    intentionalClose = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
  },

  subscribe(cb: WSCallback): () => void {
    listeners.push(cb);
    return () => {
      listeners = listeners.filter((l) => l !== cb);
    };
  },

  isConnected(): boolean {
    return ws?.readyState === WebSocket.OPEN;
  },
};
