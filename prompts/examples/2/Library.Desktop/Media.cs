using Library.Desktop;

namespace Library.Desktop.Media;

public class AudiobookPlayer
{
    public PlaybackState State { get; private set; } = PlaybackState.Stopped;
    public string? File { get; private set; }

    public void Play(string file)
    {
        File = file;
        State = PlaybackState.Playing;
    }

    public void Pause() => State = PlaybackState.Paused;
}
