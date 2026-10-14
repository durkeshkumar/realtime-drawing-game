import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Divider,
  IconButton,
  Paper,
  Stack,
  Typography,
} from "@mui/material";

import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import ContentCopyRoundedIcon from "@mui/icons-material/ContentCopyRounded";
import GroupsRoundedIcon from "@mui/icons-material/GroupsRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import SportsEsportsRoundedIcon from "@mui/icons-material/SportsEsportsRounded";
import { useNavigate, useParams } from "react-router-dom";

import apiClient from "../../api/client";
import { DrawingGameSocket } from "../../api/websocket";
import type {
  ServerGameEvent,
  WebSocketStatus,
} from "../../api/websocket";

interface LobbyPlayer {
  id: number;
  room_id: number;
  display_name: string;
  score: number;
  joined_at: string;
  left_at: string | null;
  is_ready: boolean;
}

interface LobbyResponse {
  room_code: string;
  status: string;
  player_count: number;
  max_players: number;
  players: LobbyPlayer[];
}

function getApiErrorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "response" in error) {
    const response = (
      error as {
        response?: {
          data?: {
            detail?: string | Array<{ msg?: string }>;
          };
        };
      }
    ).response;

    const detail = response?.data?.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg ?? "Invalid input").join(", ");
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Something went wrong. Please try again.";
}

