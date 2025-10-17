using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Collections.Specialized;
using System.ComponentModel;
using System.Linq;
using System.Net.Http;
using System.Net.WebSockets;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Threading;
using DexterCockpit.Docking;
using DexterCockpit.Intent;
using DexterCockpit.Services;
using DexterCockpit.State;

namespace DexterCockpit;

public partial class AgentTabsControl : UserControl, INotifyPropertyChanged
{
    private readonly ObservableCollection<AgentTabViewModel> _tabs = new();
    private AgentTabViewModel? _selectedTab;
    private ClientWebSocket? _ws;
    private CancellationTokenSource? _receiveCts;
    private readonly SemaphoreSlim _sendGate = new(1, 1);
    private readonly CockpitStateStore _store = CockpitStateStore.Instance;
    private DockHostControl? _dockHost;
    private readonly AppConfiguration _config = AppConfiguration.Instance;
    private readonly Dictionary<string, DispatcherTimer> _monitorTimers = new();
    private readonly Dictionary<string, string> _lastOcrByTab = new();
    private readonly ObservableCollection<TemplateOption> _templateOptions = new();
    private readonly Dictionary<string, TemplateOption> _templateIndex = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, AgentSlotWindow> _floatingWindows = new();
    private readonly HttpClient _http = new();
    private bool _suppressTemplateSelection;

    public sealed record TemplateOption(string OptionId, string DisplayName, AgentTemplate Template, string Group);

    public sealed record AgentTemplate(string DisplayName, string SessionId, string BaseUrl, string Model, string ApiKeyEnv, double Temperature, string SystemPrompt);

    // REMOVED: Hardcoded cloud templates - only use real agents from dexter_config.yml
    private static readonly AgentTemplate[] CloudTemplates = Array.Empty<AgentTemplate>();

    public AgentTabsControl()
    {
        InitializeComponent();
        DataContext = this;
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
        _config.ConfigurationChanged += OnConfigurationChanged;
        InitializeTemplateOptions();
    }

    public ObservableCollection<AgentTabViewModel> Tabs => _tabs;

    public ObservableCollection<TemplateOption> TemplateOptions => _templateOptions;

    public AgentTabViewModel? SelectedTab
    {
        get => _selectedTab;
        set
        {
            if (_selectedTab != value)
            {
                _selectedTab = value;
                OnPropertyChanged(nameof(SelectedTab));
            }
        }
    }

