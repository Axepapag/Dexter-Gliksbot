using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace DexterCockpit.Models
{
    /// <summary>
    /// Represents the status of a mission
    /// </summary>
    public enum MissionStatus
    {
        Queued,      // Waiting to start
        Running,     // Currently executing
        Paused,      // Temporarily stopped
        Completed,   // Successfully finished
        Failed,      // Encountered error
        Cancelled    // Manually stopped
    }

    /// <summary>
    /// Model for an agent mission/task with progress tracking
    /// </summary>
    public class Mission : INotifyPropertyChanged
    {
        private string _id = Guid.NewGuid().ToString();
        private string _name = "Untitled Mission";
        private string _description = string.Empty;
        private MissionStatus _status = MissionStatus.Queued;
        private List<string> _assignedAgentIds = new List<string>();
        private DateTime _startTime = DateTime.UtcNow;
        private DateTime? _endTime;
        private int _totalSteps = 0;
        private int _completedSteps = 0;
        private double _progressPercent = 0.0;
        private string _currentStep = string.Empty;
        private string _yamlDefinition = string.Empty;
        private Dictionary<string, object> _metadata = new Dictionary<string, object>();

        public event PropertyChangedEventHandler PropertyChanged;

        public string Id
        {
            get => _id;
            set { _id = value; OnPropertyChanged(); }
        }

        public string Name
        {
            get => _name;
            set { _name = value; OnPropertyChanged(); }
        }

        public string Description
        {
            get => _description;
            set { _description = value; OnPropertyChanged(); }
        }

        public MissionStatus Status
        {
            get => _status;
            set 
            { 
                _status = value; 
                OnPropertyChanged();
                OnPropertyChanged(nameof(StatusColor));
                OnPropertyChanged(nameof(StatusText));
            }
        }

        public List<string> AssignedAgentIds
        {
            get => _assignedAgentIds;
            set { _assignedAgentIds = value; OnPropertyChanged(); OnPropertyChanged(nameof(AgentsText)); }
        }

        public DateTime StartTime
        {
            get => _startTime;
            set { _startTime = value; OnPropertyChanged(); OnPropertyChanged(nameof(ElapsedTime)); }
        }

        public DateTime? EndTime
        {
            get => _endTime;
            set { _endTime = value; OnPropertyChanged(); OnPropertyChanged(nameof(ElapsedTime)); }
        }

        public int TotalSteps
        {
            get => _totalSteps;
            set { _totalSteps = value; OnPropertyChanged(); UpdateProgress(); }
        }

        public int CompletedSteps
        {
            get => _completedSteps;
            set { _completedSteps = value; OnPropertyChanged(); UpdateProgress(); }
        }

        public double ProgressPercent
        {
            get => _progressPercent;
            private set { _progressPercent = value; OnPropertyChanged(); }
        }

        public string CurrentStep
        {
            get => _currentStep;
            set { _currentStep = value; OnPropertyChanged(); }
        }

        public string YamlDefinition
        {
            get => _yamlDefinition;
            set { _yamlDefinition = value; OnPropertyChanged(); }
        }

        public Dictionary<string, object> Metadata
        {
            get => _metadata;
            set { _metadata = value; OnPropertyChanged(); }
        }

        // Computed properties for UI binding
        public TimeSpan ElapsedTime => (EndTime ?? DateTime.UtcNow) - StartTime;

        public string StatusColor => Status switch
        {
            MissionStatus.Queued => "#9E9E9E",      // Gray
            MissionStatus.Running => "#2196F3",     // Blue
            MissionStatus.Paused => "#FF9800",      // Orange
            MissionStatus.Completed => "#4CAF50",   // Green
            MissionStatus.Failed => "#F44336",      // Red
            MissionStatus.Cancelled => "#757575",   // Dark gray
            _ => "#9E9E9E"
        };

        public string StatusText => Status.ToString();

        public string AgentsText => AssignedAgentIds.Count > 0 
            ? string.Join(", ", AssignedAgentIds) 
            : "None";

        public string ProgressText => $"{CompletedSteps}/{TotalSteps} steps ({ProgressPercent:F1}%)";

        private void UpdateProgress()
        {
            if (TotalSteps > 0)
            {
                ProgressPercent = (CompletedSteps / (double)TotalSteps) * 100.0;
            }
            else
            {
                ProgressPercent = 0.0;
            }
            OnPropertyChanged(nameof(ProgressText));
        }

        protected void OnPropertyChanged([CallerMemberName] string propertyName = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
        }
    }
}
