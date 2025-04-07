import React, { useState, useEffect } from 'react';
import { Key, User, Save, RefreshCw, Copy, CheckCircle, AlertCircle } from 'lucide-react';

import { getCurrentUser, createApiKey } from '../services/api';
import { getUser, setUser } from '../services/auth';

const Settings = () => {
  const [profile, setProfile] = useState({
    username: '',
    email: ''
  });
  const [apiKeys, setApiKeys] = useState([]);
  const [newKeyName, setNewKeyName] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [creatingKey, setCreatingKey] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [newKey, setNewKey] = useState(null);
  const [copySuccess, setCopySuccess] = useState(false);
  
  useEffect(() => {
    const loadUserData = async () => {
      try {
        setLoading(true);
        // Get cached user data first
        const userData = getUser();
        if (userData) {
          setProfile({
            username: userData.username || '',
            email: userData.email || ''
          });
        }
        
        // Then fetch fresh data from API
        const freshUserData = await getCurrentUser();
        setProfile({
          username: freshUserData.username || '',
          email: freshUserData.email || ''
        });
        
        // Update cached user data
        setUser(freshUserData);
        
        // Load API keys
        // This would typically be a separate API call
        // For this example, we're using mock data
        setApiKeys([
          {
            id: '1',
            name: 'Development Key',
            created_at: '2023-01-15T12:00:00Z',
            expires_at: '2024-01-15T12:00:00Z'
          }
        ]);
      } catch (error) {
        console.error('Error loading user data:', error);
        setError('Failed to load user data');
      } finally {
        setLoading(false);
      }
    };
    
    loadUserData();
  }, []);
  
  const handleProfileChange = (e) => {
    const { name, value } = e.target;
    setProfile(prev => ({ ...prev, [name]: value }));
  };
  
  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');
    
    try {
      // In a real app, you would make an API call to update the profile
      // For this example, we'll just simulate a successful update
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Update cached user data
      setUser(profile);
      
      setSuccess('Profile updated successfully');
    } catch (error) {
      console.error('Error updating profile:', error);
      setError('Failed to update profile');
    } finally {
      setSaving(false);
    }
  };
  
  const handleCreateApiKey = async (e) => {
    e.preventDefault();
    if (!newKeyName.trim()) {
      setError('Please enter a name for the API key');
      return;
    }
    
    setCreatingKey(true);
    setError('');
    setSuccess('');
    
    try {
      // Create new API key
      const keyData = await createApiKey(newKeyName);
      
      // Add to list and clear form
      setApiKeys([...apiKeys, {
        id: keyData.id,
        name: keyData.name,
        created_at: new Date().toISOString(),
        expires_at: keyData.expires_at
      }]);
      
      setNewKeyName('');
      setNewKey({
        key: keyData.api_key,
        name: keyData.name
      });
      
      setSuccess('API key created successfully');
    } catch (error) {
      console.error('Error creating API key:', error);
      setError('Failed to create API key');
    } finally {
      setCreatingKey(false);
    }
  };
  
  const handleCopyApiKey = () => {
    if (newKey) {
      navigator.clipboard.writeText(newKey.key).then(
        () => {
          setCopySuccess(true);
          setTimeout(() => setCopySuccess(false), 2000);
        },
        () => {
          setError('Failed to copy API key');
        }
      );
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw size={32} className="animate-spin text-blue-500 mb-2" />
        <p className="text-gray-700 ml-2">Loading settings...</p>
      </div>
    );
  }
  
  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">Account Settings</h1>
      
      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 mb-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertCircle size={18} className="text-red-500" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-700">
                {error}
              </p>
            </div>
          </div>
        </div>
      )}
      
      {success && (
        <div className="bg-green-50 border-l-4 border-green-500 p-4 mb-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <CheckCircle size={18} className="text-green-500" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-green-700">
                {success}
              </p>
            </div>
          </div>
        </div>
      )}
      
      <div className="bg-white shadow rounded-lg mb-6">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-medium flex items-center">
            <User size={20} className="mr-2" />
            Profile Information
          </h2>
        </div>
        <div className="p-6">
          <form onSubmit={handleProfileSubmit}>
            <div className="mb-4">
              <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
                Username
              </label>
              <input
                type="text"
                id="username"
                name="username"
                value={profile.username}
                onChange={handleProfileChange}
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled
              />
            </div>
            <div className="mb-4">
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={profile.email}
                onChange={handleProfileChange}
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 flex items-center"
                disabled={saving}
              >
                {saving ? (
                  <>
                    <RefreshCw size={16} className="mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save size={16} className="mr-2" />
                    Save Changes
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
      
      <div className="bg-white shadow rounded-lg">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-medium flex items-center">
            <Key size={20} className="mr-2" />
            API Keys
          </h2>
        </div>
        <div className="p-6">
          <p className="text-sm text-gray-600 mb-4">
            API keys allow you to access the Dependency Intelligence Platform API programmatically.
            Keep your keys secure - anyone with your key can access the API as you.
          </p>
          
          {newKey && (
            <div className="bg-yellow-50 border rounded-md p-4 mb-4">
              <h3 className="font-medium mb-2">New API Key Created: {newKey.name}</h3>
              <p className="text-sm text-yellow-800 mb-2">
                This is the only time the key will be displayed. Make sure to copy it now!
              </p>
              <div className="flex items-center">
                <code className="bg-gray-100 px-3 py-2 rounded-l-md flex-1 overflow-x-auto">
                  {newKey.key}
                </code>
                <button
                  onClick={handleCopyApiKey}
                  className="px-3 py-2 bg-blue-500 text-white rounded-r-md hover:bg-blue-600 flex items-center"
                  title="Copy to clipboard"
                >
                  {copySuccess ? (
                    <CheckCircle size={18} />
                  ) : (
                    <Copy size={18} />
                  )}
                </button>
              </div>
            </div>
          )}
          
          <div className="mb-4">
            <h3 className="font-medium mb-2">Your API Keys</h3>
            {apiKeys.length > 0 ? (
              <div className="border rounded-md overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Name
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Created
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Expires
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {apiKeys.map((key) => (
                      <tr key={key.id}>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="font-medium text-gray-900">{key.name}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {new Date(key.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {new Date(key.expires_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-gray-500 italic">
                No API keys found.
              </div>
            )}
          </div>
          
          <div>
            <h3 className="font-medium mb-2">Create New API Key</h3>
            <form onSubmit={handleCreateApiKey} className="flex items-end">
              <div className="flex-1 mr-2">
                <label htmlFor="keyName" className="block text-sm font-medium text-gray-700 mb-1">
                  Key Name
                </label>
                <input
                  type="text"
                  id="keyName"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Development Key"
                  required
                  disabled={creatingKey}
                />
              </div>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 flex items-center"
                disabled={creatingKey}
              >
                {creatingKey ? (
                  <>
                    <RefreshCw size={16} className="mr-2 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Key size={16} className="mr-2" />
                    Create Key
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;