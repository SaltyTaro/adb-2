import React from 'react';
import { 
  Shield, AlertTriangle, CheckCircle, XCircle, 
  BarChart2, Package, Heart, Activity
} from 'lucide-react';

const ImpactScoreCard = ({ dependency, score }) => {
  if (!dependency || !score) {
    return (
      <div className="p-4 border rounded bg-gray-50 text-center">
        <Package size={24} className="text-gray-400 mx-auto mb-2" />
        <p className="text-gray-500">No impact score data available</p>
      </div>
    );
  }
  
  // Helper function to format score as percentage
  const formatScore = (value) => {
    if (value === null || value === undefined) return 'N/A';
    return `${(value * 100).toFixed(0)}%`;
  };
  
  // Helper to get color class based on score
  const getScoreColorClass = (value) => {
    if (value === null || value === undefined) return 'text-gray-400';
    if (value >= 0.8) return 'text-red-600';
    if (value >= 0.6) return 'text-orange-500';
    if (value >= 0.4) return 'text-yellow-500';
    return 'text-green-500';
  };
  
  // Helper to get icon based on score
  const getScoreIcon = (value) => {
    if (value === null || value === undefined) return <AlertTriangle size={16} />;
    if (value >= 0.8) return <AlertTriangle size={16} />;
    if (value >= 0.4) return <AlertTriangle size={16} />;
    return <CheckCircle size={16} />;
  };
  
  return (
    <div className="border rounded overflow-hidden">
      <div className="bg-blue-50 p-4">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-blue-800 flex items-center">
            <Package size={18} className="mr-2" />
            {dependency.name}
          </h3>
          <div className={`font-bold text-lg ${getScoreColorClass(score.overall_score)}`}>
            {formatScore(score.overall_score)}
          </div>
        </div>
        <div className="text-sm text-blue-900 mt-1">
          {dependency.ecosystem} • {dependency.latest_version || 'Unknown version'}
        </div>
      </div>
      
      <div className="p-4">
        {/* Score Bars */}
        <div className="space-y-3">
          <div>
            <div className="flex justify-between items-center mb-1">
              <div className="text-sm font-medium flex items-center">
                <Heart size={14} className="mr-1 text-purple-500" />
                Business Value
              </div>
              <div className={`text-sm ${getScoreColorClass(score.business_value_score)}`}>
                {formatScore(score.business_value_score)}
              </div>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="h-2 rounded-full bg-purple-500"
                style={{ width: `${score.business_value_score * 100}%` }}
              ></div>
            </div>
          </div>
          
          <div>
            <div className="flex justify-between items-center mb-1">
              <div className="text-sm font-medium flex items-center">
                <Activity size={14} className="mr-1 text-blue-500" />
                Usage
              </div>
              <div className={`text-sm ${getScoreColorClass(score.usage_score)}`}>
                {formatScore(score.usage_score)}
              </div>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="h-2 rounded-full bg-blue-500"
                style={{ width: `${score.usage_score * 100}%` }}
              ></div>
            </div>
          </div>
          
          <div>
            <div className="flex justify-between items-center mb-1">
              <div className="text-sm font-medium flex items-center">
                <BarChart2 size={14} className="mr-1 text-yellow-500" />
                Complexity
              </div>
              <div className={`text-sm ${getScoreColorClass(score.complexity_score)}`}>
                {formatScore(score.complexity_score)}
              </div>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="h-2 rounded-full bg-yellow-500"
                style={{ width: `${score.complexity_score * 100}%` }}
              ></div>
            </div>
          </div>
          
          <div>
            <div className="flex justify-between items-center mb-1">
              <div className="text-sm font-medium flex items-center">
                <Shield size={14} className="mr-1 text-green-500" />
                Health
              </div>
              <div className={`text-sm ${getScoreColorClass(score.health_score)}`}>
                {formatScore(score.health_score)}
              </div>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="h-2 rounded-full bg-green-500"
                style={{ width: `${score.health_score * 100}%` }}
              ></div>
            </div>
          </div>
        </div>
        
        {/* Usage Information */}
        {score.used_features && (
          <div className="mt-4">
            <div className="text-sm font-medium mb-2">Feature Usage</div>
            <div className="flex justify-between text-sm">
              <div>
                <span className="text-gray-600">Used Features:</span>
                <span className="ml-1 font-medium">{score.used_features.length}</span>
              </div>
              {score.unused_features && (
                <div>
                  <span className="text-gray-600">Unused Features:</span>
                  <span className="ml-1 font-medium">{score.unused_features.length}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
      
      {/* Impact Rating */}
      <div className={`p-3 text-center text-white font-medium ${
        score.overall_score >= 0.8 ? 'bg-red-500' :
        score.overall_score >= 0.6 ? 'bg-orange-500' :
        score.overall_score >= 0.4 ? 'bg-yellow-500' :
        'bg-green-500'
      }`}>
        {score.overall_score >= 0.8 ? 'Critical Dependency' :
         score.overall_score >= 0.6 ? 'High Impact' :
         score.overall_score >= 0.4 ? 'Medium Impact' :
         'Low Impact'}
      </div>
    </div>
  );
};

export default ImpactScoreCard;