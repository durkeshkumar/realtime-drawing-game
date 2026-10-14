
import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent } from "react";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Chip,
  Container,
  Divider,
  IconButton,
  Paper,
  Slider,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import BrushRoundedIcon from "@mui/icons-material/BrushRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import SendRoundedIcon from "@mui/icons-material/SendRounded";
import EmojiEventsRoundedIcon from "@mui/icons-material/EmojiEventsRounded";
import PaletteRoundedIcon from "@mui/icons-material/PaletteRounded";
import { useNavigate, useParams } from "react-router-dom";
import apiClient from "../../api/client";
import { DrawingGameSocket } from "../../api/websocket";
import type {
  DrawingPoint,
  ServerGameEvent,
  WebSocketStatus,
} from "../../api/websocket";

interface ChatMessage {
  id: number;
  username: string;
  text: string;
  type: "guess" | "system" | "correct";
}

interface LobbyPlayer {
  id: number;
  display_name: string;
  score: number;
  is_ready: boolean;
}

interface LobbyResponse {
  room_code: string;
  status: string;
  player_count: number;
  max_players: number;
  players: LobbyPlayer[];
}

interface NormalizedPoint {
  x: number;
  y: number;
}

interface StrokeStyle {
  color: string;
  line_width: number;
}

const COLORS = [
  "#111827",
  "#ef4444",
  "#f97316",
  "#eab308",
  "#22c55e",
  "#06b6d4",
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
  "#ffffff",
];

const CANVAS_WIDTH = 1000;
const CANVAS_HEIGHT = 600;
const ROUND_DURATION_SECONDS = 60;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : fallback;
}

