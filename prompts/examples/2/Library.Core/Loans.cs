using Library.Core.Catalog;
using Library.Core.Members;

namespace Library.Core.Loans;

public record Loan(Book Book, Member Member, DateOnly Due);

public class LoanPolicy
{
    public int MaxLoans { get; init; } = 5;
    public int Days { get; init; } = 21;

    public bool Allows(Member member, int current) => !member.Blocked && current < MaxLoans;
}

public class LateFeeCalculator
{
    public decimal PerDay { get; init; } = 0.5m;

    public decimal FeeFor(Loan loan, DateOnly returned) =>
        Math.Max(0, returned.DayNumber - loan.Due.DayNumber) * PerDay;
}

public class LoanService(BookCatalog catalog, MemberRegistry members)
{
    private readonly LoanPolicy _policy = new();
    private readonly LateFeeCalculator _fees = new();
    private readonly List<Loan> _loans = new();

    public Loan Lend(string isbn, int memberId, DateOnly today)
    {
        var book = catalog.Find(isbn) ?? throw new ArgumentException($"unknown book {isbn}");
        var member = members.Find(memberId) ?? throw new ArgumentException($"unknown member {memberId}");
        if (!_policy.Allows(member, _loans.Count(l => l.Member.Id == memberId)))
            throw new InvalidOperationException($"member {memberId} may not borrow");
        var loan = new Loan(book, member, today.AddDays(_policy.Days));
        _loans.Add(loan);
        return loan;
    }

    public decimal Return(Loan loan, DateOnly today)
    {
        _loans.Remove(loan);
        return _fees.FeeFor(loan, today);
    }
}
