using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Speech.Synthesis;
using System.Threading.Tasks;
using System.Windows.Input;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Microsoft.Extensions.Logging;
using DexterCockpit.Models;
using DexterCockpit.Services;

namespace DexterCockpit.ViewModels;

/// <summary>
/// ViewModel for main chat and per-agent chat windows
/// Handles broadcast mode, agent selection, TTS, and microphone input
/// </summary>
public partial class ChatViewModel : ObservableObject
{
    private readonly DexterApiClient _apiClient;
    private readonly DexterWebSocketClient _wsClient;
    private readonly ILogger<ChatViewModel> _logger;
    private readonly SpeechSynthesizer _tts;

    [ObservableProperty]
    private ObservableCollection<ChatMessage> messages = new();

    [ObservableProperty]
    private string inputText = string.Empty;

    [ObservableProperty]
    private bool isBroadcastMode = true;

    [ObservableProperty]
    private string selectedAgentId = "dexter";

    [ObservableProperty]
    private ObservableCollection<Agent> availableAgents = new();

    [ObservableProperty]
    private bool isTtsEnabled = true;

    [ObservableProperty]
    private bool isTtsMuted = false;

    [ObservableProperty]
    private bool isMicrophoneActive = false;

    [ObservableProperty]
    private string statusMessage = "Ready";

    [ObservableProperty]
    private bool isWaitingForResponse = false;

    public ChatViewModel(
        DexterApiClient apiClient,
        DexterWebSocketClient wsClient,
        ILogger<ChatViewModel> logger)
    {
        _apiClient = apiClient;
        _wsClient = wsClient;
        _logger = logger;
        _tts = new SpeechSynthesizer();

        // Configure TTS
        _tts.Rate = 0; // Normal speed
        _tts.Volume = 80; // 80% volume

        // Subscribe to chat responses (would come via WebSocket)
        // _wsClient.ChatResponse += OnChatResponseReceived;
    }

    /// <summary>
    /// Send message to Dexter or selected agent
    /// </summary>
    [RelayCommand]
    public async Task SendMessageAsync()
    {
        if (string.IsNullOrWhiteSpace(InputText)) return;

        var userMessage = new ChatMessage
        {
            Id = Guid.NewGuid(),
            Timestamp = DateTime.UtcNow,
            SenderName = "User",
            SenderId = "user",
            Message = InputText,
            IsUser = true
        };

        Messages.Add(userMessage);
        _logger.LogInformation("User message: {Message}", InputText);

        try
        {
            IsWaitingForResponse = true;
            StatusMessage = IsBroadcastMode 
                ? "Broadcasting to all agents (Dexter will reply)..." 
                : $"Sending to {SelectedAgentId}...";

            // Send to backend (endpoint to be implemented)
            // For broadcast mode, only Dexter replies
            var endpoint = IsBroadcastMode ? "/dexter/chat" : $"/agents/{SelectedAgentId}/chat";
            
            // Placeholder for actual API call
            // var response = await _apiClient.SendChatMessageAsync(endpoint, InputText);

            // Simulate response for now
            await Task.Delay(500);
            var botResponse = new ChatMessage
            {
                Id = Guid.NewGuid(),
                Timestamp = DateTime.UtcNow,
                SenderName = IsBroadcastMode ? "Dexter" : SelectedAgentId,
                SenderId = IsBroadcastMode ? "dexter" : SelectedAgentId,
                Message = $"[Simulated response to: {InputText}]",
                IsUser = false
            };

            Messages.Add(botResponse);

            // TTS for bot response
            if (IsTtsEnabled && !IsTtsMuted)
            {
                SpeakAsync(botResponse.Message);
            }

            InputText = string.Empty;
            StatusMessage = "Ready";
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error sending message");
            StatusMessage = $"Error: {ex.Message}";
        }
        finally
        {
            IsWaitingForResponse = false;
        }
    }

    /// <summary>
    /// Toggle broadcast mode
    /// </summary>
    [RelayCommand]
    public void ToggleBroadcast()
    {
        IsBroadcastMode = !IsBroadcastMode;
        StatusMessage = IsBroadcastMode 
            ? "Broadcast mode: All agents listen, Dexter replies" 
            : $"Direct mode: Talking to {SelectedAgentId}";
        _logger.LogInformation("Broadcast mode: {Enabled}", IsBroadcastMode);
    }

    /// <summary>
    /// Toggle TTS mute
    /// </summary>
    [RelayCommand]
    public void ToggleTtsMute()
    {
        IsTtsMuted = !IsTtsMuted;
        StatusMessage = IsTtsMuted ? "TTS muted" : "TTS enabled";
        _logger.LogInformation("TTS muted: {Muted}", IsTtsMuted);
    }

    /// <summary>
    /// Start/Stop microphone input
    /// </summary>
    [RelayCommand]
    public void ToggleMicrophone()
    {
        IsMicrophoneActive = !IsMicrophoneActive;
        
        if (IsMicrophoneActive)
        {
            StartSpeechRecognition();
            StatusMessage = "Listening...";
        }
        else
        {
            StopSpeechRecognition();
            StatusMessage = "Microphone off";
        }
        
        _logger.LogInformation("Microphone active: {Active}", IsMicrophoneActive);
    }

    /// <summary>
    /// Clear chat history
    /// </summary>
    [RelayCommand]
    public void ClearChat()
    {
        Messages.Clear();
        StatusMessage = "Chat cleared";
        _logger.LogInformation("Chat history cleared");
    }

    /// <summary>
    /// Speak text using TTS
    /// </summary>
    private void SpeakAsync(string text)
    {
        if (string.IsNullOrEmpty(text)) return;

        Task.Run(() =>
        {
            try
            {
                _tts.SpeakAsync(text);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "TTS error");
            }
        });
    }

    /// <summary>
    /// Start speech recognition (to be implemented with System.Speech.Recognition)
    /// </summary>
    private void StartSpeechRecognition()
    {
        // TODO: Implement speech recognition
        // using System.Speech.Recognition.SpeechRecognitionEngine
        _logger.LogInformation("Speech recognition started (placeholder)");
    }

    /// <summary>
    /// Stop speech recognition
    /// </summary>
    private void StopSpeechRecognition()
    {
        // TODO: Stop speech recognition engine
        _logger.LogInformation("Speech recognition stopped (placeholder)");
    }

    partial void OnSelectedAgentIdChanged(string value)
    {
        if (!IsBroadcastMode)
        {
            StatusMessage = $"Talking to {value}";
        }
    }

    /// <summary>
    /// Cleanup
    /// </summary>
    public void Dispose()
    {
        _tts?.Dispose();
        StopSpeechRecognition();
    }
}

/// <summary>
/// Chat message model
/// </summary>
public partial class ChatMessage : ObservableObject
{
    [ObservableProperty]
    private Guid id;

    [ObservableProperty]
    private DateTime timestamp;

    [ObservableProperty]
    private string senderName = string.Empty;

    [ObservableProperty]
    private string senderId = string.Empty;

    [ObservableProperty]
    private string message = string.Empty;

    [ObservableProperty]
    private bool isUser;

    public string FormattedTimestamp => Timestamp.ToLocalTime().ToString("HH:mm:ss");
}
