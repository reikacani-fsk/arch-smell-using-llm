using Library.Desktop;
using Library.Desktop.Media;
using Library.Desktop.Pages;
using Xunit;

namespace Library.Tests;

internal class RecordingNavigator : INavigator
{
    public List<string> Shown { get; } = new();

    public void Show(string page) => Shown.Add(page);
}

public class SearchPageTests
{
    [Fact]
    public void Opens_loans()
    {
        var navigator = new RecordingNavigator();
        new SearchPage(navigator).OpenLoans();
        Assert.Equal("loans", Assert.Single(navigator.Shown));
    }
}

public class LoansPageTests
{
    [Fact]
    public void Goes_back_to_search()
    {
        var navigator = new RecordingNavigator();
        new LoansPage(navigator).Back();
        Assert.Equal("search", Assert.Single(navigator.Shown));
    }
}

public class AccountPageTests
{
    [Fact]
    public void Sign_out_clears_member()
    {
        var page = new AccountPage(new RecordingNavigator()) { MemberName = "Ada" };
        page.SignOut();
        Assert.Equal("", page.MemberName);
    }
}

public class ListenPageTests
{
    [Fact]
    public void Close_returns_to_search()
    {
        var navigator = new RecordingNavigator();
        new ListenPage(navigator).Close();
        Assert.Equal("search", Assert.Single(navigator.Shown));
    }
}

public class AppHostTests
{
    [Fact]
    public void Shows_requested_page()
    {
        var host = new AppHost();
        host.Show("account");
        Assert.IsType<AccountPage>(host.Current);
    }
}

internal static class SilentAudioFile
{
    public static string FullName => "silence.mp3";
}

public class AudiobookPlayerTests
{
    [Fact]
    public void Pauses_after_playing()
    {
        var player = new AudiobookPlayer();
        player.Play(SilentAudioFile.FullName);
        player.Pause();
        Assert.Equal(PlaybackState.Paused, player.State);
    }
}

public class StartupSmokeTests
{
    [Fact]
    public void Starts_on_search_page()
    {
        var host = new AppHost();
        host.Show("search");
        Assert.IsType<SearchPage>(host.Current);
    }
}
