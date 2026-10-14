
import { useState } from "react";
import {
  Alert,
  AppBar,
  Box,
  Button,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
  Toolbar,
  Typography,
} from "@mui/material";
import SportsEsportsRoundedIcon from "@mui/icons-material/SportsEsportsRounded";
import DrawRoundedIcon from "@mui/icons-material/DrawRounded";
import GroupsRoundedIcon from "@mui/icons-material/GroupsRounded";
import EmojiObjectsRoundedIcon from "@mui/icons-material/EmojiObjectsRounded";
import {
  BrowserRouter,
  Routes,
  Route,
  useNavigate,
} from "react-router-dom";

import PlaceholderPage from "./pages/PlaceholderPage";
import LobbyPage from "./features/lobby/LobbyPage";
import GamePage from "./features/game/GamePage";
import { joinRoom } from "./api/auth";
import apiClient from "./api/client";

interface CreateRoomResponse {
  room_code: string;
  total_rounds: number;
  current_round: number;
  status: string;
}

function getApiErrorMessage(error: unknown): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error
  ) {
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
      return detail
        .map((item) => item.msg ?? "Invalid input")
        .join(", ");
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Something went wrong. Please try again.";
}

function HomePage() {
  const navigate = useNavigate();

  const [joinDialogOpen, setJoinDialogOpen] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  const [username, setUsername] = useState("");
  const [roomCode, setRoomCode] = useState("");
  const [createUsername, setCreateUsername] = useState("");
  const [totalRounds, setTotalRounds] = useState(3);

  const [errorMessage, setErrorMessage] = useState("");
  const [isJoining, setIsJoining] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const openJoinDialog = () => {
    setErrorMessage("");
    setJoinDialogOpen(true);
  };

  const closeJoinDialog = () => {
    if (isJoining) return;

    setJoinDialogOpen(false);
    setErrorMessage("");
  };

  const openCreateDialog = () => {
    setErrorMessage("");
    setCreateDialogOpen(true);
  };

  const closeCreateDialog = () => {
    if (isCreating) return;

    setCreateDialogOpen(false);
    setErrorMessage("");
  };

  const handleJoinRoom = async () => {
    const cleanUsername = username.trim();
    const cleanRoomCode = roomCode.trim().toUpperCase();

    if (!cleanUsername || !cleanRoomCode) {
      setErrorMessage("Enter your player name and room code.");
      return;
    }

    setIsJoining(true);
    setErrorMessage("");

    try {
      await joinRoom(cleanRoomCode, {
        display_name: cleanUsername,
      });

      setJoinDialogOpen(false);
      navigate(`/lobby/${encodeURIComponent(cleanRoomCode)}`);
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsJoining(false);
    }
  };

  const handleCreateRoom = async () => {
    const cleanUsername = createUsername.trim();

    if (!cleanUsername) {
      setErrorMessage("Enter your player name.");
      return;
    }

    setIsCreating(true);
    setErrorMessage("");

    try {
      // Create a room using the actual backend endpoint.
      const response = await apiClient.post<CreateRoomResponse>(
        "/rooms",
        {
          total_rounds: totalRounds,
        },
      );

      const newRoomCode = response.data.room_code
        ?.trim()
        .toUpperCase();

      if (!newRoomCode) {
        throw new Error(
          "The room was created, but the server did not return a room code.",
        );
      }

      // Register the creator as the first player in the room.
      await joinRoom(newRoomCode, {
        display_name: cleanUsername,
      });

      setCreateDialogOpen(false);

      // Show the room code in the lobby so friends can join.
      navigate(`/lobby/${encodeURIComponent(newRoomCode)}`);
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "#0b1020",
        color: "#ffffff",
        overflow: "hidden",
      }}
    >
      <AppBar
        position="static"
        elevation={0}
        sx={{
          bgcolor: "transparent",
          borderBottom: "1px solid rgba(255,255,255,0.1)",
        }}
      >
        <Container maxWidth="lg">
          <Toolbar disableGutters sx={{ minHeight: 76 }}>
            <SportsEsportsRoundedIcon
              sx={{ color: "#8b7cff", fontSize: 34, mr: 1.5 }}
            />

            <Typography
              variant="h6"
              sx={{ fontWeight: 800, letterSpacing: "-0.5px" }}
            >
              Draw<span style={{ color: "#8b7cff" }}>Together</span>
            </Typography>

            <Box sx={{ flexGrow: 1 }} />

            <Button
              variant="outlined"
              onClick={openJoinDialog}
              sx={{
                color: "#ffffff",
                borderColor: "rgba(255,255,255,0.3)",
                borderRadius: 3,
                px: 2.5,
                "&:hover": {
                  borderColor: "#8b7cff",
                  bgcolor: "rgba(139,124,255,0.1)",
                },
              }}
            >
              Join a Game
            </Button>
          </Toolbar>
        </Container>
      </AppBar>

      <Container maxWidth="lg">
        <Box
          sx={{
            minHeight: { xs: "auto", md: "75vh" },
            py: { xs: 8, md: 12 },
            display: "flex",
            alignItems: "center",
          }}
        >
          <Box sx={{ maxWidth: 760 }}>
            <Box
              sx={{
                display: "inline-flex",
                alignItems: "center",
                gap: 1,
                px: 2,
                py: 1,
                mb: 3,
                borderRadius: 10,
                bgcolor: "rgba(139,124,255,0.12)",
                border: "1px solid rgba(139,124,255,0.3)",
              }}
            >
              <DrawRoundedIcon sx={{ color: "#a99cff", fontSize: 20 }} />
              <Typography
                variant="body2"
                sx={{ color: "#c6beff", fontWeight: 600 }}
              >
                Draw • Guess • Compete
              </Typography>
            </Box>

            <Typography
              component="h1"
              sx={{
                fontSize: { xs: "3rem", md: "5.5rem" },
                fontWeight: 900,
                lineHeight: 1.05,
                letterSpacing: "-3px",
                mb: 3,
              }}
            >
              Draw it.
              <br />
              Guess it.
              <br />
              <Box component="span" sx={{ color: "#9a8cff" }}>
                Win together.
              </Box>
            </Typography>

            <Typography
              sx={{
                color: "#a6aec3",
                fontSize: { xs: "1rem", md: "1.2rem" },
                lineHeight: 1.8,
                maxWidth: 620,
                mb: 4,
              }}
            >
              Challenge your friends in a real-time drawing and guessing game.
              Take turns drawing secret words, guess before time runs out, and
              compete for the highest score.
            </Typography>

            <Stack
              direction={{ xs: "column", sm: "row" }}
              spacing={2}
              sx={{ mb: 7 }}
            >
              <Button
                variant="contained"
                size="large"
                startIcon={<DrawRoundedIcon />}
                onClick={openCreateDialog}
                sx={{
                  bgcolor: "#8b7cff",
                  color: "#ffffff",
                  px: 4,
                  py: 1.7,
                  borderRadius: 3,
                  fontSize: "1rem",
                  fontWeight: 700,
                  textTransform: "none",
                  "&:hover": { bgcolor: "#7563f0" },
                }}
              >
                Create Room
              </Button>

              <Button
                variant="outlined"
                size="large"
                startIcon={<GroupsRoundedIcon />}
                onClick={openJoinDialog}
                sx={{
                  color: "#ffffff",
                  borderColor: "rgba(255,255,255,0.25)",
                  px: 4,
                  py: 1.7,
                  borderRadius: 3,
                  fontSize: "1rem",
                  fontWeight: 700,
                  textTransform: "none",
                  "&:hover": {
                    borderColor: "#8b7cff",
                    bgcolor: "rgba(139,124,255,0.08)",
                  },
                }}
              >
                Join a Room
              </Button>
            </Stack>

            <Stack direction={{ xs: "column", sm: "row" }} spacing={4}>
              <Stack direction="row" spacing={1.5} alignItems="center">
                <EmojiObjectsRoundedIcon
                  sx={{ color: "#f5c76b", fontSize: 28 }}
                />
                <Box>
                  <Typography sx={{ fontWeight: 700 }}>
                    Guess the word
                  </Typography>
                  <Typography variant="body2" sx={{ color: "#8993ab" }}>
                    Think fast and score points
                  </Typography>
                </Box>
              </Stack>

              <Stack direction="row" spacing={1.5} alignItems="center">
                <GroupsRoundedIcon sx={{ color: "#71dfba", fontSize: 28 }} />
                <Box>
                  <Typography sx={{ fontWeight: 700 }}>
                    Play with friends
                  </Typography>
                  <Typography variant="body2" sx={{ color: "#8993ab" }}>
                    Compete in multiplayer rooms
                  </Typography>
                </Box>
              </Stack>
            </Stack>
          </Box>
        </Box>
      </Container>

      {/* Create Room Dialog */}
      <Dialog
        open={createDialogOpen}
        onClose={closeCreateDialog}
        fullWidth
        maxWidth="xs"
        slotProps={{
          paper: {
            sx: {
              bgcolor: "#151b2e",
              color: "#ffffff",
              borderRadius: 4,
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 800, pt: 3 }}>
          Create a Room
        </DialogTitle>

        <DialogContent>
          <Typography sx={{ color: "#a6aec3", mb: 3 }}>
            Choose your player name and the number of rounds. Your friends can
            join using the room code.
          </Typography>

          {errorMessage && (
            <Alert
              severity="error"
              onClose={() => setErrorMessage("")}
              sx={{ mb: 2 }}
            >
              {errorMessage}
            </Alert>
          )}

          <Stack spacing={2}>
            <TextField
              label="Your player name"
              value={createUsername}
              onChange={(event) => setCreateUsername(event.target.value)}
              fullWidth
              disabled={isCreating}
              slotProps={{ htmlInput: { maxLength: 30 } }}
              sx={darkFieldStyles}
            />

            <TextField
              select
              label="Number of rounds"
              value={totalRounds}
              onChange={(event) => setTotalRounds(Number(event.target.value))}
              fullWidth
              disabled={isCreating}
              sx={darkFieldStyles}
            >
              {[1, 2, 3, 4, 5].map((rounds) => (
                <MenuItem key={rounds} value={rounds}>
                  {rounds} {rounds === 1 ? "round" : "rounds"}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 3, gap: 1 }}>
          <Button
            onClick={closeCreateDialog}
            disabled={isCreating}
            sx={{ color: "#b7bfd2" }}
          >
            Cancel
          </Button>

          <Button
            variant="contained"
            disabled={!createUsername.trim() || isCreating}
            onClick={() => void handleCreateRoom()}
            sx={{
              bgcolor: "#8b7cff",
              "&:hover": { bgcolor: "#7563f0" },
            }}
          >
            {isCreating ? (
              <CircularProgress size={22} color="inherit" />
            ) : (
              "Create & Enter"
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Join Room Dialog */}
      <Dialog
        open={joinDialogOpen}
        onClose={closeJoinDialog}
        fullWidth
        maxWidth="xs"
        slotProps={{
          paper: {
            sx: {
              bgcolor: "#151b2e",
              color: "#ffffff",
              borderRadius: 4,
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 800, pt: 3 }}>
          Join a Game
        </DialogTitle>

        <DialogContent>
          <Typography sx={{ color: "#a6aec3", mb: 3 }}>
            Enter your player name and the room code shared by your friend.
          </Typography>

          {errorMessage && (
            <Alert
              severity="error"
              onClose={() => setErrorMessage("")}
              sx={{ mb: 2 }}
            >
              {errorMessage}
            </Alert>
          )}

          <Stack spacing={2}>
            <TextField
              label="Your player name"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              fullWidth
              disabled={isJoining}
              slotProps={{ htmlInput: { maxLength: 30 } }}
              sx={darkFieldStyles}
            />

            <TextField
              label="Room code"
              value={roomCode}
              onChange={(event) =>
                setRoomCode(event.target.value.toUpperCase())
              }
              onKeyDown={(event) => {
                if (event.key === "Enter" && !isJoining) {
                  void handleJoinRoom();
                }
              }}
              fullWidth
              disabled={isJoining}
              slotProps={{ htmlInput: { maxLength: 20 } }}
              sx={darkFieldStyles}
            />
          </Stack>
        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 3, gap: 1 }}>
          <Button
            onClick={closeJoinDialog}
            disabled={isJoining}
            sx={{ color: "#b7bfd2" }}
          >
            Cancel
          </Button>

          <Button
            variant="contained"
            disabled={!username.trim() || !roomCode.trim() || isJoining}
            onClick={() => void handleJoinRoom()}
            sx={{
              bgcolor: "#8b7cff",
              "&:hover": { bgcolor: "#7563f0" },
            }}
          >
            {isJoining ? (
              <CircularProgress size={22} color="inherit" />
            ) : (
              "Join Room"
            )}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

const darkFieldStyles = {
  "& .MuiInputLabel-root": { color: "#a6aec3" },
  "& .MuiOutlinedInput-root": {
    color: "#ffffff",
    "& fieldset": {
      borderColor: "rgba(255,255,255,0.2)",
    },
  },
  "& .MuiSvgIcon-root": {
    color: "#a6aec3",
  },
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/lobby/:roomCode" element={<LobbyPage />} />
        <Route path="/game/:roomCode" element={<GamePage />} />

        <Route
          path="/results/:roomCode"
          element={
            <PlaceholderPage
              title="Game Results"
              description="Final scores, rankings, and game history will appear here."
            />
          }
        />

        <Route
          path="*"
          element={
            <PlaceholderPage
              title="Page Not Found"
              description="This page doesn't exist. Return home to start playing."
            />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
