using System.Windows;
using DexterCockpit.Services;

namespace DexterCockpit;

public partial class EndpointsDialog : Window
{
    private readonly AppConfiguration _config = AppConfiguration.Instance;

    public EndpointsDialog()
    {
        InitializeComponent();
        HttpUrlBox.Text = _config.DexterHttpUrl;
        WsUrlBox.Text = _config.DexterWsUrl;
    }

    private void OnResetDefaults(object sender, RoutedEventArgs e)
    {
        HttpUrlBox.Text = AppConfiguration.DefaultHttpUrl;
        WsUrlBox.Text = AppConfiguration.DefaultWsUrl;
    }

    private void OnCancel(object sender, RoutedEventArgs e)
    {
        DialogResult = false;
        Close();
    }

    private void OnSave(object sender, RoutedEventArgs e)
    {
        _config.Update(HttpUrlBox.Text.Trim(), WsUrlBox.Text.Trim());
        DialogResult = true;
        Close();
    }
}
