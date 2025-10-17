using System;
using System.IO;
using System.Windows;

namespace DexterCockpit
{
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
            AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;
            DispatcherUnhandledException += OnDispatcherUnhandledException;
            base.OnStartup(e);
        }

        private void OnUnhandledException(object sender, UnhandledExceptionEventArgs e)
        {
            LogException(e.ExceptionObject as Exception);
        }

        private void OnDispatcherUnhandledException(object sender, System.Windows.Threading.DispatcherUnhandledExceptionEventArgs e)
        {
            LogException(e.Exception);
            e.Handled = true;
            MessageBox.Show($"Application error: {e.Exception.Message}\n\nSee crash.log for details.", "Dexter Cockpit Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }

        private void LogException(Exception? ex)
        {
            if (ex == null) return;
            
            var logPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "crash.log");
            var logMessage = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}]\n{ex}\n\n";
            File.AppendAllText(logPath, logMessage);
        }
    }
}