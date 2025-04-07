import React, { useState } from 'react';
import { 
  Calendar, ChevronRight, ChevronDown, AlertCircle, 
  GitBranch, GitMerge, Archive, Package
} from 'lucide-react';

const PredictiveTimeline = ({ timeline, dependencies, timeHorizon = 180 }) => {
  const [expandedDateIndices, setExpandedDateIndices] = useState([]);
  
  if (!timeline || Object.keys(timeline).length === 0) {
    return (
      <div className="p-4 border rounded bg-gray-50 text-center">
        <Calendar size={24} className="text-gray-400 mx-auto mb-2" />
        <p className="text-gray-500">No timeline data available</p>
      </div>
    );
  }
  
  // Sort dates chronologically
  const sortedDates = Object.keys(timeline).sort((a, b) => new Date(a) - new Date(b));
  
  // Toggle date expansion
  const toggleDateExpansion = (index) => {
    if (expandedDateIndices.includes(index)) {
      setExpandedDateIndices(expandedDateIndices.filter(i => i !== index));
    } else {
      setExpandedDateIndices([...expandedDateIndices, index]);
    }
  };
  
  // Render event icon based on type
  const renderEventIcon = (eventType) => {
    switch (eventType) {
      case 'breaking_change':
        return <AlertCircle size={16} className="text-red-500" />;
      case 'deprecation':
        return <Archive size={16} className="text-yellow-500" />;
      case 'predicted_release':
        return <Package size={16} className="text-blue-500" />;
      case 'major_version':
        return <GitBranch size={16} className="text-purple-500" />;
      case 'minor_version':
        return <GitMerge size={16} className="text-green-500" />;
      default:
        return <ChevronRight size={16} className="text-gray-500" />;
    }
  };
  
  // Format date for display
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  };
  
  return (
    <div className="predictive-timeline">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Predictive Timeline</h3>
        <div className="text-sm text-gray-500">
          Next {timeHorizon} days
        </div>
      </div>
      
      <div className="border rounded overflow-hidden">
        <div className="bg-blue-50 p-3">
          <div className="text-sm text-blue-800">
            Showing predicted breaking changes, updates, and deprecations over time
          </div>
        </div>
        
        <div className="divide-y">
          {sortedDates.map((date, index) => {
            const events = timeline[date];
            const isExpanded = expandedDateIndices.includes(index);
            
            return (
              <div key={index} className="relative">
                <button
                  className="w-full p-4 flex items-center justify-between hover:bg-gray-50 text-left"
                  onClick={() => toggleDateExpansion(index)}
                >
                  <div className="flex items-center">
                    <Calendar size={18} className="text-blue-500 mr-2" />
                    <div>
                      <div className="font-medium">{formatDate(date)}</div>
                      <div className="text-sm text-gray-500">
                        {events.length} event{events.length !== 1 ? 's' : ''}
                      </div>
                    </div>
                  </div>
                  {isExpanded ? 
                    <ChevronDown size={20} className="text-gray-400" /> : 
                    <ChevronRight size={20} className="text-gray-400" />
                  }
                </button>
                
                {/* Event details */}
                {isExpanded && (
                  <div className="p-4 pt-0 space-y-3 pl-10">
                    {events.map((event, eventIndex) => (
                      <div 
                        key={eventIndex} 
                        className={`p-3 rounded ${
                          event.event_type === 'breaking_change' ? 'bg-red-50 border border-red-100' :
                          event.event_type === 'deprecation' ? 'bg-yellow-50 border border-yellow-100' :
                          event.event_type === 'major_version' || (event.event_type === 'predicted_release' && event.is_major) ? 
                            'bg-purple-50 border border-purple-100' :
                          'bg-blue-50 border border-blue-100'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="font-medium flex items-center">
                            {renderEventIcon(event.event_type)}
                            <span className="ml-2">{event.dependency}</span>
                            {event.version && 
                              <span className="ml-2 px-2 py-0.5 bg-white rounded text-xs">
                                {event.version}
                              </span>
                            }
                          </div>
                          <div className="text-xs px-2 py-1 bg-white rounded capitalize">
                            {event.event_type.replace(/_/g, ' ')}
                          </div>
                        </div>
                        {event.details && (
                          <div className="text-sm mt-2">{event.details}</div>
                        )}
                        {event.compatibility_score !== undefined && (
                          <div className="mt-2">
                            <div className="text-xs text-gray-600">
                              Compatibility Score: 
                              <span className={`ml-1 font-medium ${
                                event.compatibility_score >= 0.7 ? 'text-green-600' :
                                event.compatibility_score >= 0.4 ? 'text-yellow-600' :
                                'text-red-600'
                              }`}>
                                {(event.compatibility_score * 100).toFixed(0)}%
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          
          {sortedDates.length === 0 && (
            <div className="p-4 text-center text-gray-500">
              No events predicted in the next {timeHorizon} days
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PredictiveTimeline;