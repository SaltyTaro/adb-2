import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Link } from 'react-router-dom';
import { Package, LogOut, Menu, X, User, BarChart2, Home } from 'lucide-react';

import { isAuthenticated, logout, getUser } from './services/auth';
import { getCurrentUser } from './services/api';

// Import pages and components
import Dashboard from './components/Dashboard';
import Project from './pages/Project';
import DependencyDetail from './components/DependencyDetail';
import AnalysisReport from './components/AnalysisReport';
import Login from './pages/Login';
import Register from './pages/Register';
import Settings from './pages/Settings';

// Protected Route component
const ProtectedRoute = ({ children }) => {
  if (!isAuthenticated()) {
    return <Navigate to="/login" />;
  }
  return children;
};

const App = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  
  useEffect(() => {
    const loadUser = async () => {
      try {
        if (isAuthenticated()) {
          // Load user data from API or local storage
          const userData = getUser();
          if (!userData) {
            const fetchedUser = await getCurrentUser();
            setUser(fetchedUser);
          } else {
            setUser(userData);
          }
        }
      } catch (error) {
        console.error('Error loading user data:', error);
      } finally {
        setLoading(false);
      }
    };
    
    loadUser();
  }, []);
  
  const handleLogout = () => {
    logout();
    setUser(null);
  };
  
  const toggleMobileMenu = () => {
    setMobileMenuOpen(!mobileMenuOpen);
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-pulse">
          <Package size={48} className="text-blue-500" />
          <p className="mt-2 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }
  
  return (
    <Router>
      <div className="min-h-screen bg-gray-100">
        {isAuthenticated() ? (
          // Authenticated layout with sidebar
          <div className="flex h-screen overflow-hidden">
            {/* Sidebar for desktop */}
            <div className="hidden md:flex md:flex-shrink-0">
              <div className="flex flex-col w-64 border-r bg-white">
                <div className="flex items-center justify-center h-16 px-4 border-b">
                  <Link to="/" className="flex items-center">
                    <Package size={24} className="text-blue-500 mr-2" />
                    <span className="text-lg font-bold">Dependency IQ</span>
                  </Link>
                </div>
                <div className="flex flex-col flex-grow overflow-y-auto">
                  <nav className="flex-1 px-2 py-4 space-y-1">
                    <Link
                      to="/"
                      className="flex items-center px-2 py-2 rounded-md hover:bg-gray-100"
                    >
                      <Home size={20} className="mr-3 text-gray-600" />
                      Dashboard
                    </Link>
                    <Link
                      to="/settings"
                      className="flex items-center px-2 py-2 rounded-md hover:bg-gray-100"
                    >
                      <User size={20} className="mr-3 text-gray-600" />
                      Profile
                    </Link>
                  </nav>
                  <div className="px-4 py-4 border-t">
                    <div className="flex items-center">
                      <div className="flex-1">
                        <p className="text-sm font-medium">{user?.username || 'User'}</p>
                        <p className="text-xs text-gray-500">{user?.email || ''}</p>
                      </div>
                      <button
                        onClick={handleLogout}
                        className="p-1 hover:bg-gray-100 rounded"
                        title="Logout"
                      >
                        <LogOut size={18} className="text-gray-600" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Main content */}
            <div className="flex flex-col flex-1 w-0 overflow-hidden">
              {/* Mobile header */}
              <div className="md:hidden pl-1 pt-1 sm:pl-3 sm:pt-3 flex items-center justify-between border-b h-16 px-4">
                <button
                  onClick={toggleMobileMenu}
                  className="p-2 rounded-md hover:bg-gray-100"
                >
                  {mobileMenuOpen ? (
                    <X size={24} className="text-gray-600" />
                  ) : (
                    <Menu size={24} className="text-gray-600" />
                  )}
                </button>
                <div className="flex items-center">
                  <Package size={24} className="text-blue-500 mr-2" />
                  <span className="text-lg font-bold">Dependency IQ</span>
                </div>
                <div className="w-10"></div> {/* Spacer to center logo */}
              </div>
              
              {/* Mobile menu */}
              {mobileMenuOpen && (
                <div className="md:hidden fixed inset-0 z-10 bg-white pt-16">
                  <div className="px-2 pt-2 pb-3 space-y-1">
                    <Link
                      to="/"
                      onClick={toggleMobileMenu}
                      className="block px-3 py-2 rounded-md hover:bg-gray-100 font-medium"
                    >
                      <div className="flex items-center">
                        <Home size={20} className="mr-3 text-gray-600" />
                        Dashboard
                      </div>
                    </Link>
                    <Link
                      to="/settings"
                      onClick={toggleMobileMenu}
                      className="block px-3 py-2 rounded-md hover:bg-gray-100 font-medium"
                    >
                      <div className="flex items-center">
                        <User size={20} className="mr-3 text-gray-600" />
                        Profile
                      </div>
                    </Link>
                  </div>
                  
                  <div className="border-t px-4 py-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium">{user?.username || 'User'}</p>
                        <p className="text-xs text-gray-500">{user?.email || ''}</p>
                      </div>
                      <button
                        onClick={() => {
                          handleLogout();
                          toggleMobileMenu();
                        }}
                        className="p-2 hover:bg-gray-100 rounded flex items-center"
                      >
                        <LogOut size={18} className="text-gray-600 mr-1" />
                        <span className="text-sm">Logout</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}
              
              {/* Main content */}
              <main className="flex-1 overflow-y-auto bg-gray-100">
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/projects/:projectId" element={<Project />} />
                  <Route path="/dependencies/:dependencyId" element={<DependencyDetail />} />
                  <Route path="/analyses/:analysisId" element={<AnalysisReport />} />
                  <Route path="/settings" element={<Settings />} />
                </Routes>
              </main>
            </div>
          </div>
        ) : (
          // Public routes
          <Routes>
            <Route path="/login" element={<Login setUser={setUser} />} />
            <Route path="/register" element={<Register setUser={setUser} />} />
            <Route path="*" element={<Navigate to="/login" />} />
          </Routes>
        )}
      </div>
    </Router>
  );
};

export default App;