    public event PropertyChangedEventHandler? PropertyChanged;
    public event EventHandler<string>? ConnectionStatusChanged;
    public event EventHandler<ChatMessageEventArgs>? ChatMessageRaised;
    public event EventHandler? TabsMetadataChanged;

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        LoadFromStore();
        _tabs.CollectionChanged += Tabs_CollectionChanged;
        _ = ConnectWithRetryAsync();
        _ = RefreshTemplateOptionsAsync();
    }

    private async Task ConnectWithRetryAsync()
    {
        const int maxRetries = 30;
        const int delaySeconds = 2;
        
        for (int attempt = 1; attempt <= maxRetries; attempt++)
        {
            if (await EnsureConnectedAsync())
            {
                return; // Successfully connected
            }
            
            RaiseConnectionStatus($"Connection failed (attempt {attempt}/{maxRetries}), retrying in {delaySeconds}s...");
            await Task.Delay(TimeSpan.FromSeconds(delaySeconds));
        }
        
        RaiseConnectionStatus($"Failed to connect after {maxRetries} attempts. Please ensure backend is running.");
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        _tabs.CollectionChanged -= Tabs_CollectionChanged;
        foreach (var timer in _monitorTimers.Values)
        {
            timer.Stop();
        }
        _monitorTimers.Clear();

        _receiveCts?.Cancel();
        _receiveCts = null;
        _ws?.Dispose();
        _ws = null;
        _config.ConfigurationChanged -= OnConfigurationChanged;

        foreach (var window in _floatingWindows.Values.ToList())
        {
            window.Close();
        }
        _floatingWindows.Clear();
    }


    private void Tabs_CollectionChanged(object? sender, NotifyCollectionChangedEventArgs e)
    {
        PersistState();
        if (e.Action == NotifyCollectionChangedAction.Remove && e.OldItems != null)
        {
            foreach (AgentTabViewModel tab in e.OldItems)
            {
                StopMonitor(tab.TabId, false);
            }
        }
        RaiseTabsMetadataChanged();
    }

    public void AttachDockHost(DockHostControl dockHost)
    {
        _dockHost = dockHost;
    }

    // REMOVED: Old CreateTemplate and BuildCloudPrompt - unused after removing hardcoded templates

    private void InitializeTemplateOptions()
    {
        // Start with empty - will be populated from backend API
        UpdateTemplateOptions(Enumerable.Empty<TemplateOption>());
    }

    private IEnumerable<TemplateOption> BuildStaticTemplateOptions()
    {
        // NO static templates - only real agents from backend
        yield break;
    }

    private AgentTemplate? CreateTemplateFromSlot(string slotId, JsonElement element)
    {
        if (element.ValueKind != JsonValueKind.Object)
        {
            return null;
        }

        string display = slotId;
        if (element.TryGetProperty("label", out var labelProp) && labelProp.ValueKind == JsonValueKind.String)
        {
            display = labelProp.GetString() ?? slotId;
        }

        string baseUrl = string.Empty;
        if (element.TryGetProperty("endpoint", out var endpointProp) && endpointProp.ValueKind == JsonValueKind.String)
        {
            baseUrl = endpointProp.GetString() ?? string.Empty;
        }

        string model = string.Empty;
        if (element.TryGetProperty("model", out var modelProp) && modelProp.ValueKind == JsonValueKind.String)
        {
            model = modelProp.GetString() ?? string.Empty;
        }

        string apiKeyEnv = string.Empty;
        if (element.TryGetProperty("api_key_env", out var apiKeyProp) && apiKeyProp.ValueKind == JsonValueKind.String)
        {
            apiKeyEnv = apiKeyProp.GetString() ?? string.Empty;
        }

        double temperature = 0.2;
        if (element.TryGetProperty("temperature", out var tempProp) && tempProp.TryGetDouble(out var temp))
        {
            temperature = temp;
        }

        string systemPrompt = string.Empty;
        if (element.TryGetProperty("system_prompt", out var promptProp) && promptProp.ValueKind == JsonValueKind.String)
        {
            systemPrompt = promptProp.GetString() ?? string.Empty;
        }

        return new AgentTemplate(display, slotId, baseUrl, model, apiKeyEnv, temperature, systemPrompt);
    }

    private async Task RefreshTemplateOptionsAsync()
    {
        var options = new List<TemplateOption>();  // Start empty - no static templates
        try
        {
            var url = $"{_config.DexterHttpUrl.TrimEnd('/')}/slots";
            var json = await _http.GetStringAsync(url);
            using var doc = JsonDocument.Parse(json);
            
            // Parse agents from dexter_config.yml format
            if (doc.RootElement.TryGetProperty("slots", out var slotsElement) && 
                slotsElement.ValueKind == JsonValueKind.Object)
            {
                foreach (var prop in slotsElement.EnumerateObject())
                {
                    var agentId = prop.Name;
                    var template = CreateTemplateFromSlot(agentId, prop.Value);
                    if (template != null)
                    {
                        var optionId = $"agent:{agentId}";
                        var displayName = template.DisplayName;
                        var provider = "";
                        
                        // Get provider from config
                        if (prop.Value.TryGetProperty("provider", out var providerProp) && 
                            providerProp.ValueKind == JsonValueKind.String)
                        {
                            provider = providerProp.GetString() ?? "";
                        }
                        
                        // Format: "Dexter (Gemini)" or "BSM (OpenAI)"
                        var label = string.IsNullOrEmpty(provider) 
                            ? displayName 
                            : $"{displayName} ({provider})";
                        
                        options.Add(new TemplateOption(optionId, label, template, "Agents"));
                    }
                }
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[Dexter] Failed to refresh agent templates: {ex.Message}");
        }

        UpdateTemplateOptions(options);
    }

    private void UpdateTemplateOptions(IEnumerable<TemplateOption> options)
    {
        void Apply()
        {
            _templateOptions.Clear();
            _templateIndex.Clear();
            foreach (var option in options)
            {
                _templateOptions.Add(option);
                _templateIndex[option.OptionId] = option;
            }

            foreach (var tab in _tabs)
            {
                TryAssignTemplateToTab(tab);
            }
        }

        if (Dispatcher.CheckAccess())
        {
            Apply();
        }
        else
        {
            Dispatcher.Invoke(Apply);
        }
    }

    private void TryAssignTemplateToTab(AgentTabViewModel tab)
    {
        if (!string.IsNullOrWhiteSpace(tab.SelectedTemplateId) && _templateIndex.ContainsKey(tab.SelectedTemplateId))
        {
            return;
        }

        var match = FindMatchingTemplate(tab);
        if (match != null)
        {
            _suppressTemplateSelection = true;
            tab.SelectedTemplateId = match.OptionId;
            _suppressTemplateSelection = false;
        }
    }

    internal TemplateOption? FindMatchingTemplate(AgentTabViewModel tab)
    {
        foreach (var option in _templateOptions)
        {
            if (TemplateMatches(option.Template, tab))
            {
                return option;
            }
        }
        return null;
    }

    private TemplateOption? GetPreferredTemplateOption()
    {
        if (_templateIndex.TryGetValue("slot:default_slot", out var defaultOption))
        {
            return defaultOption;
        }
        return _templateOptions.FirstOrDefault();
    }

    private void ApplyTemplateToTab(AgentTabViewModel tab, TemplateOption option, bool overwriteName, bool logChange)
    {
        _suppressTemplateSelection = true;
        tab.SelectedTemplateId = option.OptionId;
        _suppressTemplateSelection = false;

        var template = option.Template;
        if (overwriteName || string.IsNullOrWhiteSpace(tab.DisplayName) || tab.DisplayName.StartsWith("Agent ", StringComparison.OrdinalIgnoreCase))
        {
            tab.DisplayName = template.DisplayName;
        }
        tab.BaseUrl = template.BaseUrl;
        tab.ApiKeyEnv = template.ApiKeyEnv;
        tab.Model = template.Model;
        tab.Temperature = template.Temperature;
        tab.SystemPrompt = template.SystemPrompt;
        tab.SessionId = template.SessionId;

        if (logChange)
        {
            tab.AppendLog($"[template] applied {option.DisplayName}");
        }

        PersistState();
    }

    internal void ApplyTemplateById(AgentTabViewModel tab, string optionId, bool overwriteName, bool logChange)
    {
        if (_templateIndex.TryGetValue(optionId, out var option))
        {
            ApplyTemplateToTab(tab, option, overwriteName, logChange);
        }
    }

    public void LoadFromStore()
    {
        _tabs.Clear();
        var settings = _store.State.Agents ?? new System.Collections.Generic.List<AgentTabSettings>();
        foreach (var s in settings)
        {
            var vm = new AgentTabViewModel(s);
            vm.PropertyChanged += OnTabPropertyChanged;
            _tabs.Add(vm);
            TryAssignTemplateToTab(vm);
        }

        if (_tabs.Count == 0)
        {
            var preferred = GetPreferredTemplateOption();
            AgentTabViewModel vm;
            if (preferred != null)
            {
                vm = CreateViewModelFromOption(preferred);
            }
            else
            {
                vm = CreateCustomViewModel("Agent 1");
            }
            vm.PropertyChanged += OnTabPropertyChanged;
            _tabs.Add(vm);
        }

        SelectedTab = _tabs.FirstOrDefault();
    }

    private void PersistState()
    {
        _store.State.Agents = _tabs.Select(tab =>
        {
            tab.SyncToSettings();
            var settings = tab.Settings;
            return new AgentTabSettings
            {
                TabId = settings.TabId,
                DisplayName = settings.DisplayName,
                BaseUrl = settings.BaseUrl,
                ApiKeyEnv = settings.ApiKeyEnv,
                Model = settings.Model,
                Temperature = settings.Temperature,
                SystemPrompt = settings.SystemPrompt,
                SessionId = settings.SessionId,
                TargetTitleFallback = settings.TargetTitleFallback,
                MonitorEnabled = settings.MonitorEnabled,
                TemplateId = settings.TemplateId
            };
        }).ToList();
        _store.Save();
    }

    public AgentTabViewModel AddTab()
    {
        AgentTabViewModel vm;
        var preferred = GetPreferredTemplateOption();
        if (preferred != null)
        {
            vm = CreateViewModelFromOption(preferred);
        }
        else
        {
            vm = CreateCustomViewModel($"Agent {_tabs.Count + 1}");
        }

        vm.PropertyChanged += OnTabPropertyChanged;
        _tabs.Add(vm);
        SelectedTab = vm;
        PersistState();
        return vm;
    }

    private AgentTabViewModel CreateCustomViewModel(string name)
    {
        var settings = new AgentTabSettings
        {
            DisplayName = name,
            BaseUrl = string.Empty,
            ApiKeyEnv = string.Empty,
            Model = string.Empty,
            Temperature = 0.2,
            SystemPrompt = string.Empty,
            SessionId = "local",
            TargetTitleFallback = string.Empty,
            MonitorEnabled = false,
            TemplateId = null
        };
        return new AgentTabViewModel(settings);
    }

    private AgentTabViewModel CreateViewModelFromOption(TemplateOption option)
    {
        var template = option.Template;
        var settings = new AgentTabSettings
        {
            DisplayName = template.DisplayName,
            SessionId = template.SessionId,
            BaseUrl = template.BaseUrl,
            ApiKeyEnv = template.ApiKeyEnv,
            Model = template.Model,
            Temperature = template.Temperature,
            SystemPrompt = template.SystemPrompt,
            TargetTitleFallback = string.Empty,
            MonitorEnabled = false,
            TemplateId = option.OptionId
        };
        var vm = new AgentTabViewModel(settings)
        {
            SelectedTemplateId = option.OptionId
        };
        return vm;
    }

    private static bool TemplateMatches(AgentTemplate template, AgentTabViewModel vm)
    {
        return string.Equals(template.Model, vm.Model, StringComparison.OrdinalIgnoreCase)
               && string.Equals(template.BaseUrl, vm.BaseUrl, StringComparison.OrdinalIgnoreCase);
    }

    public void RemoveTab(AgentTabViewModel tab)
    {
        StopMonitor(tab.TabId, false);
        tab.PropertyChanged -= OnTabPropertyChanged;
        _tabs.Remove(tab);
        PersistState();
        if (_tabs.Count == 0)
        {
            AddTab();
        }
        else
        {
            SelectedTab = _tabs.FirstOrDefault();
        }
    }

    private void OnTabPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (sender is AgentTabViewModel vm)
        {
            switch (e.PropertyName)
            {
                case nameof(AgentTabViewModel.DisplayName):
                case nameof(AgentTabViewModel.BaseUrl):
                case nameof(AgentTabViewModel.ApiKeyEnv):
                case nameof(AgentTabViewModel.Model):
                case nameof(AgentTabViewModel.Temperature):
                case nameof(AgentTabViewModel.SystemPrompt):
                case nameof(AgentTabViewModel.SessionId):
                case nameof(AgentTabViewModel.TargetTitleFallback):
                    PersistState();
                    break;
                case nameof(AgentTabViewModel.MonitorEnabled):
                    if (vm.MonitorEnabled)
                    {
                        StartMonitor(vm, true);
                    }
                    else
                    {
                        StopMonitor(vm.TabId, true);
                    }
                    PersistState();
                    break;
            }
        }
    }

    private void OnConfigurationChanged(object? sender, EventArgs e)
    {
        RaiseConnectionStatus("WS reconnecting...");
        Dispatcher.InvokeAsync(() => _ = ReconnectAsync());
    }

    private void RaiseConnectionStatus(string status)
    {
        ConnectionStatusChanged?.Invoke(this, status);
    }

    private async Task<bool> EnsureConnectedAsync()
    {
        if (_ws != null && _ws.State == WebSocketState.Open)
        {
            return true;
        }

        _receiveCts?.Cancel();
        _receiveCts = null;
        _ws?.Dispose();
        _ws = new ClientWebSocket();
        try
        {
            await _ws.ConnectAsync(new Uri(_config.DexterWsUrl), CancellationToken.None);
            RaiseConnectionStatus($"WS connected ({_config.DexterWsUrl})");
        }
        catch (Exception ex)
        {
            _ws.Dispose();
            _ws = null;
            RaiseConnectionStatus($"WS connect failed: {ex.Message}");
            return false;
        }

        _receiveCts = new CancellationTokenSource();
        _ = Task.Run(() => ReceiveLoopAsync(_receiveCts.Token));
        return true;
    }

    private async Task ReconnectAsync()
    {
        if (await EnsureConnectedAsync())
        {
            return;
        }
    }

    private async Task ReceiveLoopAsync(CancellationToken token)
    {
        var buffer = new byte[65536];
        try
        {
            while (!token.IsCancellationRequested && _ws != null)
            {
                var result = await _ws.ReceiveAsync(buffer, token);
                if (result.MessageType == WebSocketMessageType.Close)
                {
                    RaiseConnectionStatus("WS disconnected");
                    break;
                }
                if (result.MessageType == WebSocketMessageType.Text)
                {
                    var text = Encoding.UTF8.GetString(buffer, 0, result.Count);
                    Dispatcher.Invoke(() => AppendEffectLog(text));
                }
            }
        }
        catch (OperationCanceledException)
        {
        }
        catch (WebSocketException ex)
        {
            RaiseConnectionStatus($"WS error: {ex.Message}");
        }
    }

    private void AppendEffectLog(string message)
    {
        try
        {
            var root = JsonNode.Parse(message) as JsonObject;
            if (root is null)
            {
                SelectedTab?.AppendLog($"[effect] {message}");
                return;
            }

            var payload = root["payload"] as JsonObject ?? root;
            var intentNode = payload["intent"] as JsonObject;
            if (intentNode is null)
            {
                SelectedTab?.AppendLog($"[effect] {payload.ToJsonString()}");
                return;
            }

            var metaNode = intentNode["meta"] as JsonObject;
            var tab = LocateTab(metaNode);
            if (tab == null)
            {
                return;
            }

            var status = payload["status"]?.GetValue<string>() ?? "ok";
            var kind = intentNode["kind"]?.GetValue<string>() ?? "unknown";
            var detail = payload["detail"] as JsonObject;
            string detailText = string.Empty;
            if (detail is not null)
            {
                if (detail.TryGetPropertyValue("text", out var textNode) && textNode is JsonValue tv && tv.TryGetValue<string>(out var txtVal))
                {
                    detailText = txtVal;
                }
                else if (detail.TryGetPropertyValue("reason", out var reasonNode) && reasonNode is JsonValue rv && rv.TryGetValue<string>(out var reason))
                {
                    detailText = reason;
                }
                else if (detail.TryGetPropertyValue("error", out var errorNode) && errorNode is JsonValue ev && ev.TryGetValue<string>(out var err))
                {
                    detailText = err;
                }
            }

            if (string.Equals(kind, "ocr", StringComparison.OrdinalIgnoreCase) && !string.IsNullOrEmpty(detailText))
            {
                HandleOcrEffect(tab, detailText);
                return;
            }

            var summary = BuildEffectSummary(status, kind, detailText);
            if (status == "error" || status == "denied")
            {
                tab.AppendError(summary);
            }
            tab.AppendLog(summary);
            ChatMessageRaised?.Invoke(this, new ChatMessageEventArgs(tab, summary, ChatMessageDirection.Incoming));
        }
        catch (Exception ex)
        {
            var errorMessage = $"[effect-error] {ex.Message}";
            SelectedTab?.AppendError(errorMessage);
            SelectedTab?.AppendLog(errorMessage);
        }
    }

    private static string BuildEffectSummary(string status, string kind, string detail)
    {
        var prefix = status switch
        {
            "ok" => "[ok]",
            "denied" => "[denied]",
            "error" => "[error]",
            "unknown_intent" => "[unknown]",
            _ => "[effect]"
        };
        if (!string.IsNullOrWhiteSpace(detail))
        {
            return $"{prefix} {kind} :: {detail}";
        }
        return $"{prefix} {kind}";
    }

    private AgentTabViewModel? LocateTab(JsonObject? meta)
    {
        if (meta == null)
        {
            return SelectedTab;
        }

        string? agentId = GetString(meta, "agent_id") ?? GetString(meta, "agent_tab_id");
        if (!string.IsNullOrWhiteSpace(agentId))
        {
            var tab = _tabs.FirstOrDefault(t => string.Equals(t.TabId, agentId, StringComparison.OrdinalIgnoreCase));
            if (tab != null)
            {
                return tab;
            }
        }

        string? sessionId = GetString(meta, "session_id");
        if (!string.IsNullOrWhiteSpace(sessionId))
        {
            var tab = _tabs.FirstOrDefault(t => string.Equals(t.SessionId, sessionId, StringComparison.OrdinalIgnoreCase));
            if (tab != null)
            {
                return tab;
            }
        }

        return SelectedTab;
    }

    private static string? GetString(JsonObject? obj, string property)
    {
        if (obj == null)
        {
            return null;
        }
        if (obj.TryGetPropertyValue(property, out var node) && node is JsonValue val && val.TryGetValue<string>(out var text))
        {
            return text;
        }
        return null;
    }

    private async Task SendIntentAsync(JsonObject intent)
    {
        if (!await EnsureConnectedAsync() || _ws == null)
        {
            return;
        }

        var payload = JsonSerializer.Serialize(new { type = "intent", intent });
        var bytes = Encoding.UTF8.GetBytes(payload);
        await _sendGate.WaitAsync();
        try
        {
            await _ws.SendAsync(bytes, WebSocketMessageType.Text, true, CancellationToken.None);
        }
        finally
        {
            _sendGate.Release();
        }
    }

    public async Task SendNaturalLanguageAsync(AgentTabViewModel tab, string text, string origin)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return;
        }

        tab.CommandText = string.Empty;
        tab.AppendLog($"[nl] {text}");
        ChatMessageRaised?.Invoke(this, new ChatMessageEventArgs(tab, text, ChatMessageDirection.Outgoing));
        var args = new JsonObject
        {
            ["text"] = text
        };
        var intent = BuildIntent("nl_command", args, tab, includePlanner: true);
        await SendIntentAsync(intent);
    }

    public async Task SendTypeTextAsync(AgentTabViewModel tab, string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return;
        }

        // Focus the docked window before typing
        _dockHost?.FocusDockedWindow();

        var args = new JsonObject { ["text"] = text };
        var intent = BuildIntent("type_text", args, tab);
        tab.AppendLog($"[type] {text}");
        await SendIntentAsync(intent);
    }

    public async Task SendHotkeyAsync(AgentTabViewModel tab, string chord)
    {
        if (string.IsNullOrWhiteSpace(chord))
        {
            return;
        }

        // Focus the docked window before sending hotkey
        _dockHost?.FocusDockedWindow();

        var args = new JsonObject { ["chord"] = chord };
        var intent = BuildIntent("hotkey", args, tab);
        tab.AppendLog($"[hotkey] {chord}");
        await SendIntentAsync(intent);
    }

    public async Task SaveSlotAsync(AgentTabViewModel tab)
    {
        var templateId = tab.SelectedTemplateId;
        if (string.IsNullOrWhiteSpace(templateId) || !templateId.StartsWith("slot:", StringComparison.OrdinalIgnoreCase))
        {
            MessageBox.Show("Select a slot preset before saving.", "Dexter", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        var slotId = templateId.Substring(5);
        var payload = new
        {
            slot_id = slotId,
            label = string.IsNullOrWhiteSpace(tab.DisplayName) ? null : tab.DisplayName,
            endpoint = string.IsNullOrWhiteSpace(tab.BaseUrl) ? null : tab.BaseUrl,
            api_key_env = string.IsNullOrWhiteSpace(tab.ApiKeyEnv) ? null : tab.ApiKeyEnv,
            model = string.IsNullOrWhiteSpace(tab.Model) ? null : tab.Model,
            temperature = tab.Temperature,
            system_prompt = string.IsNullOrWhiteSpace(tab.SystemPrompt) ? null : tab.SystemPrompt
        };

        try
        {
            var url = $"{_config.DexterHttpUrl.TrimEnd('/')}/slot/set";
            var json = JsonSerializer.Serialize(payload);
            using var content = new StringContent(json, Encoding.UTF8, "application/json");
            var response = await _http.PostAsync(url, content);
            var body = await response.Content.ReadAsStringAsync();
            if (!response.IsSuccessStatusCode)
            {
                MessageBox.Show($"Save failed: {response.StatusCode} {body}", "Dexter", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }
            tab.AppendLog($"[slot] saved {slotId}");
            await RefreshTemplateOptionsAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Save failed: {ex.Message}", "Dexter", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    public async Task RequestOcrForDockedWindowAsync(AgentTabViewModel tab)
    {
        if (_dockHost == null || !_dockHost.HasDockedWindow || !_dockHost.TryGetDockedBounds(out var rect))
        {
            MessageBox.Show("No docked window detected.", "Dexter", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        var args = new JsonObject { ["bounds"] = new JsonArray(rect.Left, rect.Top, rect.Right, rect.Bottom) };
        var intent = BuildIntent("ocr", args, tab);
        tab.AppendLog("[ocr] requested");
        await SendIntentAsync(intent);
    }

    private JsonObject BuildIntent(string kind, JsonObject args, AgentTabViewModel tab, bool includePlanner = false)
    {
        var meta = BuildMeta(tab, includePlanner);
        var intent = new JsonObject
        {
            ["kind"] = kind,
            ["args"] = args,
            ["meta"] = meta
        };
        IntentMetaHelper.ApplyDefaultCockpitMeta(intent);
        return intent;
    }

    private JsonObject BuildMeta(AgentTabViewModel tab, bool includePlanner)
    {
        var meta = new JsonObject
        {
            ["agent_id"] = tab.TabId,
            ["agent_tab_id"] = tab.TabId,
            ["session_id"] = tab.SessionId
        };

        ApplyTarget(meta, tab);

        if (includePlanner)
        {
            if (!string.IsNullOrWhiteSpace(tab.BaseUrl)) meta["base_url"] = tab.BaseUrl;
            if (!string.IsNullOrWhiteSpace(tab.ApiKeyEnv)) meta["api_key_env"] = tab.ApiKeyEnv;
            if (!string.IsNullOrWhiteSpace(tab.Model)) meta["model"] = tab.Model;
            meta["temperature"] = tab.Temperature;
            if (!string.IsNullOrWhiteSpace(tab.SystemPrompt)) meta["system_prompt"] = tab.SystemPrompt;
        }

        return meta;
    }

    private void ApplyTarget(JsonObject meta, AgentTabViewModel tab)
    {
        string? title = null;
        if (_dockHost != null && _dockHost.HasDockedWindow && _dockHost.TryGetSnapshot(out var snapshot))
        {
            meta["hwnd"] = $"HWND:{snapshot.Handle.ToInt64()}";
            if (!string.IsNullOrWhiteSpace(snapshot.Title))
            {
                title = snapshot.Title;
            }
            if (_dockHost.TryGetDockedBounds(out var rect))
            {
                meta["target_bounds"] = new JsonArray(rect.Left, rect.Top, rect.Right, rect.Bottom);
            }
        }

        if (string.IsNullOrWhiteSpace(title))
        {
            title = tab.TargetTitleFallback;
        }

        if (!string.IsNullOrWhiteSpace(title))
        {
            meta["target_title"] = title;
        }
    }

    private async void OnSaveSlot(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is AgentTabViewModel tab)
        {
            await SaveSlotAsync(tab);
        }
    }

    private void OnPresetSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_suppressTemplateSelection)
        {
            return;
        }

        if (sender is ComboBox combo && combo.DataContext is AgentTabViewModel tab && combo.SelectedItem is TemplateOption option)
        {
            ApplyTemplateToTab(tab, option, overwriteName: true, logChange: true);
        }
    }

    private void OnPopOutTab(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is AgentTabViewModel tab)
        {
            ShowFloatingWindow(tab);
        }
    }

    private void ShowFloatingWindow(AgentTabViewModel tab)
    {
        if (_floatingWindows.TryGetValue(tab.TabId, out var existing))
        {
            if (existing.IsVisible)
            {
                existing.Activate();
                return;
            }
            _floatingWindows.Remove(tab.TabId);
        }

        var window = new AgentSlotWindow(this, tab)
        {
            Owner = Window.GetWindow(this)
        };
        window.Closed += (_, __) => _floatingWindows.Remove(tab.TabId);
        _floatingWindows[tab.TabId] = window;
        window.Show();
    }

    private async void OnSendNlCommand(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is AgentTabViewModel tab)
        {
            var text = tab.CommandText.Trim();
            if (string.IsNullOrWhiteSpace(text)) return;
            await SendNaturalLanguageAsync(tab, text, "Tab");
        }
    }

    private async void OnQuickType(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is AgentTabViewModel tab)
        {
            var text = tab.QuickTypeText;
            await SendTypeTextAsync(tab, text);
            tab.QuickTypeText = string.Empty;
        }
    }

    private async void OnQuickHotkey(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is AgentTabViewModel tab)
        {
            var chord = tab.QuickHotkeyChord?.Trim();
            await SendHotkeyAsync(tab, chord ?? string.Empty);
            tab.QuickHotkeyChord = string.Empty;
        }
    }

    private async void OnOcrDocked(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is AgentTabViewModel tab)
        {
            await RequestOcrForDockedWindowAsync(tab);
        }
    }

    private void OnClearLog(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is AgentTabViewModel tab)
        {
            tab.LogText = string.Empty;
            tab.ClearErrors();
        }
    }

    private void OnClearErrors(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is AgentTabViewModel tab)
        {
            tab.ClearErrors();
        }
    }

    private void OnRemoveTab(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is AgentTabViewModel tab)
        {
            if (MessageBox.Show($"Remove '{tab.DisplayName}'?", "Dexter", MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes)
            {
                RemoveTab(tab);
            }
        }
    }

    private void OnMonitorToggle(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is AgentTabViewModel tab)
        {
            if (tab.MonitorEnabled)
            {
                StartMonitor(tab, true);
            }
            else
            {
                StopMonitor(tab.TabId, true);
            }
            PersistState();
        }
    }

    private void StartMonitor(AgentTabViewModel tab, bool immediate)
    {
        if (!_monitorTimers.TryGetValue(tab.TabId, out var timer))
        {
            timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(3) };
            timer.Tick += async (_, __) => await SendMonitorOcrAsync(tab);
            _monitorTimers[tab.TabId] = timer;
        }
        timer.Stop();
        timer.Start();
        tab.AppendLog("[monitor] started");
        if (immediate)
        {
            _ = SendMonitorOcrAsync(tab, true);
        }
    }

    private void StopMonitor(string tabId, bool log)
    {
        if (_monitorTimers.Remove(tabId, out var timer))
        {
            timer.Stop();
        }
        if (log)
        {
            var tab = _tabs.FirstOrDefault(t => t.TabId == tabId);
            tab?.AppendLog("[monitor] stopped");
        }
    }

    private void RaiseTabsMetadataChanged()
    {
        TabsMetadataChanged?.Invoke(this, EventArgs.Empty);
    }

    private async Task SendMonitorOcrAsync(AgentTabViewModel tab, bool immediate = false)
    {
        if (!tab.MonitorEnabled)
        {
            StopMonitor(tab.TabId, false);
            return;
        }

        if (_dockHost == null || !_dockHost.HasDockedWindow || !_dockHost.TryGetDockedBounds(out var rect))
        {
            if (immediate)
            {
                tab.AppendLog("[monitor] waiting for docked window...");
            }
            return;
        }

        var args = new JsonObject { ["bounds"] = new JsonArray(rect.Left, rect.Top, rect.Right, rect.Bottom) };
        var intent = BuildIntent("ocr", args, tab);
        await SendIntentAsync(intent);
    }

    private void HandleOcrEffect(AgentTabViewModel tab, string text)
    {
        if (_lastOcrByTab.TryGetValue(tab.TabId, out var last) && string.Equals(last, text, StringComparison.Ordinal))
        {
            return;
        }
        _lastOcrByTab[tab.TabId] = text;
        tab.AppendLog("[ocr] " + TrimSnippet(text, 160));
        ChatMessageRaised?.Invoke(this, new ChatMessageEventArgs(tab, text, ChatMessageDirection.Incoming));
    }

    private static string TrimSnippet(string text, int maxLength = 120)
    {
        var normalized = text.Replace("\r\n", " ").Replace('\n', ' ').Replace('\r', ' ').Trim();
        if (normalized.Length > maxLength)
        {
            normalized = normalized.Substring(0, maxLength).TrimEnd() + "...";
        }
        return normalized;
    }

    private async void OnCommandTextKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter && !Keyboard.Modifiers.HasFlag(ModifierKeys.Shift))
        {
            e.Handled = true;
            if (sender is FrameworkElement element && element.DataContext is AgentTabViewModel tab)
            {
                var text = tab.CommandText.Trim();
                if (string.IsNullOrWhiteSpace(text)) return;
                await SendNaturalLanguageAsync(tab, text, "Tab");
            }
        }
    }

    protected virtual void OnPropertyChanged(string propertyName)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
}

public enum ChatMessageDirection
{
    Outgoing,
    Incoming
}

public sealed class ChatMessageEventArgs : EventArgs
{
    public ChatMessageEventArgs(AgentTabViewModel tab, string message, ChatMessageDirection direction)
    {
        Tab = tab;
        Message = message;
        Direction = direction;
    }

    public AgentTabViewModel Tab { get; }
    public string Message { get; }
    public ChatMessageDirection Direction { get; }
}
