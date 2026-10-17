using Library.Desktop.Pages;

namespace Library.Desktop;

public enum PlaybackState { Stopped, Playing, Paused }

public interface INavigator
{
    void Show(string page);
}

public class AppHost : INavigator
{
    private readonly Dictionary<string, Func<object>> _pages;

    public AppHost()
    {
        _pages = new()
        {
            ["search"] = () => new SearchPage(this),
            ["loans"] = () => new LoansPage(this),
            ["account"] = () => new AccountPage(this),
            ["listen"] = () => new ListenPage(this),
        };
    }

    public object? Current { get; private set; }
    public PlaybackState AudiobookState { get; set; } = PlaybackState.Stopped;

    public void Show(string page) => Current = _pages[page]();
}
