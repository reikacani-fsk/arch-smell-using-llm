using Library.Core.Catalog;
using Library.Core.Loans;
using Library.Core.Members;
using Xunit;

namespace Library.Tests;

internal static class BookBuilder
{
    public static Book Any(string isbn = "978-0") => new(isbn, "Dune", "Herbert");
}

public class BookCatalogTests
{
    [Fact]
    public void Finds_added_book()
    {
        var catalog = new BookCatalog();
        catalog.Add(BookBuilder.Any());
        Assert.NotNull(catalog.Find("978-0"));
    }
}

public class BookCatalogSearchTests
{
    [Fact]
    public void Filters_by_author()
    {
        var catalog = new BookCatalog();
        catalog.Add(BookBuilder.Any());
        Assert.Single(catalog.ByAuthor("Herbert"));
    }
}

public class CatalogCacheTests
{
    [Fact]
    public void Second_lookup_returns_cached_book()
    {
        var catalog = new BookCatalog();
        catalog.Add(BookBuilder.Any());
        Assert.Same(catalog.Find("978-0"), catalog.Find("978-0"));
    }
}

internal static class MemberBuilder
{
    public static Member Any(int id = 1) => new(id, "Ada", false);
}

public class MemberRegistryTests
{
    [Fact]
    public void Blocks_member()
    {
        var registry = new MemberRegistry();
        registry.Add(MemberBuilder.Any());
        registry.Block(1);
        Assert.True(registry.Find(1)!.Blocked);
    }
}

public class MemberCacheTests
{
    [Fact]
    public void Second_lookup_returns_cached_member()
    {
        var registry = new MemberRegistry();
        registry.Add(MemberBuilder.Any());
        Assert.Same(registry.Find(1), registry.Find(1));
    }
}

internal static class FixedClock
{
    public static DateOnly Today => new(2026, 1, 1);
}

internal class LoanScenario
{
    public BookCatalog Catalog { get; } = new();
    public MemberRegistry Members { get; } = new();
    public LoanService Service { get; }

    public LoanScenario()
    {
        Catalog.Add(new Book("978-0", "Dune", "Herbert"));
        Members.Add(new Member(1, "Ada", false));
        Service = new LoanService(Catalog, Members);
    }

    public Loan Lend() => Service.Lend("978-0", 1, FixedClock.Today);
}

public class LoanServiceTests
{
    [Fact]
    public void Returning_on_time_costs_nothing()
    {
        var scenario = new LoanScenario();
        var loan = scenario.Lend();
        Assert.Equal(0m, scenario.Service.Return(loan, FixedClock.Today));
    }
}

public class LoanPolicyTests
{
    [Fact]
    public void Blocked_member_may_not_borrow()
    {
        var scenario = new LoanScenario();
        scenario.Members.Block(1);
        Assert.Throws<InvalidOperationException>(() => scenario.Lend());
    }
}

public class LateFeeCalculatorTests
{
    [Fact]
    public void Charges_per_late_day()
    {
        var loan = new LoanScenario().Lend();
        Assert.Equal(1.5m, new LateFeeCalculator().FeeFor(loan, loan.Due.AddDays(3)));
    }
}
