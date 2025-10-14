using System;
using System.Windows;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using DexterCockpit.Services;
using DexterCockpit.ViewModels;

namespace DexterCockpit;

/// <summary>
/// Interaction logic for App.xaml
/// </summary>
public partial class App : Application
{
    private ServiceProvider? _serviceProvider;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // Setup Dependency Injection
        var services = new ServiceCollection();

        // Logging
        services.AddLogging(builder =>
        {
            builder.AddConsole();
            builder.AddDebug();
            builder.SetMinimumLevel(LogLevel.Information);
        });

        // Services
        services.AddSingleton<DexterApiClient>(sp =>
            new DexterApiClient("http://localhost:8765", sp.GetRequiredService<ILogger<DexterApiClient>>()));
        
        services.AddSingleton<DexterWebSocketClient>(sp =>
            new DexterWebSocketClient(sp.GetRequiredService<ILogger<DexterWebSocketClient>>()));

        // ViewModels
        services.AddSingleton<AgentRosterViewModel>();
        services.AddSingleton<LogsViewModel>();
        services.AddSingleton<ChatViewModel>();
        services.AddSingleton<PerformanceViewModel>();
        services.AddSingleton<MainViewModel>();

        // Main Window
        services.AddSingleton<MainWindow>();

        _serviceProvider = services.BuildServiceProvider();

        // Show Main Window
        var mainWindow = _serviceProvider.GetRequiredService<MainWindow>();
        mainWindow.Show();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _serviceProvider?.Dispose();
        base.OnExit(e);
    }
}
