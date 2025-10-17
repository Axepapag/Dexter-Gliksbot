using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using DexterCockpit.Services;

namespace DexterCockpit;

public partial class PolicyEditorControl : UserControl
{
    private readonly AppConfiguration _config = AppConfiguration.Instance;
    private readonly HttpClient _http = new();

    private readonly Dictionary<string, ProfileModel> _profiles = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, CatalogGroup> _catalogGroups = new(StringComparer.OrdinalIgnoreCase);

    private ProfileModel? _currentProfile;
    private string _activeProfileId = string.Empty;
    private bool _isLoading;
    private bool _suppressCatalogEvents;

    public PolicyEditorControl()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
        _config.ConfigurationChanged += OnConfigurationChanged;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        _ = ReloadAsync();
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        _config.ConfigurationChanged -= OnConfigurationChanged;
    }

    private void OnConfigurationChanged(object? sender, EventArgs e)
    {
        Dispatcher.Invoke(() => _ = ReloadAsync());
    }

    private async Task ReloadAsync()
    {
        if (_isLoading)
        {
            return;
        }

        _isLoading = true;
        try
        {
            StatusText.Text = "Loading policy presets...";
            var baseUrl = _config.DexterHttpUrl.TrimEnd('/');
            var url = $"{baseUrl}/policy/presets";
            var request = new HttpRequestMessage(HttpMethod.Get, url);
            request.Headers.TryAddWithoutValidation("X-Dexter-Protocol", "v1");

            var response = await _http.SendAsync(request);
            response.EnsureSuccessStatusCode();

            await using var stream = await response.Content.ReadAsStreamAsync();
            using var document = await JsonDocument.ParseAsync(stream);
            ApplyPresets(document.RootElement);

            StatusText.Text = "Policy presets loaded.";
        }
        catch (Exception ex)
        {
            StatusText.Text = $"Load failed: {ex.Message}";
        }
        finally
        {
            _isLoading = false;
        }
    }

    private void ApplyPresets(JsonElement root)
    {
        _profiles.Clear();
        ProfileCombo.Items.Clear();

        _activeProfileId = root.GetPropertyOrDefault("mode", string.Empty);

        if (root.TryGetProperty("profiles", out var profilesElement) && profilesElement.ValueKind == JsonValueKind.Object)
        {
            foreach (var prop in profilesElement.EnumerateObject())
            {
                var id = prop.Name;
                var value = prop.Value;
                var label = value.GetPropertyOrDefault("label", CultureInfo.InvariantCulture.TextInfo.ToTitleCase(id));
                var description = value.GetPropertyOrDefault("description", string.Empty);
                var policyNode = value.TryGetProperty("policy", out var policyElement)
                    ? JsonNode.Parse(policyElement.GetRawText())?.AsObject()
                    : new JsonObject();
                if (policyNode == null)
                {
                    policyNode = new JsonObject();
                }

                var model = new ProfileModel(id, label, description, policyNode);
                _profiles[id] = model;

                var comboItem = new ComboBoxItem
                {
                    Content = $"{label} ({id})",
                    Tag = id
                };
                ProfileCombo.Items.Add(comboItem);
            }
        }

        BuildCatalog(root);

        if (ProfileCombo.Items.Count > 0)
        {
            var targetId = _activeProfileId;
            if (!_profiles.ContainsKey(targetId))
            {
                targetId = _profiles.Keys.First();
            }
            SelectProfile(targetId);
            ProfileCombo.SelectedItem = ProfileCombo.Items
                .OfType<ComboBoxItem>()
                .FirstOrDefault(item => string.Equals(item.Tag as string, targetId, StringComparison.OrdinalIgnoreCase));
        }
        else
        {
            ProfileDescription.Text = "No profiles defined.";
            PolicyText.Clear();
            RuleCountsText.Text = string.Empty;
        }

        HealthText.Text = $"Active profile: {_activeProfileId}";
    }

    private void BuildCatalog(JsonElement root)
    {
        _catalogGroups.Clear();

        while (CatalogContainer.Children.Count > 2)
        {
            CatalogContainer.Children.RemoveAt(2);
        }

        if (!root.TryGetProperty("catalog", out var catalogElement) || catalogElement.ValueKind != JsonValueKind.Object)
        {
            CatalogHint.Text = "No catalog entries available. Edit the policy using the JSON view.";
            return;
        }

        CatalogHint.Text = "Toggle the checklists to adjust deny rules. Save to persist, Activate to set the live mode.";

        foreach (var categoryProperty in catalogElement.EnumerateObject())
        {
            var categoryId = categoryProperty.Name;
            var entriesElement = categoryProperty.Value;
            if (entriesElement.ValueKind != JsonValueKind.Array)
            {
                continue;
            }

            var group = new CatalogGroup(categoryId);
            var expander = new Expander
            {
                Header = group.DisplayName,
                IsExpanded = categoryId.Equals("process", StringComparison.OrdinalIgnoreCase)
            };
            expander.Margin = new Thickness(0, 0, 0, 12);
            var panel = new StackPanel();

            foreach (var entryElement in entriesElement.EnumerateArray())
            {
                if (entryElement.ValueKind != JsonValueKind.Object)
                {
                    continue;
                }

                var entry = new CatalogEntry(
                    entryElement.GetPropertyOrDefault("id", Guid.NewGuid().ToString()),
                    entryElement.GetPropertyOrDefault("label", "Unknown"),
                    entryElement.GetPropertyOrDefault("path", string.Empty),
                    entryElement.GetPropertyOrDefault("value", string.Empty));

                if (string.IsNullOrWhiteSpace(entry.Path) || string.IsNullOrWhiteSpace(entry.Value))
                {
                    continue;
                }

                if (entryElement.TryGetProperty("extras", out var extrasElement) && extrasElement.ValueKind == JsonValueKind.Array)
                {
                    foreach (var extra in extrasElement.EnumerateArray())
                    {
                        if (extra.ValueKind == JsonValueKind.String)
                        {
                            entry.Extras.Add(extra.GetString()!);
                        }
                    }
                }

                var checkbox = new CheckBox
                {
                    Content = entry.Label,
                    Tag = entry,
                    Margin = new Thickness(0, 2, 0, 2)
                };
                checkbox.Checked += OnCatalogToggle;
                checkbox.Unchecked += OnCatalogToggle;
                entry.CheckBox = checkbox;

                group.Entries.Add(entry);
                panel.Children.Add(checkbox);
            }

            if (group.Entries.Count == 0)
            {
                continue;
            }

            expander.Content = panel;
            group.Expander = expander;
            _catalogGroups[group.Name] = group;
            CatalogContainer.Children.Add(expander);
        }
    }

    private void SelectProfile(string profileId)
    {
        if (!_profiles.TryGetValue(profileId, out var model))
        {
            return;
        }

        _currentProfile = model;
        ProfileDescription.Text = model.Description;
        UpdatePolicyText(model.Policy);
        UpdateRuleCounts(model.Policy);

        _suppressCatalogEvents = true;
        try
        {
            foreach (var group in _catalogGroups.Values)
            {
                foreach (var entry in group.Entries)
                {
                    var isSelected = IsValueSelected(model.Policy, entry.Path, entry.Value);
                    entry.CheckBox.IsChecked = isSelected;
                }
            }
        }
        finally
        {
            _suppressCatalogEvents = false;
        }
    }

    private void UpdatePolicyText(JsonObject policy)
    {
        var json = JsonSerializer.Serialize(policy, new JsonSerializerOptions
        {
            WriteIndented = true
        });
        PolicyText.Text = json;
    }

    private void UpdateRuleCounts(JsonObject policy)
    {
        var builder = new StringBuilder();
        foreach (var kvp in policy)
        {
            if (kvp.Value is JsonObject section)
            {
                var sectionTotal = 0;
                foreach (var sectionProp in section)
                {
                    if (sectionProp.Value is JsonArray arr)
                    {
                        sectionTotal += arr.Count;
                    }
                }

                if (sectionTotal > 0)
                {
                    if (builder.Length > 0)
                    {
                        builder.Append(", ");
                    }
                    builder.Append($"{kvp.Key}: {sectionTotal}");
                }
            }
            else if (kvp.Value is JsonArray array)
            {
                if (builder.Length > 0)
                {
                    builder.Append(", ");
                }
                builder.Append($"{kvp.Key}: {array.Count}");
            }
        }

        RuleCountsText.Text = builder.Length > 0 ? $"Rule counts - {builder}" : "Rule counts - none";
    }

    private void OnCatalogToggle(object sender, RoutedEventArgs e)
    {
        if (_suppressCatalogEvents || _currentProfile == null)
        {
            return;
        }

        if (sender is not CheckBox checkbox || checkbox.Tag is not CatalogEntry entry)
        {
            return;
        }

        var shouldAdd = checkbox.IsChecked == true;
        ApplyCatalogEntry(_currentProfile.Policy, entry, shouldAdd);
        UpdatePolicyText(_currentProfile.Policy);
        UpdateRuleCounts(_currentProfile.Policy);
        StatusText.Text = shouldAdd
            ? $"Added '{entry.Label}' to {_currentProfile.Label}."
            : $"Removed '{entry.Label}' from {_currentProfile.Label}.";
    }

    private static void ApplyCatalogEntry(JsonObject policy, CatalogEntry entry, bool add)
    {
        if (add)
        {
            var array = EnsureArray(policy, entry.Path);
            AddUnique(array, entry.Value);
            foreach (var extra in entry.Extras)
            {
                AddUnique(array, extra);
            }
        }
        else
        {
            var node = GetNode(policy, entry.Path);
            if (node is JsonArray array)
            {
                RemoveValue(array, entry.Value);
                foreach (var extra in entry.Extras)
                {
                    RemoveValue(array, extra);
                }
            }
        }
    }

    private static bool IsValueSelected(JsonObject policy, string path, string value)
    {
        var node = GetNode(policy, path);
        if (node is JsonArray array)
        {
            return array.Any(item => item is JsonValue v && string.Equals(v.GetValue<string?>(), value, StringComparison.OrdinalIgnoreCase));
        }
        return false;
    }

    private static JsonNode? GetNode(JsonObject root, string path)
    {
        var parts = path.Split('.', StringSplitOptions.RemoveEmptyEntries);
        JsonNode? node = root;
        foreach (var part in parts)
        {
            if (node is JsonObject obj)
            {
                node = obj.TryGetPropertyValue(part, out var next) ? next : null;
            }
            else
            {
                return null;
            }
        }
        return node;
    }

    private static JsonArray EnsureArray(JsonObject root, string path)
    {
        var parts = path.Split('.', StringSplitOptions.RemoveEmptyEntries);
        JsonObject current = root;

        for (var i = 0; i < parts.Length; i++)
        {
            var key = parts[i];
            var isLast = i == parts.Length - 1;

            if (isLast)
            {
                if (current[key] is JsonArray array)
                {
                    return array;
                }
                var newArray = new JsonArray();
                current[key] = newArray;
                return newArray;
            }

            if (current[key] is JsonObject child)
            {
                current = child;
            }
            else
            {
                var next = new JsonObject();
                current[key] = next;
                current = next;
            }
        }

        return new JsonArray();
    }

    private static void AddUnique(JsonArray array, string value)
    {
        if (array.Any(item => item is JsonValue v && string.Equals(v.GetValue<string?>(), value, StringComparison.OrdinalIgnoreCase)))
        {
            return;
        }
        array.Add(value);
    }

    private static void RemoveValue(JsonArray array, string value)
    {
        for (var i = array.Count - 1; i >= 0; i--)
        {
            if (array[i] is JsonValue v && string.Equals(v.GetValue<string?>(), value, StringComparison.OrdinalIgnoreCase))
            {
                array.RemoveAt(i);
            }
        }
    }

    private async void OnReload(object sender, RoutedEventArgs e)
    {
        await ReloadAsync();
    }

    private async void OnSave(object sender, RoutedEventArgs e)
    {
        if (_currentProfile == null)
        {
            return;
        }

        try
        {
            var payload = new JsonObject
            {
                ["profile_id"] = _currentProfile.Id,
                ["label"] = _currentProfile.Label,
                ["description"] = _currentProfile.Description,
                ["policy"] = _currentProfile.Policy.DeepClone()
            };

            var baseUrl = _config.DexterHttpUrl.TrimEnd('/');
            var url = $"{baseUrl}/policy/profile/update";
            var response = await _http.PostAsJsonAsync(url, payload);
            response.EnsureSuccessStatusCode();

            StatusText.Text = $"Profile '{_currentProfile.Label}' saved.";
            await ReloadAsync();
        }
        catch (Exception ex)
        {
            StatusText.Text = $"Save failed: {ex.Message}";
        }
    }

    private async void OnActivate(object sender, RoutedEventArgs e)
    {
        if (_currentProfile == null)
        {
            return;
        }

        try
        {
            var baseUrl = _config.DexterHttpUrl.TrimEnd('/');
            var url = $"{baseUrl}/mode/set";
            var payload = new { mode = _currentProfile.Id };
            var response = await _http.PostAsJsonAsync(url, payload);
            response.EnsureSuccessStatusCode();

            _activeProfileId = _currentProfile.Id;
            HealthText.Text = $"Active profile: {_activeProfileId}";
            StatusText.Text = $"Activated profile '{_currentProfile.Label}'.";
        }
        catch (Exception ex)
        {
            StatusText.Text = $"Activate failed: {ex.Message}";
        }
    }

    private void OnProfileSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ProfileCombo.SelectedItem is ComboBoxItem item && item.Tag is string id)
        {
            SelectProfile(id);
        }
    }

    private sealed record ProfileModel(string Id, string Label, string Description, JsonObject Policy);

    private sealed class CatalogEntry
    {
        public CatalogEntry(string id, string label, string path, string value)
        {
            Id = id;
            Label = label;
            Path = path;
            Value = value;
        }

        public string Id { get; }
        public string Label { get; }
        public string Path { get; }
        public string Value { get; }
        public List<string> Extras { get; } = new();
        public CheckBox CheckBox { get; set; } = null!;
    }

    private sealed class CatalogGroup
    {
        public CatalogGroup(string name)
        {
            Name = name;
            DisplayName = CultureInfo.InvariantCulture.TextInfo.ToTitleCase(name.Replace('_', ' '));
        }

        public string Name { get; }
        public string DisplayName { get; }
        public List<CatalogEntry> Entries { get; } = new();
        public Expander Expander { get; set; } = null!;
    }
}

internal static class JsonElementExtensions
{
    public static string GetPropertyOrDefault(this JsonElement element, string propertyName, string defaultValue)
    {
        if (element.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String)
        {
            return property.GetString() ?? defaultValue;
        }
        return defaultValue;
    }
}
