// Token management
const TOKEN_KEY = 'DIP_AUTH_TOKEN';
const USER_KEY = 'DIP_USER';

// Save authentication token to local storage
export const setToken = (token) => {
  localStorage.setItem(TOKEN_KEY, token);
};

// Get token from local storage
export const getToken = () => {
  return localStorage.getItem(TOKEN_KEY);
};

// Clear token from local storage
export const clearToken = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

// Check if user is authenticated
export const isAuthenticated = () => {
  return !!getToken();
};

// Save user data to local storage
export const setUser = (user) => {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
};

// Get user data from local storage
export const getUser = () => {
  const userStr = localStorage.getItem(USER_KEY);
  if (userStr) {
    try {
      return JSON.parse(userStr);
    } catch (e) {
      clearToken(); // Clear invalid data
      return null;
    }
  }
  return null;
};

// Login and save token
export const handleLoginSuccess = (data) => {
  if (data.access_token) {
    setToken(data.access_token);
    return true;
  }
  return false;
};

// Logout (clear token and redirect)
export const logout = () => {
  clearToken();
  window.location.href = '/login';
};

// Protected route component
export const ProtectedRoute = ({ children }) => {
  if (!isAuthenticated()) {
    window.location.href = '/login';
    return null;
  }
  return children;
};