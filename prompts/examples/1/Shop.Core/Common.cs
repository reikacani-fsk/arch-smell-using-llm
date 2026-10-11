using System.Text;

namespace Shop.Core.Common;

public record SmtpSettings(string Host, int Port);

public class EmailSender
{
    private readonly SmtpSettings _settings;

    public EmailSender(SmtpSettings settings) => _settings = settings;

    public void Send(string to, string body) => Console.WriteLine($"[{_settings.Host}:{_settings.Port}] {to}: {body}");
}

public record CsvOptions(char Separator);

public class CsvExporter
{
    private readonly CsvOptions _options;

    public CsvExporter(CsvOptions options) => _options = options;

    public string Write(IEnumerable<string[]> rows) => string.Join("\n", rows.Select(r => string.Join(_options.Separator, r)));
}

public static class Crc32
{
    public static uint Compute(byte[] data)
    {
        uint crc = 0xFFFFFFFF;
        foreach (var b in data)
        {
            crc ^= b;
            for (var i = 0; i < 8; i++) crc = (crc >> 1) ^ (0xEDB88320 & (uint)-(int)(crc & 1));
        }
        return ~crc;
    }

    public static uint Compute(string text) => Compute(Encoding.UTF8.GetBytes(text));
}
