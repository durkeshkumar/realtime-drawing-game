
import apiClient from "./client";

export interface Player {
  id: number;
  room_id: number;
  display_name: string;
  score: number;
  joined_at: string;
  left_at: string | null;
  is_ready: boolean;
}

export interface JoinRoomRequest {
  display_name: string;
}

export interface JoinRoomResponse extends Player {
  access_token: string;
  token_type: string;
}

export const joinRoom = async (
  roomCode: string,
  data: JoinRoomRequest
): Promise<JoinRoomResponse> => {
  const normalizedRoomCode = roomCode.trim().toUpperCase();

  const response = await apiClient.post<JoinRoomResponse>(
    `/rooms/${encodeURIComponent(normalizedRoomCode)}/players`,
    data
  );

  const result = response.data;

  sessionStorage.setItem("player_access_token", result.access_token);
  sessionStorage.setItem("player_id", String(result.id));
  sessionStorage.setItem("room_code", normalizedRoomCode);
  sessionStorage.setItem("player_display_name", result.display_name);

  return result;
};

export const logout = (): void => {
  sessionStorage.removeItem("player_access_token");
  sessionStorage.removeItem("player_id");
  sessionStorage.removeItem("room_code");
  sessionStorage.removeItem("player_display_name");
};
