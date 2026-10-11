namespace Warehouse.Data;

public class Database
{
    private readonly Dictionary<string, string> _rows = new();

    public string? Read(string key) => _rows.GetValueOrDefault(key);

    public void Write(string key, string value) => _rows[key] = value;
}
