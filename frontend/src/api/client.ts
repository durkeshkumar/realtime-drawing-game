
import axios from "axios";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

if (!apiBaseUrl) {
  throw new Error(
    "VITE_API_BASE_URL is not configured. Please check frontend/.env."
  );
}

const apiClient = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 15000,
});

// Automatically attach the player's access token to API requests.
apiClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem("player_access_token");

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

export default apiClient;
