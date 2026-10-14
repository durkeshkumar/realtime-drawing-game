
export interface DrawingPoint {
  x: number;
  y: number;
}

export interface DrawingEvent {
  type: "draw_start" | "draw_move" | "draw_end" | "clear_canvas";
  round_number: number;
  color: string;
  line_width: number;
  points: DrawingPoint[];
}

export interface GuessEvent {
  type: "guess";
  round_number: number;
  guess: string;
}

export type OutgoingGameEvent =
  | DrawingEvent
  | GuessEvent
  | { type: "ping" };

export interface ServerGameEvent {
  type: string;
  [key: string]: unknown;
}

export interface WebSocketCredentials {
  roomCode: string;
  playerId: number;
  token: string;
}

export type WebSocketStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

type EventListener = (event: ServerGameEvent) => void;
type StatusListener = (status: WebSocketStatus) => void;

export class DrawingGameSocket {
  private socket: WebSocket | null = null;
  private readonly credentials: WebSocketCredentials;
  private readonly eventListeners = new Set<EventListener>();
  private readonly statusListeners = new Set<StatusListener>();

  public status: WebSocketStatus = "disconnected";

  constructor(credentials: WebSocketCredentials) {
    this.credentials = credentials;
  }

  connect(): void {
    if (
      this.socket &&
      (this.socket.readyState === WebSocket.CONNECTING ||
        this.socket.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

    if (!apiBaseUrl) {
      this.setStatus("error");
      throw new Error(
        "VITE_API_BASE_URL is not configured. Please check frontend/.env."
      );
    }

    const baseUrl = new URL(apiBaseUrl);
    const protocol = baseUrl.protocol === "https:" ? "wss:" : "ws:";
    const roomCode = encodeURIComponent(
      this.credentials.roomCode.trim().toUpperCase()
    );

    const url = new URL(
      `${protocol}//${baseUrl.host}/ws/rooms/${roomCode}`
    );

    url.searchParams.set("player_id", String(this.credentials.playerId));
    url.searchParams.set("token", this.credentials.token);

    this.setStatus("connecting");

    try {
      this.socket = new WebSocket(url.toString());
    } catch (error) {
      this.setStatus("error");
      throw error;
    }

    this.socket.addEventListener("open", () => {
      this.setStatus("connected");
    });

    this.socket.addEventListener("message", (message: MessageEvent<string>) => {
      try {
        const event: unknown = JSON.parse(message.data);

        if (
          typeof event === "object" &&
          event !== null &&
          "type" in event &&
          typeof event.type === "string"
        ) {
          this.eventListeners.forEach((listener) => {
            listener(event as ServerGameEvent);
          });
        }
      } catch {
        console.error("Received an invalid WebSocket message.");
      }
    });

    this.socket.addEventListener("error", () => {
      this.setStatus("error");
    });

    this.socket.addEventListener("close", () => {
      this.setStatus("disconnected");
      this.socket = null;
    });
  }

  send(event: OutgoingGameEvent): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return false;
    }

    this.socket.send(JSON.stringify(event));
    return true;
  }

  ping(): boolean {
    return this.send({ type: "ping" });
  }

  onEvent(listener: EventListener): () => void {
    this.eventListeners.add(listener);

    return () => {
      this.eventListeners.delete(listener);
    };
  }

  onStatusChange(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    listener(this.status);

    return () => {
      this.statusListeners.delete(listener);
    };
  }

  disconnect(): void {
    const socket = this.socket;
    this.socket = null;

    if (
      socket &&
      (socket.readyState === WebSocket.CONNECTING ||
        socket.readyState === WebSocket.OPEN)
    ) {
      socket.close(1000, "Client disconnected");
    }

    this.setStatus("disconnected");
  }

  private setStatus(status: WebSocketStatus): void {
    this.status = status;

    this.statusListeners.forEach((listener) => {
      listener(status);
    });
  }
}
