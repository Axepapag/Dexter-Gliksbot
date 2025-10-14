using System.Windows;
using DexterCockpit.ViewModels;
using Microsoft.Extensions.Logging;

namespace DexterCockpit;

/// <summary>
/// Interaction logic for MainWindow.xaml
/// </summary>
public partial class MainWindow : Window
{
    private readonly MainViewModel _viewModel;

    public MainWindow(MainViewModel viewModel)
    {
        InitializeComponent();
        _viewModel = viewModel;
        DataContext = _viewModel;

        // Initialize on load
        Loaded += async (s, e) => await _viewModel.InitializeAsync();

        // Cleanup on close
        Closing += (s, e) => _viewModel.Dispose();
    }
}
