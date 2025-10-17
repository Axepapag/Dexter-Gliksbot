using System;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using DexterCockpit.Docking;

namespace DexterCockpit;

public partial class WindowPickerDialog : Window
{
    private readonly Func<IReadOnlyList<WindowOption>> _dataProvider;
    private readonly ObservableCollection<WindowOption> _options = new();
    private readonly ICollectionView _view;

    public WindowPickerDialog(Func<IReadOnlyList<WindowOption>> dataProvider)
    {
        InitializeComponent();
        _dataProvider = dataProvider ?? throw new ArgumentNullException(nameof(dataProvider));
        WindowList.ItemsSource = _options;
        _view = CollectionViewSource.GetDefaultView(_options);
        _view.Filter = Filter;
    }

    public WindowOption? SelectedOption { get; private set; }

    protected override void OnContentRendered(EventArgs e)
    {
        base.OnContentRendered(e);
        RefreshOptions();
        SearchBox.Focus();
    }

    private void RefreshOptions()
    {
        _options.Clear();
        foreach (var option in _dataProvider().DistinctBy(o => (o.DisplayTitle, o.Handle, o.IsHistory)))
        {
            _options.Add(option);
        }
        _view.Refresh();
    }

    private bool Filter(object obj)
    {
        if (string.IsNullOrWhiteSpace(SearchBox.Text))
        {
            return true;
        }

        if (obj is not WindowOption option)
        {
            return false;
        }

        var term = SearchBox.Text.Trim();
        return (!string.IsNullOrWhiteSpace(option.DisplayTitle) &&
                option.DisplayTitle.IndexOf(term, StringComparison.OrdinalIgnoreCase) >= 0)
               || (!string.IsNullOrWhiteSpace(option.ProcessName) &&
                   option.ProcessName.IndexOf(term, StringComparison.OrdinalIgnoreCase) >= 0);
    }

    private void SearchBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        _view.Refresh();
    }

    private void BtnRefresh_Click(object sender, RoutedEventArgs e)
    {
        RefreshOptions();
    }

    private void BtnSelect_Click(object sender, RoutedEventArgs e)
    {
        AcceptSelection();
    }

    private void WindowList_MouseDoubleClick(object sender, System.Windows.Input.MouseButtonEventArgs e)
    {
        AcceptSelection();
    }

    private void AcceptSelection()
    {
        if (WindowList.SelectedItem is WindowOption option)
        {
            SelectedOption = option;
            DialogResult = true;
        }
    }
}