function getText(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function getApiErrorMessage(error: unknown): string {
  if (
    isRecord(error) &&
    isRecord(error.response) &&
    isRecord(error.response.data) &&
    typeof error.response.data.detail === "string"
  ) {
    return error.response.data.detail;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Unable to communicate with the game server.";
}

function GamePage() {
  const navigate = useNavigate();
  const { roomCode = "" } = useParams();

  const normalizedRoomCode = roomCode.trim().toUpperCase();
  const playerId = Number(sessionStorage.getItem("player_id"));
  const playerToken = sessionStorage.getItem("player_access_token") ?? "";

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawingRef = useRef(false);
  const lastPointRef = useRef<NormalizedPoint | null>(null);
  const remotePointsRef = useRef<Map<number, NormalizedPoint>>(new Map());
  const remoteStylesRef = useRef<Map<number, StrokeStyle>>(new Map());
  const socketRef = useRef<DrawingGameSocket | null>(null);
  const messageIdRef = useRef(0);

  const [selectedColor, setSelectedColor] = useState("#111827");
  const [brushSize, setBrushSize] = useState(5);
  const [guess, setGuess] = useState("");
  const [players, setPlayers] = useState<LobbyPlayer[]>([]);
  const playersRef = useRef<LobbyPlayer[]>([]);

  // Keep the latest players available without reconnecting the WebSocket.
  playersRef.current = players;

  const [roundNumber, setRoundNumber] = useState(1);
  const [totalRounds, setTotalRounds] = useState(3);
  const [secretWord, setSecretWord] = useState("");
  const [roundStartedAt, setRoundStartedAt] = useState<string | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(ROUND_DURATION_SECONDS);
  const [roundEnded, setRoundEnded] = useState(false);
  const [drawerPlayerId, setDrawerPlayerId] = useState<number | null>(null);

  const [socketStatus, setSocketStatus] =
    useState<WebSocketStatus>("disconnected");

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 1,
      username: "Game",
      text: "Welcome! Connect to the room to start playing.",
      type: "system",
    },
  ]);

  const [errorMessage, setErrorMessage] = useState("");
  const [notice, setNotice] = useState("");

  // Only the player assigned by the backend can draw.
  const isDrawer = drawerPlayerId !== null && drawerPlayerId === playerId;

  useEffect(() => {
    if (!roundStartedAt || roundEnded) {
      return;
    }

    const updateTimer = () => {
      const startTime = new Date(roundStartedAt).getTime();

      if (!Number.isFinite(startTime)) {
        return;
      }

      const elapsed = Math.floor((Date.now() - startTime) / 1000);

      setSecondsLeft(
        Math.max(0, ROUND_DURATION_SECONDS - elapsed),
      );
    };

    updateTimer();

    const timer = window.setInterval(updateTimer, 1000);

    return () => window.clearInterval(timer);
  }, [roundStartedAt, roundEnded]);

  const addMessage = useCallback(
    (
      username: string,
      text: string,
      type: ChatMessage["type"] = "guess",
    ) => {
      messageIdRef.current += 1;

      setMessages((previous) => [
        ...previous,
        {
          id: messageIdRef.current + Date.now(),
          username,
          text,
          type,
        },
      ]);
    },
    [],
  );

  const loadPlayers = useCallback(async () => {
    if (!normalizedRoomCode) {
      return;
    }

    try {
      const response = await apiClient.get<LobbyResponse>(
        `/rooms/${encodeURIComponent(normalizedRoomCode)}/lobby`,
      );

      setPlayers(response.data.players ?? []);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    }
  }, [normalizedRoomCode]);

  const getCanvasPoint = (
    event: PointerEvent<HTMLCanvasElement>,
  ): NormalizedPoint | null => {
    const canvas = canvasRef.current;

    if (!canvas) {
      return null;
    }

    const rect = canvas.getBoundingClientRect();

    if (rect.width === 0 || rect.height === 0) {
      return null;
    }

    return {
      x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    };
  };

  const drawSegment = useCallback(
    (
      from: NormalizedPoint,
      to: NormalizedPoint,
      style: StrokeStyle,
    ) => {
      const canvas = canvasRef.current;
      const context = canvas?.getContext("2d");

      if (!canvas || !context) {
        return;
      }

      context.beginPath();
      context.moveTo(from.x * canvas.width, from.y * canvas.height);
      context.lineTo(to.x * canvas.width, to.y * canvas.height);
      context.strokeStyle = style.color;
      context.lineWidth = style.line_width;
      context.lineCap = "round";
      context.lineJoin = "round";
      context.stroke();
    },
    [],
  );

  const clearLocalCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");

    if (canvas && context) {
      context.clearRect(0, 0, canvas.width, canvas.height);
    }

    remotePointsRef.current.clear();
    remoteStylesRef.current.clear();
  }, []);

  const handleServerEvent = useCallback(
    (event: ServerGameEvent) => {
      const eventType = event.type;

      if (
        typeof event.round_number === "number" &&
        Number.isFinite(event.round_number)
      ) {
        setRoundNumber(event.round_number);
      }

      const possibleDrawerId =
        event.drawer_player_id ??
        event.current_drawer_id ??
        event.drawer_id;

      if (typeof possibleDrawerId === "number") {
        setDrawerPlayerId(possibleDrawerId);
      }

      // The backend sends state_restored with room and current_round nested inside it.
      if (
        eventType === "state_restored" ||
        eventType === "restored_state" ||
        eventType === "game_state" ||
        eventType === "round_started" ||
        eventType === "game_started"
      ) {
        const state = isRecord(event.state) ? event.state : event;
        const room = isRecord(state.room) ? state.room : {};
        const currentRound = isRecord(state.current_round)
          ? state.current_round
          : state;

        const stateDrawerId =
          currentRound.drawer_player_id ??
          state.drawer_player_id ??
          state.current_drawer_id ??
          state.drawer_id;

        if (typeof stateDrawerId === "number") {
          setDrawerPlayerId(stateDrawerId);
        }

        const nextRound = getNumber(
          currentRound.round_number,
          getNumber(
            room.current_round,
            getNumber(state.round_number, 1),
          ),
        );

        setRoundNumber(nextRound);
        setTotalRounds(getNumber(room.total_rounds, 3));
        setRoundEnded(false);
        setRoundStartedAt(getText(currentRound.started_at) || null);
        setSecondsLeft(ROUND_DURATION_SECONDS);

        // Only the assigned drawer should receive the secret word.
        setSecretWord(
          typeof currentRound.word === "string"
            ? currentRound.word
            : "",
        );

        if (Array.isArray(state.players)) {
          const restoredPlayers = state.players
            .filter(isRecord)
            .map((item) => ({
              id: getNumber(item.player_id, getNumber(item.id, -1)),
              display_name: getText(item.display_name, "Player"),
              score: getNumber(item.score, 0),
              is_ready: Boolean(item.is_ready),
            }))
            .filter((item) => item.id > 0);

          setPlayers(restoredPlayers);
        }
      }

      if (eventType === "round_ended") {
        setRoundEnded(true);
        setSecondsLeft(0);
        setSecretWord(getText(event.word));

        addMessage(
          "Game",
          `Round ${getNumber(event.round_number, 1)} has ended.`,
          "system",
        );

        if (Array.isArray(event.scoreboard)) {
          const updated = event.scoreboard
            .filter(isRecord)
            .map((item) => ({
              id: getNumber(item.player_id, -1),
              display_name: getText(item.display_name, "Player"),
              score: getNumber(item.score, 0),
              is_ready: Boolean(item.is_ready),
            }))
            .filter((item) => item.id > 0);

          setPlayers(updated);
        }

        return;
      }

      if (eventType === "game_completed") {
        sessionStorage.setItem(
          "game_results",
          JSON.stringify({
            room_code: normalizedRoomCode,
            total_rounds: getNumber(event.total_rounds, totalRounds),
            scoreboard: Array.isArray(event.scoreboard)
              ? event.scoreboard
              : [],
            winner: event.winner ?? null,
          }),
        );

        navigate(`/results/${encodeURIComponent(normalizedRoomCode)}`);
        return;
      }

      if (
        eventType === "draw_start" ||
        eventType === "draw_move" ||
        eventType === "draw_end"
      ) {
        const sourcePlayerId = getNumber(event.player_id, -1);

        // The local canvas already renders this player's strokes.
        if (sourcePlayerId === playerId) {
          return;
        }

        const rawPoints = Array.isArray(event.points) ? event.points : [];

        const points = rawPoints.filter(
          (point): point is DrawingPoint =>
            isRecord(point) &&
            typeof point.x === "number" &&
            typeof point.y === "number" &&
            Number.isFinite(point.x) &&
            Number.isFinite(point.y),
        );

        const style: StrokeStyle = {
          color: getText(event.color, "#111827"),
          line_width: getNumber(event.line_width, 5),
        };

        if (sourcePlayerId >= 0) {
          remoteStylesRef.current.set(sourcePlayerId, style);
        }

        if (eventType === "draw_start") {
          const firstPoint = points[0];

          if (firstPoint) {
            remotePointsRef.current.set(sourcePlayerId, firstPoint);
          }

          return;
        }

        if (eventType === "draw_move") {
          let previousPoint =
            remotePointsRef.current.get(sourcePlayerId) ?? null;

          for (const point of points) {
            if (previousPoint) {
              drawSegment(
                previousPoint,
                point,
                remoteStylesRef.current.get(sourcePlayerId) ?? style,
              );
            }

            previousPoint = point;
          }

          if (previousPoint) {
            remotePointsRef.current.set(sourcePlayerId, previousPoint);
          }

          return;
        }

        if (eventType === "draw_end") {
          remotePointsRef.current.delete(sourcePlayerId);
          remoteStylesRef.current.delete(sourcePlayerId);
          return;
        }
      }

      if (eventType === "clear_canvas") {
        const sourcePlayerId = getNumber(event.player_id, -1);

        if (sourcePlayerId !== playerId) {
          clearLocalCanvas();
          addMessage("Game", "The drawing canvas was cleared.", "system");
        }

        return;
      }

      if (eventType === "guess") {
        const sourcePlayerId = getNumber(event.player_id, -1);
        const text = getText(event.guess);

        if (text) {
          const sender =
            playersRef.current.find(
              (player) => player.id === sourcePlayerId,
            )?.display_name ?? "Player";

          addMessage(sender, text);
        }

        return;
      }

      if (eventType === "correct_guess") {
        const sourcePlayerId = getNumber(event.player_id, -1);

        const correctPlayerName = getText(
          event.display_name,
          playersRef.current.find(
            (player) => player.id === sourcePlayerId,
          )?.display_name ?? "A player",
        );

        const points = getNumber(
          event.points_awarded,
          getNumber(event.points, 0),
        );

        addMessage(
          "Game",
          `${correctPlayerName} guessed correctly${
            points > 0 ? ` and earned ${points} points` : ""
          }!`,
          "correct",
        );

        if (Array.isArray(event.scoreboard)) {
          const updated = event.scoreboard
            .filter(isRecord)
            .map((item) => ({
              id: getNumber(item.player_id, -1),
              display_name: getText(item.display_name, "Player"),
              score: getNumber(item.score, 0),
              is_ready: Boolean(item.is_ready),
            }))
            .filter((item) => item.id > 0);

          setPlayers(updated);
        } else {
          void loadPlayers();
        }

        return;
      }

      if (
        eventType === "player_joined" ||
        eventType === "player_left" ||
        eventType === "player_ready_changed" ||
        eventType === "player_presence"
      ) {
        void loadPlayers();
        return;
      }

      if (eventType === "error") {
        setNotice(
          getText(event.message, "The server reported a game error."),
        );
        return;
      }

      if (eventType === "connected") {
        setNotice("Connected to the game server.");
        void loadPlayers();
      }
    },
    [
      addMessage,
      clearLocalCanvas,
      drawSegment,
      loadPlayers,
      navigate,
      normalizedRoomCode,
      playerId,
      totalRounds,
    ],
  );

  useEffect(() => {
    if (
      !normalizedRoomCode ||
      !Number.isInteger(playerId) ||
      playerId <= 0 ||
      !playerToken
    ) {
      setErrorMessage(
        "Player credentials were not found. Please join the room from the home page first.",
      );
      return;
    }

    const socket = new DrawingGameSocket({
      roomCode: normalizedRoomCode,
      playerId,
      token: playerToken,
    });

    socketRef.current = socket;

    const unsubscribeEvents = socket.onEvent(handleServerEvent);
    const unsubscribeStatus = socket.onStatusChange(setSocketStatus);

    try {
      socket.connect();
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    }

    // Load the lobby once when entering the game.
    void loadPlayers();

    return () => {
      unsubscribeEvents();
      unsubscribeStatus();
      socket.disconnect();

      if (socketRef.current === socket) {
        socketRef.current = null;
      }
    };
  }, [
    handleServerEvent,
    loadPlayers,
    normalizedRoomCode,
    playerId,
    playerToken,
  ]);

  const startDrawing = (event: PointerEvent<HTMLCanvasElement>) => {
    if (
      !isDrawer ||
      socketStatus !== "connected" ||
      roundEnded
    ) {
      return;
    }

    const canvas = canvasRef.current;
    const point = getCanvasPoint(event);

    if (!canvas || !point) {
      return;
    }

    event.preventDefault();
    canvas.setPointerCapture(event.pointerId);

    drawingRef.current = true;
    lastPointRef.current = point;

    socketRef.current?.send({
      type: "draw_start",
      round_number: roundNumber,
      color: selectedColor,
      line_width: brushSize,
      points: [point],
    });
  };

  const draw = (event: PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current || !isDrawer || roundEnded) {
      return;
    }

    event.preventDefault();

    const point = getCanvasPoint(event);
    const lastPoint = lastPointRef.current;

    if (!point || !lastPoint) {
      return;
    }

    drawSegment(lastPoint, point, {
      color: selectedColor,
      line_width: brushSize,
    });

    socketRef.current?.send({
      type: "draw_move",
      round_number: roundNumber,
      color: selectedColor,
      line_width: brushSize,
      points: [point],
    });

    lastPointRef.current = point;
  };

  const stopDrawing = () => {
    if (!drawingRef.current) {
      return;
    }

    drawingRef.current = false;
    lastPointRef.current = null;

    socketRef.current?.send({
      type: "draw_end",
      round_number: roundNumber,
      color: selectedColor,
      line_width: brushSize,
      points: [],
    });
  };

  const clearCanvas = () => {
    if (!isDrawer || roundEnded) {
      setNotice("Only the current drawer can clear the canvas.");
      return;
    }

    clearLocalCanvas();

    const sent = socketRef.current?.send({
      type: "clear_canvas",
      round_number: roundNumber,
      color: selectedColor,
      line_width: brushSize,
      points: [],
    });

    if (!sent) {
      setNotice("Canvas cleared locally, but the server is disconnected.");
    } else {
      setNotice("Canvas cleared.");
    }
  };

  const submitGuess = () => {
    const cleanGuess = guess.trim();

    if (
      !cleanGuess ||
      socketStatus !== "connected" ||
      isDrawer ||
      roundEnded
    ) {
      return;
    }

    const sent = socketRef.current?.send({
      type: "guess",
      round_number: roundNumber,
      guess: cleanGuess,
    });

    if (!sent) {
      setErrorMessage("Your guess could not be sent. Check the connection.");
      return;
    }

    addMessage("You", cleanGuess);
    setGuess("");
    setErrorMessage("");
  };

  const connectionLabel: Record<WebSocketStatus, string> = {
    connecting: "Connecting…",
    connected: "Live connection",
    disconnected: "Disconnected",
    error: "Connection error",
  };

  const connectionColor: Record<
    WebSocketStatus,
    "success" | "warning" | "error" | "default"
  > = {
    connecting: "warning",
    connected: "success",
    disconnected: "default",
    error: "error",
  };

  const sortedPlayers = [...players].sort(
    (first, second) => second.score - first.score,
  );

  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "#0b1020",
        color: "#ffffff",
        py: 3,
        px: { xs: 1.5, md: 3 },
      }}
    >
      <Container maxWidth="xl">
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          gap={2}
          sx={{ mb: 3, flexWrap: "wrap" }}
        >
          <Stack direction="row" alignItems="center" spacing={1.5}>
            <IconButton
              aria-label="Back to lobby"
              onClick={() =>
                navigate(`/lobby/${encodeURIComponent(normalizedRoomCode)}`)
              }
              sx={{ color: "#ffffff" }}
            >
              <ArrowBackRoundedIcon />
            </IconButton>

            <Box>
              <Typography sx={{ fontWeight: 900, fontSize: "1.3rem" }}>
                DrawTogether
              </Typography>
              <Typography variant="caption" sx={{ color: "#8993ab" }}>
                Room: {normalizedRoomCode}
              </Typography>
            </Box>
          </Stack>

          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            flexWrap="wrap"
            useFlexGap
          >
            <Chip
              label={`Round ${roundNumber} / ${totalRounds}`}
              sx={{
                bgcolor: "rgba(139,124,255,0.15)",
                color: "#c6beff",
                fontWeight: 700,
              }}
            />
            <Chip
              label={`${secondsLeft}s`}
              color={secondsLeft <= 10 ? "error" : "default"}
              variant="outlined"
            />
            <Chip
              label={connectionLabel[socketStatus]}
              color={connectionColor[socketStatus]}
              variant="outlined"
            />
          </Stack>
        </Stack>

        {errorMessage && (
          <Alert
            severity="error"
            onClose={() => setErrorMessage("")}
            sx={{ mb: 2 }}
          >
            {errorMessage}
          </Alert>
        )}

        {notice && (
          <Alert
            severity="info"
            onClose={() => setNotice("")}
            sx={{ mb: 2 }}
          >
            {notice}
          </Alert>
        )}

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: {
              xs: "1fr",
              lg: "minmax(0, 1fr) 320px",
            },
            gap: 3,
            alignItems: "start",
          }}
        >
          <Box>
            <Paper
              elevation={0}
              sx={{
                bgcolor: "#151b2e",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: 4,
                p: { xs: 2, md: 3 },
                mb: 3,
              }}
            >
              <Stack
                direction={{ xs: "column", sm: "row" }}
                alignItems={{ xs: "flex-start", sm: "center" }}
                justifyContent="space-between"
                gap={2}
                sx={{ mb: 2.5 }}
              >
                <Box>
                  <Typography
                    variant="overline"
                    sx={{ color: "#a99cff", fontWeight: 800 }}
                  >
                    {isDrawer ? "YOUR TURN TO DRAW" : "GUESS THE WORD"}
                  </Typography>

                  <Typography variant="h5" sx={{ fontWeight: 900 }}>
                    {isDrawer
                      ? secretWord
                        ? `Your word: ${secretWord}`
                        : "Waiting for your word…"
                      : "Guess the word"}
                  </Typography>
                </Box>

                <Chip
                  label={
                    socketStatus === "connected"
                      ? "Multiplayer enabled"
                      : "Waiting for connection"
                  }
                  sx={{
                    bgcolor: "rgba(113,223,186,0.12)",
                    color: "#71dfba",
                    fontWeight: 700,
                  }}
                />
              </Stack>

              {!isDrawer && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  Guess the word before the timer ends.
                </Alert>
              )}

              {isDrawer && !secretWord && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  Waiting for the server to send your secret word.
                </Alert>
              )}

              {roundEnded && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  This round has ended. Waiting for the next round or final results.
                </Alert>
              )}

              <Box
                sx={{
                  width: "100%",
                  bgcolor: "#ffffff",
                  borderRadius: 3,
                  overflow: "hidden",
                  lineHeight: 0,
                  touchAction: "none",
                }}
              >
                <canvas
                  ref={canvasRef}
                  width={CANVAS_WIDTH}
                  height={CANVAS_HEIGHT}
                  onPointerDown={startDrawing}
                  onPointerMove={draw}
                  onPointerUp={stopDrawing}
                  onPointerCancel={stopDrawing}
                  onPointerLeave={stopDrawing}
                  aria-label="Multiplayer drawing canvas"
                  style={{
                    display: "block",
                    width: "100%",
                    height: "auto",
                    aspectRatio: "5 / 3",
                    cursor: isDrawer && !roundEnded ? "crosshair" : "default",
                    touchAction: "none",
                  }}
                />
              </Box>

              <Divider
                sx={{ borderColor: "rgba(255,255,255,0.1)", my: 2.5 }}
              />

              <Stack
                direction={{ xs: "column", sm: "row" }}
                spacing={3}
                alignItems={{ xs: "stretch", sm: "center" }}
              >
                <Box sx={{ flex: 1 }}>
                  <Stack
                    direction="row"
                    alignItems="center"
                    spacing={1}
                    sx={{ mb: 1.5 }}
                  >
                    <PaletteRoundedIcon sx={{ color: "#a99cff" }} />
                    <Typography sx={{ fontWeight: 700 }}>Colors</Typography>
                  </Stack>

                  <Stack
                    direction="row"
                    spacing={1}
                    flexWrap="wrap"
                    useFlexGap
                  >
                    {COLORS.map((color) => (
                      <Box
                        key={color}
                        component="button"
                        type="button"
                        aria-label={`Select color ${color}`}
                        disabled={!isDrawer || roundEnded}
                        onClick={() => setSelectedColor(color)}
                        sx={{
                          width: 30,
                          height: 30,
                          p: 0,
                          borderRadius: "50%",
                          cursor: isDrawer ? "pointer" : "not-allowed",
                          bgcolor: color,
                          border:
                            selectedColor === color
                              ? "3px solid #a99cff"
                              : "2px solid rgba(255,255,255,0.25)",
                          outline: "none",
                        }}
                      />
                    ))}
                  </Stack>
                </Box>

                <Box sx={{ width: { xs: "100%", sm: 180 } }}>
                  <Stack
                    direction="row"
                    alignItems="center"
                    spacing={1}
                    sx={{ mb: 0.5 }}
                  >
                    <BrushRoundedIcon sx={{ color: "#a99cff" }} />
                    <Typography sx={{ fontWeight: 700 }}>
                      Brush: {brushSize}px
                    </Typography>
                  </Stack>

                  <Slider
                    min={2}
                    max={24}
                    value={brushSize}
                    disabled={!isDrawer || roundEnded}
                    onChange={(_, value) => {
                      if (typeof value === "number") {
                        setBrushSize(value);
                      }
                    }}
                    aria-label="Brush size"
                    sx={{ color: "#8b7cff" }}
                  />
                </Box>

                <Button
                  variant="outlined"
                  startIcon={<DeleteOutlineRoundedIcon />}
                  onClick={clearCanvas}
                  disabled={!isDrawer || roundEnded}
                  sx={{
                    color: "#ff9b9b",
                    borderColor: "rgba(255,155,155,0.4)",
                    textTransform: "none",
                    "&:hover": {
                      borderColor: "#ff9b9b",
                      bgcolor: "rgba(255,155,155,0.08)",
                    },
                  }}
                >
                  Clear
                </Button>
              </Stack>
            </Paper>

            <Paper
              elevation={0}
              sx={{
                bgcolor: "#151b2e",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: 4,
                p: 3,
              }}
            >
              <Stack
                direction="row"
                alignItems="center"
                spacing={1.5}
                sx={{ mb: 2 }}
              >
                <EmojiEventsRoundedIcon
                  sx={{ color: "#f5c76b", fontSize: 28 }}
                />
                <Typography variant="h6" sx={{ fontWeight: 800 }}>
                  Players & Scores
                </Typography>
              </Stack>

              {sortedPlayers.length === 0 ? (
                <Typography variant="body2" sx={{ color: "#8993ab" }}>
                  Waiting for player information…
                </Typography>
              ) : (
                <Stack
                  direction={{ xs: "column", sm: "row" }}
                  spacing={2}
                  flexWrap="wrap"
                >
                  {sortedPlayers.map((player, index) => (
                    <Box
                      key={player.id}
                      sx={{
                        flex: "1 1 180px",
                        display: "flex",
                        alignItems: "center",
                        gap: 1.5,
                        p: 1.5,
                        borderRadius: 3,
                        bgcolor: "rgba(255,255,255,0.035)",
                      }}
                    >
                      <Avatar
                        sx={{
                          bgcolor:
                            player.id === playerId ? "#7563f0" : "#159c83",
                        }}
                      >
                        {player.display_name.charAt(0).toUpperCase()}
                      </Avatar>

                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography sx={{ fontWeight: 700 }}>
                          {index + 1}. {player.display_name}
                          {player.id === playerId ? " (You)" : ""}
                        </Typography>

                        <Typography
                          variant="body2"
                          sx={{ color: "#a6aec3" }}
                        >
                          {player.score} points
                        </Typography>

                        {player.id === drawerPlayerId && (
                          <Chip
                            size="small"
                            label="Drawing"
                            sx={{
                              mt: 0.5,
                              bgcolor: "rgba(113,223,186,0.12)",
                              color: "#71dfba",
                            }}
                          />
                        )}
                      </Box>
                    </Box>
                  ))}
                </Stack>
              )}
            </Paper>
          </Box>

          <Paper
            elevation={0}
            sx={{
              bgcolor: "#151b2e",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 4,
              display: "flex",
              flexDirection: "column",
              minHeight: { xs: 420, lg: 700 },
              maxHeight: { lg: 820 },
              overflow: "hidden",
            }}
          >
            <Box sx={{ p: 2.5 }}>
              <Typography variant="h6" sx={{ fontWeight: 800 }}>
                Guesses & Chat
              </Typography>

              <Typography
                variant="body2"
                sx={{ color: "#8993ab", mt: 0.5 }}
              >
                Send your guess to the other players.
              </Typography>
            </Box>

            <Divider sx={{ borderColor: "rgba(255,255,255,0.1)" }} />

            <Stack
              spacing={2}
              sx={{
                p: 2,
                flex: 1,
                overflowY: "auto",
                minHeight: 240,
              }}
            >
              {messages.map((message) => (
                <Box
                  key={message.id}
                  sx={{
                    alignSelf:
                      message.username === "You" ? "flex-end" : "stretch",
                    maxWidth: "100%",
                    p: 1.5,
                    borderRadius: 3,
                    bgcolor:
                      message.type === "system"
                        ? "rgba(139,124,255,0.12)"
                        : message.type === "correct"
                          ? "rgba(113,223,186,0.12)"
                          : "rgba(255,255,255,0.045)",
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      display: "block",
                      mb: 0.5,
                      color:
                        message.type === "system"
                          ? "#b7aaff"
                          : message.type === "correct"
                            ? "#71dfba"
                            : "#a6aec3",
                      fontWeight: 700,
                    }}
                  >
                    {message.username}
                  </Typography>

                  <Typography sx={{ overflowWrap: "anywhere" }}>
                    {message.text}
                  </Typography>
                </Box>
              ))}
            </Stack>

            <Divider sx={{ borderColor: "rgba(255,255,255,0.1)" }} />

            <Box
              component="form"
              onSubmit={(event) => {
                event.preventDefault();
                submitGuess();
              }}
              sx={{ p: 2, display: "flex", gap: 1 }}
            >
              <TextField
                value={guess}
                onChange={(event) => setGuess(event.target.value)}
                placeholder="Type your guess..."
                size="small"
                fullWidth
                disabled={
                  socketStatus !== "connected" ||
                  isDrawer ||
                  roundEnded
                }
                slotProps={{
                  htmlInput: { maxLength: 100 },
                }}
                sx={{
                  "& .MuiOutlinedInput-root": {
                    color: "#ffffff",
                    borderRadius: 3,
                    "& fieldset": {
                      borderColor: "rgba(255,255,255,0.15)",
                    },
                  },
                }}
              />

              <IconButton
                type="submit"
                aria-label="Send guess"
                disabled={
                  !guess.trim() ||
                  socketStatus !== "connected" ||
                  isDrawer ||
                  roundEnded
                }
                sx={{
                  bgcolor: "#8b7cff",
                  color: "#ffffff",
                  borderRadius: 3,
                  "&:hover": { bgcolor: "#7563f0" },
                  "&.Mui-disabled": {
                    bgcolor: "rgba(139,124,255,0.2)",
                    color: "#626b80",
                  },
                }}
              >
                <SendRoundedIcon />
              </IconButton>
            </Box>

            {isDrawer && (
              <Typography
                variant="caption"
                sx={{ color: "#8993ab", px: 2, pb: 2 }}
              >
                You are the current drawer. Guesses are disabled for you.
              </Typography>
            )}
          </Paper>
        </Box>
      </Container>
    </Box>
  );
}

export default GamePage;
