using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace DexterCockpit.State;

public sealed class AgentTabViewModel : INotifyPropertyChanged
{
    private string _displayName;
    private string _baseUrl;
    private string _apiKeyEnv;
    private string _model;
    private double _temperature;
    private string _systemPrompt;
    private string _commandText = string.Empty;
    private string _logText = string.Empty;
    private string _errorText = string.Empty;
    private bool _hasErrors = false;
    private string _sessionId;
    private string _targetTitleFallback;
    private bool _monitorEnabled;
    private string _quickTypeText = string.Empty;
    private string _quickHotkeyChord = string.Empty;
    private string? _selectedTemplateId;

    public AgentTabViewModel(AgentTabSettings settings)
    {
        Settings = settings;
        _displayName = settings.DisplayName;
        _baseUrl = settings.BaseUrl;
        _apiKeyEnv = settings.ApiKeyEnv;
        _model = settings.Model;
        _temperature = settings.Temperature;
        _systemPrompt = settings.SystemPrompt;
        _sessionId = string.IsNullOrWhiteSpace(settings.SessionId) ? "local" : settings.SessionId;
        _targetTitleFallback = settings.TargetTitleFallback;
        _monitorEnabled = settings.MonitorEnabled;
        _selectedTemplateId = settings.TemplateId;
    }

    public AgentTabSettings Settings { get; }

    public string TabId => Settings.TabId;

    public string DisplayName
    {
        get => _displayName;
        set => SetField(ref _displayName, value);
    }

    public string BaseUrl
    {
        get => _baseUrl;
        set => SetField(ref _baseUrl, value);
    }

    public string ApiKeyEnv
    {
        get => _apiKeyEnv;
        set => SetField(ref _apiKeyEnv, value);
    }

    public string Model
    {
        get => _model;
        set => SetField(ref _model, value);
    }

    public double Temperature
    {
        get => _temperature;
        set => SetField(ref _temperature, value);
    }

    public string SystemPrompt
    {
        get => _systemPrompt;
        set => SetField(ref _systemPrompt, value);
    }

    public string SessionId
    {
        get => _sessionId;
        set => SetField(ref _sessionId, string.IsNullOrWhiteSpace(value) ? "local" : value);
    }

    public string TargetTitleFallback
    {
        get => _targetTitleFallback;
        set => SetField(ref _targetTitleFallback, value ?? string.Empty);
    }

    public bool MonitorEnabled
    {
        get => _monitorEnabled;
        set => SetField(ref _monitorEnabled, value);
    }

    public string QuickTypeText
    {
        get => _quickTypeText;
        set => SetField(ref _quickTypeText, value ?? string.Empty);
    }

    public string QuickHotkeyChord
    {
        get => _quickHotkeyChord;
        set => SetField(ref _quickHotkeyChord, value ?? string.Empty);
    }

    public string CommandText
    {
        get => _commandText;
        set => SetField(ref _commandText, value);
    }

    public string LogText
    {
        get => _logText;
        set => SetField(ref _logText, value);
    }

    public string ErrorText
    {
        get => _errorText;
        set => SetField(ref _errorText, value);
    }

    public bool HasErrors
    {
        get => _hasErrors;
        set => SetField(ref _hasErrors, value);
    }

    public string? SelectedTemplateId
    {
        get => _selectedTemplateId;
        set => SetField(ref _selectedTemplateId, value);
    }

    public void AppendLog(string text)
    {
        var timestamp = DateTime.Now.ToString("HH:mm:ss");
        var formattedText = $"[{timestamp}] {text}";
        LogText = string.IsNullOrWhiteSpace(LogText) ? formattedText : $"{LogText}\n{formattedText}";
    }

    public void AppendError(string text)
    {
        var timestamp = DateTime.Now.ToString("HH:mm:ss");
        var formattedText = $"[{timestamp}] ERROR: {text}";
        ErrorText = string.IsNullOrWhiteSpace(ErrorText) ? formattedText : $"{ErrorText}\n{formattedText}";
        HasErrors = true;
    }

    public void ClearErrors()
    {
        ErrorText = string.Empty;
        HasErrors = false;
    }

    public void SyncToSettings()
    {
        Settings.DisplayName = DisplayName;
        Settings.BaseUrl = BaseUrl;
        Settings.ApiKeyEnv = ApiKeyEnv;
        Settings.Model = Model;
        Settings.Temperature = Temperature;
        Settings.SystemPrompt = SystemPrompt;
        Settings.SessionId = SessionId;
        Settings.TargetTitleFallback = TargetTitleFallback;
        Settings.MonitorEnabled = MonitorEnabled;
        Settings.TemplateId = SelectedTemplateId;
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    private void SetField<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (Equals(field, value)) return;
        field = value;
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}
