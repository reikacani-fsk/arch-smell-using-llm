namespace Library.Core.Members;

public record Member(int Id, string Name, bool Blocked);

public class MemberRegistry
{
    private readonly Dictionary<int, Member> _members = new();
    private readonly MemberCache _cache = new();

    public void Add(Member member) => _members[member.Id] = member;

    public Member? Find(int id) => _cache.GetOrAdd(id, () => _members.GetValueOrDefault(id));

    public void Block(int id)
    {
        _members[id] = _members[id] with { Blocked = true };
        _cache.Evict(id);
    }
}

internal class MemberCache
{
    private readonly Dictionary<int, (Member? Value, DateTime Expires)> _entries = new();

    public Member? GetOrAdd(int id, Func<Member?> load)
    {
        if (_entries.TryGetValue(id, out var entry) && entry.Expires > DateTime.UtcNow)
            return entry.Value;
        var value = load();
        _entries[id] = (value, DateTime.UtcNow.AddMinutes(5));
        return value;
    }

    public void Evict(int id) => _entries.Remove(id);
}
