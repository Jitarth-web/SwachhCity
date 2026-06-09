/**
 * Shared data store for SwachhGram applications
 * This simulates a database that all apps can access
 */

// In-memory data store (simulating database)
const SwachhGramData = {
  incidents: [],
  crews: [],
  assignments: [],
  
  // Add new incident
  addIncident: function(incident) {
    const newIncident = {
      id: 'INC-' + Date.now(),
      ...incident,
      status: 'pending',
      created_at: new Date().toISOString(),
      assigned_to: null,
      assigned_at: null,
      started_at: null,
      completed_at: null,
      completion_notes: null,
      weight_collected: null
    };
    
    this.incidents.push(newIncident);
    console.log('New incident added:', newIncident);
    return newIncident;
  },
  
  // Get all incidents
  getAllIncidents: function() {
    return this.incidents;
  },
  
  // Get incidents by status
  getIncidentsByStatus: function(status) {
    return this.incidents.filter(inc => inc.status === status);
  },
  
  // Get incidents assigned to crew
  getIncidentsForCrew: function(crewId) {
    return this.incidents.filter(inc => inc.assigned_to === crewId);
  },
  
  // Assign incident to crew
  assignIncident: function(incidentId, crewId) {
    const incident = this.incidents.find(inc => inc.id === incidentId);
    if (incident) {
      incident.assigned_to = crewId;
      incident.assigned_at = new Date().toISOString();
      incident.status = 'assigned';
      console.log(`Incident ${incidentId} assigned to crew ${crewId}`);
      return true;
    }
    return false;
  },
  
  // Start work on incident
  startIncidentWork: function(incidentId) {
    const incident = this.incidents.find(inc => inc.id === incidentId);
    if (incident) {
      incident.started_at = new Date().toISOString();
      incident.status = 'in_progress';
      console.log(`Work started on incident ${incidentId}`);
      return true;
    }
    return false;
  },
  
  // Complete incident
  completeIncident: function(incidentId, completionData) {
    const incident = this.incidents.find(inc => inc.id === incidentId);
    if (incident) {
      incident.completed_at = new Date().toISOString();
      incident.status = 'completed';
      incident.completion_notes = completionData.notes;
      incident.weight_collected = completionData.weight;
      console.log(`Incident ${incidentId} completed`);
      return true;
    }
    return false;
  },
  
  // Get crew by ID
  getCrewById: function(crewId) {
    return this.crews.find(crew => crew.id === crewId);
  },
  
  // Update crew location
  updateCrewLocation: function(crewId, location) {
    const crew = this.getCrewById(crewId);
    if (crew) {
      crew.current_location = location;
      crew.last_location_update = new Date().toISOString();
      return true;
    }
    return false;
  },
  
  // Initialize sample data
  initializeSampleData: function() {
    // Sample crews
    this.crews = [
      {
        id: 'crew-001',
        name: 'Team Alpha',
        status: 'active',
        current_location: { latitude: 12.9716, longitude: 77.5946, accuracy: 10 },
        last_location_update: new Date().toISOString(),
        collections_today: 0,
        avg_time: 0
      },
      {
        id: 'crew-002',
        name: 'Team Beta',
        status: 'active',
        current_location: { latitude: 12.9452, longitude: 77.6145, accuracy: 15 },
        last_location_update: new Date().toISOString(),
        collections_today: 0,
        avg_time: 0
      },
      {
        id: 'crew-003',
        name: 'Team Gamma',
        status: 'active',
        current_location: { latitude: 12.9886, longitude: 77.5906, accuracy: 12 },
        last_location_update: new Date().toISOString(),
        collections_today: 0,
        avg_time: 0
      }
    ];
    
    console.log('Sample data initialized');
  }
};

// Initialize sample data
SwachhGramData.initializeSampleData();

// Make it globally available
if (typeof window !== 'undefined') {
  window.SwachhGramData = SwachhGramData;
} else if (typeof global !== 'undefined') {
  global.SwachhGramData = SwachhGramData;
}
