using System;
using System.ComponentModel;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using DexterCockpit.State;

namespace DexterCockpit;

public partial class AgentSlotWindow : Window
{
    private readonly AgentTabsControl _owner;
    private readonly AgentTabViewModel _tab;
    private bool _suppressTemplateEvents;

    public AgentSlotWindow(AgentTabsControl owner, AgentTabViewModel tab)
    {
        _owner = owner;
        _tab = tab;
        DataContext = tab;
        InitializeComponent();
        Title = $"Agent · {tab.DisplayName}";
        _tab.PropertyChanged += OnTabPropertyChanged;
        _suppressTemplateEvents = true;
        PresetCombo.SelectedValue = tab.SelectedTemplateId;
        _suppressTemplateEvents = false;
    }

    public System.Collections.ObjectModel.ObservableCollection<AgentTabsControl.TemplateOption> TemplateOptions => _owner.TemplateOptions;

    private async void OnSendNl(object sender, RoutedEventArgs e)
    {
        var text = _tab.CommandText?.Trim() ?? string.Empty;
        await _owner.SendNaturalLanguageAsync(_tab, text, "Window");
    }

    private async void OnNlKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter && !Keyboard.Modifiers.HasFlag(ModifierKeys.Shift))
        {
            e.Handled = true;
            var text = _tab.CommandText?.Trim() ?? string.Empty;
            await _owner.SendNaturalLanguageAsync(_tab, text, "Window");
        }
    }

    private async void OnSendType(object sender, RoutedEventArgs e)
    {
        var text = _tab.QuickTypeText ?? string.Empty;
        await _owner.SendTypeTextAsync(_tab, text);
        _tab.QuickTypeText = string.Empty;
    }

    private async void OnSendHotkey(object sender, RoutedEventArgs e)
    {
        var chord = _tab.QuickHotkeyChord ?? string.Empty;
        await _owner.SendHotkeyAsync(_tab, chord);
        _tab.QuickHotkeyChord = string.Empty;
    }

    private async void OnOcr(object sender, RoutedEventArgs e)
    {
        await _owner.RequestOcrForDockedWindowAsync(_tab);
    }

    private void OnClearLog(object sender, RoutedEventArgs e)
    {
        _tab.LogText = string.Empty;
    }

    private async void OnSaveSlot(object sender, RoutedEventArgs e)
    {
        await _owner.SaveSlotAsync(_tab);
    }

    private void OnPresetChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_suppressTemplateEvents)
        {
            return;
        }

        if (sender is ComboBox combo && combo.SelectedValue is string optionId)
        {
            _owner.ApplyTemplateById(_tab, optionId, overwriteName: true, logChange: true);
        }
    }

    private void OnCloseClick(object sender, RoutedEventArgs e)
    {
        Close();
    }

    private void OnTabPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(AgentTabViewModel.DisplayName))
        {
            Dispatcher.Invoke(() => Title = $"Agent · {_tab.DisplayName}");
        }

        if (e.PropertyName == nameof(AgentTabViewModel.SelectedTemplateId))
        {
            Dispatcher.Invoke(() =>
            {
                _suppressTemplateEvents = true;
                PresetCombo.SelectedValue = _tab.SelectedTemplateId;
                _suppressTemplateEvents = false;
            });
        }
    }

    protected override void OnClosed(EventArgs e)
    {
        base.OnClosed(e);
        _tab.PropertyChanged -= OnTabPropertyChanged;
    }

}
