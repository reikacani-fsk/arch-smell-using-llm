namespace Library.Core.Catalog;

public record Book(string Isbn, string Title, string Author);

public class BookCatalog
{
    private readonly Dictionary<string, Book> _books = new();
    private readonly CatalogCache _cache = new();

    public void Add(Book book) => _books[book.Isbn] = book;

    public Book? Find(string isbn) => _cache.GetOrAdd(isbn, () => _books.GetValueOrDefault(isbn));

    public IEnumerable<Book> ByAuthor(string author) => _books.Values.Where(b => b.Author == author);
}

internal class CatalogCache
{
    private readonly Dictionary<string, (Book? Value, DateTime Expires)> _entries = new();

    public Book? GetOrAdd(string isbn, Func<Book?> load)
    {
        if (_entries.TryGetValue(isbn, out var entry) && entry.Expires > DateTime.UtcNow)
            return entry.Value;
        var value = load();
        _entries[isbn] = (value, DateTime.UtcNow.AddMinutes(5));
        return value;
    }
}
