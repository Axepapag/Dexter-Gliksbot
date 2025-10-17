using System;
using DexterCockpit.State;

namespace DexterCockpit.Services;

public sealed class AppConfiguration
{
    private static readonly Lazy<AppConfiguration> LazyInstance = new(() => new AppConfiguration());

    public static AppConfiguration Instance => LazyInstance.Value;

    private readonly CockpitStateStore _store = CockpitStateStore.Instance;

    private string _dexterHttpUrl = DefaultHttpUrl;
    private string _dexterWsUrl = DefaultWsUrl;

    public const string DefaultHttpUrl = "http://127.0.0.1:8765";
    public const string DefaultWsUrl = "ws://127.0.0.1:8765/ws";

    public event EventHandler? ConfigurationChanged;

    private AppConfiguration()
    {
        Reload();
    }

    public string DexterHttpUrl
    {
        get => _dexterHttpUrl;
        private set => _dexterHttpUrl = value;
    }

    public string DexterWsUrl
    {
        get => _dexterWsUrl;
        private set => _dexterWsUrl = value;
    }

    public void Reload()
    {
        var envHttp = Environment.GetEnvironmentVariable("DEXTER_HTTP_URL");
        var envWs = Environment.GetEnvironmentVariable("DEXTER_WS_URL");

        if (!string.IsNullOrWhiteSpace(envHttp))
        {
            DexterHttpUrl = envHttp;
        }
        else if (!string.IsNullOrWhiteSpace(_store.State.DexterHttpUrl))
        {
            DexterHttpUrl = _store.State.DexterHttpUrl!;
        }
        else
        {
            DexterHttpUrl = DefaultHttpUrl;
        }

        if (!string.IsNullOrWhiteSpace(envWs))
        {
            DexterWsUrl = envWs;
        }
        else if (!string.IsNullOrWhiteSpace(_store.State.DexterWsUrl))
        {
            DexterWsUrl = _store.State.DexterWsUrl!;
        }
        else
        {
            DexterWsUrl = DefaultWsUrl;
        }

        ConfigurationChanged?.Invoke(this, EventArgs.Empty);
    }

    public void Update(string httpUrl, string wsUrl)
    {
        if (string.IsNullOrWhiteSpace(httpUrl))
        {
            httpUrl = DefaultHttpUrl;
        }

        if (string.IsNullOrWhiteSpace(wsUrl))
        {
            wsUrl = DefaultWsUrl;
        }

        DexterHttpUrl = httpUrl;
        DexterWsUrl = wsUrl;

        _store.UpdateEndpoints(httpUrl, wsUrl);
        ConfigurationChanged?.Invoke(this, EventArgs.Empty);
    }
}
