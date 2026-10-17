using Library.Desktop.Media;

namespace Library.Desktop.Pages;

public class SearchPage(INavigator navigator)
{
    public string Query { get; set; } = "";

    public void OpenLoans() => navigator.Show("loans");
}

public class LoansPage(INavigator navigator)
{
    public List<string> Isbns { get; } = new();

    public void Back() => navigator.Show("search");
}

public class AccountPage(INavigator navigator)
{
    public string MemberName { get; set; } = "";

    public void SignOut()
    {
        MemberName = "";
        navigator.Show("search");
    }
}

public class ListenPage(INavigator navigator)
{
    private readonly AudiobookPlayer _player = new();

    public void Play(string file) => _player.Play(file);

    public void Close()
    {
        _player.Pause();
        navigator.Show("search");
    }
}
