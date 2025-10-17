using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using DexterCockpit.Models;

namespace DexterCockpit.Views
{
    public partial class MissionControlView : UserControl
    {
        public ObservableCollection<Mission> Missions { get; set; }
        private readonly HttpClient httpClient;
        private readonly string backendUrl;

        public MissionControlView()
        {
            InitializeComponent();
            Missions = new ObservableCollection<Mission>();
            MissionsListBox.ItemsSource = Missions;
            
            // Initialize HTTP client for backend API
            httpClient = new HttpClient();
            backendUrl = "http://localhost:8765"; // Default from dexter_config.yml
            
            // Show empty state initially
            UpdateEmptyState();
            
            // Load missions from real backend
            _ = LoadMissionsAsync();
        }

        private async Task LoadMissionsAsync()
        {
            try
            {
                UpdateConnectionStatus(false); // Show connecting...
                
                // Try to fetch missions from backend
                var response = await httpClient.GetAsync($"{backendUrl}/missions");
                
                if (response.IsSuccessStatusCode)
                {
                    var json = await response.Content.ReadAsStringAsync();
                    var missions = JsonSerializer.Deserialize<Mission[]>(json);
                    
                    if (missions != null)
                    {
                        Dispatcher.Invoke(() =>
                        {
                            Missions.Clear();
                            foreach (var mission in missions)
                            {
                                Missions.Add(mission);
                            }
                            UpdateEmptyState();
                            UpdateMissionCount();
                            UpdateLastUpdateTime();
                            UpdateConnectionStatus(true);
                        });
                    }
                }
                else
                {
                    UpdateConnectionStatus(false);
                }
            }
            catch (Exception ex)
            {
                Dispatcher.Invoke(() =>
                {
                    UpdateConnectionStatus(false);
                    ConnectionStatusText.Text = $"○ Backend Offline: {ex.Message}";
                });
            }
        }

        private void UpdateMissionCount()
        {
            int activeCount = Missions.Count(m => m.Status == MissionStatus.Running || m.Status == MissionStatus.Queued);
            MissionCountText.Text = $"({activeCount} active)";
        }

        private void UpdateEmptyState()
        {
            if (Missions.Count == 0)
            {
                EmptyState.Visibility = Visibility.Visible;
                MissionsListBox.Visibility = Visibility.Collapsed;
            }
            else
            {
                EmptyState.Visibility = Visibility.Collapsed;
                MissionsListBox.Visibility = Visibility.Visible;
            }
        }

        private void UpdateLastUpdateTime()
        {
            LastUpdateText.Text = $"Last update: {DateTime.Now:HH:mm:ss}";
        }

        private void RefreshButton_Click(object sender, RoutedEventArgs e)
        {
            // Reload missions from backend
            _ = LoadMissionsAsync();
        }

        private void NewMissionButton_Click(object sender, RoutedEventArgs e)
        {
            // TODO: Open mission creation dialog
            MessageBox.Show("Mission creation dialog coming soon!\n\nThis will allow you to:\n• Define mission name and description\n• Assign agents\n• Set priority\n• Upload YAML mission definitions", 
                          "New Mission", MessageBoxButton.OK, MessageBoxImage.Information);
        }

        // Public method to add mission (can be called from WebSocket handler)
        public void AddOrUpdateMission(Mission mission)
        {
            Dispatcher.Invoke(() =>
            {
                var existing = Missions.FirstOrDefault(m => m.Id == mission.Id);
                if (existing != null)
                {
                    // Update existing mission
                    existing.Name = mission.Name;
                    existing.Description = mission.Description;
                    existing.Status = mission.Status;
                    existing.CompletedSteps = mission.CompletedSteps;
                    existing.TotalSteps = mission.TotalSteps;
                    existing.CurrentStep = mission.CurrentStep;
                    existing.EndTime = mission.EndTime;
                }
                else
                {
                    // Add new mission
                    Missions.Add(mission);
                    UpdateEmptyState();
                }
                
                UpdateMissionCount();
                UpdateLastUpdateTime();
            });
        }

        // Public method to remove mission
        public void RemoveMission(string missionId)
        {
            Dispatcher.Invoke(() =>
            {
                var mission = Missions.FirstOrDefault(m => m.Id == missionId);
                if (mission != null)
                {
                    Missions.Remove(mission);
                    UpdateEmptyState();
                    UpdateMissionCount();
                    UpdateLastUpdateTime();
                }
            });
        }

        // Update connection status (can be called from WebSocket handler)
        public void UpdateConnectionStatus(bool connected)
        {
            Dispatcher.Invoke(() =>
            {
                if (connected)
                {
                    ConnectionStatusText.Text = "● Connected to Backend";
                    ConnectionStatusText.Foreground = new System.Windows.Media.SolidColorBrush(
                        (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#4CAF50"));
                }
                else
                {
                    ConnectionStatusText.Text = "○ Disconnected";
                    ConnectionStatusText.Foreground = new System.Windows.Media.SolidColorBrush(
                        (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#F44336"));
                }
            });
        }
    }
}