function LobbyPage() {
  const navigate = useNavigate();
  const { roomCode = "" } = useParams();

  const normalizedRoomCode = roomCode.trim().toUpperCase();
  const playerId = Number(sessionStorage.getItem("player_id"));
  const playerToken = sessionStorage.getItem("player_access_token");

  const [lobby, setLobby] = useState<LobbyResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdatingReady, setIsUpdatingReady] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [copyMessage, setCopyMessage] = useState("");
  const [socketStatus, setSocketStatus] =
    useState<WebSocketStatus>("disconnected");

  const currentPlayer = lobby?.players.find(
    (player) => player.id === playerId,
  );

  const isReady = currentPlayer?.is_ready ?? false;

  const loadLobby = useCallback(
    async (showLoading = false) => {
      if (!normalizedRoomCode) {
        setErrorMessage("A room code is required.");
        setIsLoading(false);
        return;
      }

      if (showLoading) {
        setIsLoading(true);
      }

      try {
        const response = await apiClient.get<LobbyResponse>(
          `/rooms/${encodeURIComponent(normalizedRoomCode)}/lobby`,
        );

        setLobby(response.data);
        setErrorMessage("");
      } catch (error: unknown) {
        setErrorMessage(getApiErrorMessage(error));
      } finally {
        setIsLoading(false);
      }
    },
    [normalizedRoomCode],
  );

  useEffect(() => {
    void loadLobby(true);

    if (
      !playerToken ||
      !Number.isInteger(playerId) ||
      playerId <= 0 ||
      !normalizedRoomCode
    ) {
      setSocketStatus("disconnected");
      return;
    }

    const socket = new DrawingGameSocket({
      roomCode: normalizedRoomCode,
      playerId,
      token: playerToken,
    });

    const unsubscribeStatus = socket.onStatusChange((status) => {
      setSocketStatus(status);
    });

    const unsubscribeEvents = socket.onEvent(
      (event: ServerGameEvent) => {
        if (
          event.type === "player_joined" ||
          event.type === "player_ready_changed" ||
          event.type === "player_left" ||
          event.type === "player_presence"
        ) {
          void loadLobby();
        }
      },
    );

    try {
      socket.connect();
    } catch {
      setSocketStatus("error");
    }

    // Load once when opening the lobby.
    // Subsequent lobby updates come from WebSocket events.
    return () => {
      unsubscribeEvents();
      unsubscribeStatus();
      socket.disconnect();
    };
  }, [loadLobby, normalizedRoomCode, playerId, playerToken]);

  const handleCopyRoomCode = async () => {
    try {
      await navigator.clipboard.writeText(normalizedRoomCode);
      setCopyMessage("Room code copied!");

      window.setTimeout(() => {
        setCopyMessage("");
      }, 2000);
    } catch {
      setCopyMessage("Unable to copy. Please copy the room code manually.");
    }
  };

  const handleToggleReady = async () => {
    if (!playerToken || !Number.isInteger(playerId) || playerId <= 0) {
      setActionError(
        "Your player session is missing. Please return home and join the room again.",
      );
      return;
    }

    setIsUpdatingReady(true);
    setActionError("");

    try {
      const response = await apiClient.patch<LobbyPlayer>(
        `/rooms/${encodeURIComponent(normalizedRoomCode)}/players/${playerId}/ready`,
        { is_ready: !isReady },
      );

      setLobby((previous) => {
        if (!previous) {
          return previous;
        }

        return {
          ...previous,
          players: previous.players.map((player) =>
            player.id === response.data.id ? response.data : player,
          ),
        };
      });
    } catch (error: unknown) {
      setActionError(getApiErrorMessage(error));
    } finally {
      setIsUpdatingReady(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "#0b1020",
        color: "#ffffff",
        py: 5,
        px: 2,
      }}
    >
      <Container maxWidth="md">
        <Button
          startIcon={<ArrowBackRoundedIcon />}
          onClick={() => navigate("/")}
          sx={{ color: "#a6aec3", mb: 4, textTransform: "none" }}
        >
          Back to Home
        </Button>

        <Box sx={{ textAlign: "center", mb: 5 }}>
          <GroupsRoundedIcon
            sx={{ fontSize: 48, color: "#9a8cff", mb: 1 }}
          />

          <Typography
            component="h1"
            sx={{
              fontSize: { xs: "2rem", sm: "2.8rem" },
              fontWeight: 900,
              mb: 1,
            }}
          >
            Game Lobby
          </Typography>

          <Typography sx={{ color: "#a6aec3" }}>
            Invite your friends and get ready to draw!
          </Typography>

          <Chip
            size="small"
            label={
              socketStatus === "connected"
                ? "Live updates connected"
                : socketStatus === "connecting"
                  ? "Connecting to live updates…"
                  : socketStatus === "error"
                    ? "Live updates unavailable"
                    : "Live updates disconnected"
            }
            sx={{
              mt: 2,
              bgcolor:
                socketStatus === "connected"
                  ? "rgba(73,205,153,0.12)"
                  : "rgba(255,255,255,0.06)",
              color:
                socketStatus === "connected" ? "#71dfba" : "#a6aec3",
            }}
          />
        </Box>

        {errorMessage && (
          <Alert
            severity="error"
            sx={{ mb: 3 }}
            action={
              <Button
                color="inherit"
                size="small"
                onClick={() => void loadLobby(true)}
              >
                Retry
              </Button>
            }
          >
            {errorMessage}
          </Alert>
        )}

        {actionError && (
          <Alert
            severity="error"
            onClose={() => setActionError("")}
            sx={{ mb: 3 }}
          >
            {actionError}
          </Alert>
        )}

        {!isLoading && lobby && !currentPlayer && (
          <Alert severity="warning" sx={{ mb: 3 }}>
            Your player is not in this room's active lobby. Return home and
            join the room again if your session has expired or you left.
          </Alert>
        )}

        <Paper
          elevation={0}
          sx={{
            p: { xs: 2.5, sm: 4 },
            bgcolor: "#151b2e",
            color: "#ffffff",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 4,
            mb: 3,
          }}
        >
          <Typography
            variant="body2"
            sx={{ color: "#a6aec3", mb: 1, textAlign: "center" }}
          >
            ROOM CODE
          </Typography>

          <Stack
            direction="row"
            justifyContent="center"
            alignItems="center"
            spacing={1}
          >
            <Typography
              sx={{
                color: "#b7aaff",
                fontSize: { xs: "1.8rem", sm: "2.5rem" },
                fontWeight: 900,
                letterSpacing: 5,
                overflowWrap: "anywhere",
              }}
            >
              {lobby?.room_code ?? normalizedRoomCode}
            </Typography>

            <IconButton
              onClick={() => void handleCopyRoomCode()}
              aria-label="Copy room code"
              sx={{ color: "#b7aaff" }}
            >
              <ContentCopyRoundedIcon />
            </IconButton>
          </Stack>

          {copyMessage && (
            <Typography
              variant="caption"
              sx={{
                display: "block",
                textAlign: "center",
                color: "#71dfba",
              }}
            >
              {copyMessage}
            </Typography>
          )}

          <Typography
            variant="caption"
            sx={{
              display: "block",
              color: "#8993ab",
              textAlign: "center",
              mt: 1,
            }}
          >
            Share this code with your friends to invite them.
          </Typography>
        </Paper>

        <Paper
          elevation={0}
          sx={{
            p: { xs: 2.5, sm: 4 },
            bgcolor: "#151b2e",
            color: "#ffffff",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 4,
          }}
        >
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            sx={{ mb: 2 }}
          >
            <Typography variant="h6" sx={{ fontWeight: 800 }}>
              Players
            </Typography>

            <Chip
              label={`${lobby?.player_count ?? 0} / ${lobby?.max_players ?? 8}`}
              sx={{
                bgcolor: "rgba(139,124,255,0.15)",
                color: "#c6beff",
                fontWeight: 700,
              }}
            />
          </Stack>

          <Divider sx={{ borderColor: "rgba(255,255,255,0.1)", mb: 2 }} />

          {isLoading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 5 }}>
              <CircularProgress sx={{ color: "#9a8cff" }} />
            </Box>
          ) : (
            <Stack spacing={2}>
              {(lobby?.players ?? []).map((player) => {
                const isCurrentPlayer = player.id === playerId;

                return (
                  <Box
                    key={player.id}
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 2,
                      p: 2,
                      borderRadius: 3,
                      bgcolor: "rgba(255,255,255,0.035)",
                    }}
                  >
                    <Avatar
                      sx={{
                        bgcolor: isCurrentPlayer ? "#7563f0" : "#27324a",
                        fontWeight: 700,
                      }}
                    >
                      {player.display_name.charAt(0).toUpperCase()}
                    </Avatar>

                    <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                      <Typography
                        sx={{ fontWeight: 700, overflowWrap: "anywhere" }}
                      >
                        {player.display_name}
                        {isCurrentPlayer ? " (You)" : ""}
                      </Typography>

                      <Typography variant="caption" sx={{ color: "#8993ab" }}>
                        Score: {player.score}
                      </Typography>
                    </Box>

                    <Chip
                      size="small"
                      icon={
                        player.is_ready ? (
                          <CheckCircleRoundedIcon />
                        ) : undefined
                      }
                      label={player.is_ready ? "Ready" : "Not ready"}
                      sx={{
                        bgcolor: player.is_ready
                          ? "rgba(73,205,153,0.12)"
                          : "rgba(255,255,255,0.06)",
                        color: player.is_ready ? "#71dfba" : "#a6aec3",
                        "& .MuiChip-icon": { color: "#71dfba" },
                      }}
                    />
                  </Box>
                );
              })}

              {lobby && lobby.players.length === 0 && (
                <Typography
                  sx={{ color: "#8993ab", textAlign: "center", py: 3 }}
                >
                  No active players found in this room.
                </Typography>
              )}
            </Stack>
          )}

          <Divider sx={{ borderColor: "rgba(255,255,255,0.1)", my: 3 }} />

          <Stack spacing={2}>
            <Button
              fullWidth
              size="large"
              variant={isReady ? "outlined" : "contained"}
              disabled={
                isLoading ||
                isUpdatingReady ||
                !currentPlayer ||
                !playerToken
              }
              onClick={() => void handleToggleReady()}
              sx={{
                py: 1.5,
                borderRadius: 3,
                fontWeight: 800,
                textTransform: "none",
                bgcolor: isReady ? "transparent" : "#8b7cff",
                color: "#ffffff",
                borderColor: "#8b7cff",
                "&:hover": {
                  bgcolor: isReady
                    ? "rgba(139,124,255,0.08)"
                    : "#7563f0",
                },
              }}
            >
              {isUpdatingReady ? (
                <CircularProgress size={22} color="inherit" />
              ) : isReady ? (
                "I'm Not Ready"
              ) : (
                "I'm Ready"
              )}
            </Button>

            <Button
              fullWidth
              size="large"
              variant="outlined"
              startIcon={<SportsEsportsRoundedIcon />}
              disabled={!isReady || !currentPlayer}
              onClick={() =>
                navigate(`/game/${encodeURIComponent(normalizedRoomCode)}`)
              }
              sx={{
                py: 1.5,
                borderRadius: 3,
                borderColor: "rgba(255,255,255,0.2)",
                color: "#ffffff",
                fontWeight: 800,
                textTransform: "none",
                "&:hover": { borderColor: "#8b7cff" },
                "&.Mui-disabled": {
                  color: "#626b80",
                  borderColor: "rgba(255,255,255,0.08)",
                },
              }}
            >
              Start Game
            </Button>
          </Stack>

          <Typography
            variant="caption"
            sx={{
              display: "block",
              textAlign: "center",
              color: "#8993ab",
              mt: 2,
            }}
          >
            Lobby changes update through WebSocket events. Use Retry if the
            lobby cannot be loaded.
          </Typography>
        </Paper>
      </Container>
    </Box>
  );
}

export default LobbyPage;